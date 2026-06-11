import asyncio
import html
import logging
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List

import yfinance as yf
import pandas as pd

from stock_data import get_top_stocks, get_stock_history, get_stock_info, SECTOR_MAP, INDONESIAN_STOCKS, _fetch_stock_card
from services.db import VOLUME_THRESHOLD, TRADE_HORIZON_DAYS, _now_iso
from services.cache import RedisClient

logger = logging.getLogger('saham-api')

# ── Thread pool for parallel yfinance calls ──
_executor = ThreadPoolExecutor(max_workers=5)

# ── Simple in-memory cache (backward compat with routes) ──
_market_summary_cache = {}
_news_cache: Dict[str, Dict[str, Any]] = {}

# Redis client singleton
_redis = RedisClient()


# ── News sentiment: lightweight RSS + Indonesian/English lexicon, no external dependency ──
POSITIVE_NEWS_WORDS = {
    'naik', 'menguat', 'positif', 'profit', 'laba', 'untung', 'rekor', 'dividen', 'buyback', 'akuisisi',
    'kontrak', 'ekspansi', 'tumbuh', 'pertumbuhan', 'surplus', 'upgrade', 'outperform', 'bullish',
    'rebound', 'recovery', 'meningkat', 'tertinggi', 'solid', 'kuat', 'bagus', 'prospek', 'target naik'
}
NEGATIVE_NEWS_WORDS = {
    'turun', 'melemah', 'negatif', 'rugi', 'kerugian', 'anjlok', 'koreksi', 'gugatan', 'denda',
    'utang', 'default', 'suspensi', 'delisting', 'fraud', 'korupsi', 'bearish', 'downgrade',
    'underperform', 'tekanan', 'terendah', 'lemah', 'pangkas', 'turun laba', 'loss'
}


def _plain_text(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()


def _news_sentiment_score(text: str) -> int:
    lowered = (text or '').lower()
    pos = sum(1 for w in POSITIVE_NEWS_WORDS if w in lowered)
    neg = sum(1 for w in NEGATIVE_NEWS_WORDS if w in lowered)
    return max(-3, min(3, pos - neg))


def _label_news(score: int) -> str:
    if score > 0:
        return 'POSITIVE'
    if score < 0:
        return 'NEGATIVE'
    return 'NEUTRAL'


def _fetch_news_for_symbol(symbol: str, limit: int = 8) -> Dict[str, Any]:
    clean_symbol = symbol.upper().replace('.JK', '').strip()
    cache_key = f'news:{clean_symbol}:{limit}'
    now = time.time()
    NEWS_TTL = 1800  # 30 minutes

    # Check Redis first
    redis_data = _redis.get_json(cache_key)
    if redis_data is not None:
        # Refresh in-memory for backward compat readers
        _news_cache[cache_key] = {'data': redis_data, 'timestamp': now}
        return redis_data

    # Fallback to in-memory cache
    cached = _news_cache.get(cache_key)
    if cached and (now - cached['timestamp']) < NEWS_TTL:
        return cached['data']

    company = SECTOR_MAP.get(clean_symbol + '.JK', '')
    query = f'{clean_symbol} saham OR emiten OR IDX'
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
        'q': query,
        'hl': 'id',
        'gl': 'ID',
        'ceid': 'ID:id',
    })
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 SahamApp/1.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read(350000)
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item')[:limit * 2]:
            title = _plain_text(item.findtext('title') or '')
            desc = _plain_text(item.findtext('description') or '')
            link = item.findtext('link') or ''
            published = item.findtext('pubDate') or ''
            text = f'{title} {desc}'
            if clean_symbol.lower() not in text.lower() and 'saham' not in text.lower() and 'emiten' not in text.lower():
                continue
            score = _news_sentiment_score(text)
            items.append({
                'title': title,
                'summary': desc[:220],
                'url': link,
                'published_at': published,
                'sentiment': _label_news(score),
                'sentiment_score': score,
            })
            if len(items) >= limit:
                break
    except Exception as exc:
        logger.info('news fetch failed for %s: %s', clean_symbol, exc)

    total_score = sum(int(i.get('sentiment_score') or 0) for i in items)
    pos = sum(1 for i in items if i.get('sentiment') == 'POSITIVE')
    neg = sum(1 for i in items if i.get('sentiment') == 'NEGATIVE')
    if total_score > 1 or pos > neg:
        overall = 'POSITIVE'
        reason = 'Berita terbaru cenderung positif, jadi menambah bobot BUY.'
    elif total_score < -1 or neg > pos:
        overall = 'NEGATIVE'
        reason = 'Berita terbaru cenderung negatif, jadi menambah bobot SELL / hindari.'
    else:
        overall = 'NEUTRAL'
        reason = 'Berita belum memberi bias kuat. Sinyal tetap dominan dari teknikal/fundamental.'
    data = {
        'symbol': clean_symbol,
        'sentiment': overall,
        'sentiment_score': max(-10, min(10, total_score)),
        'positive_count': pos,
        'negative_count': neg,
        'neutral_count': max(0, len(items) - pos - neg),
        'reason': reason,
        'items': items,
        'updated_at': _now_iso(),
    }
    _news_cache[cache_key] = {'data': data, 'timestamp': now}
    # Also cache in Redis for cross-process sharing
    _redis.set_json(cache_key, data, ttl=NEWS_TTL)
    return data


def _apply_news_bias(signal_obj: Dict[str, Any], news: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not news:
        return signal_obj
    score = int(news.get('sentiment_score') or 0)
    if score == 0:
        return signal_obj
    adjusted = dict(signal_obj)
    adjusted['reasons'] = list(signal_obj.get('reasons', []))
    delta = max(-8, min(8, score * 2))
    adjusted['strength'] = max(1, min(100, int(round(float(adjusted.get('strength', 50)) + delta))))
    if score > 0:
        adjusted['reasons'].append('Berita positif terdeteksi — menjadi pertimbangan tambahan untuk BUY')
    else:
        adjusted['reasons'].append('Berita negatif terdeteksi — menjadi pertimbangan tambahan untuk SELL / hindari')
    if adjusted['strength'] >= 65 and score > 0:
        adjusted['signal'] = 'BUY'
    elif adjusted['strength'] <= 40 and score < 0:
        adjusted['signal'] = 'SELL'
    elif 41 <= adjusted['strength'] <= 64:
        adjusted['signal'] = 'NEUTRAL'
    return adjusted


# ── Symbol / time helpers ──

def _ensure_symbol(symbol: str) -> str:
    """Add .JK suffix if missing."""
    s = symbol.upper().strip()
    if not s.endswith('.JK'):
        s = s + '.JK'
    return s


# ── Async helpers for yfinance ──

async def _run_sync_with_timeout(fn, *args, timeout=10, **kwargs):
    """Run a sync function in executor thread with timeout."""
    return await asyncio.wait_for(
        asyncio.get_event_loop().run_in_executor(_executor, lambda: fn(*args, **kwargs)),
        timeout=timeout,
    )


async def _fetch_stock_data_with_retry(fetch_func, *args, max_retries=2, timeout=10, fallback_symb=None, **kwargs):
    """Fetch yfinance data with retry and timeout.

    If all retries fail and fallback_symb is provided, tries the fallback provider.
    Returns None on total failure (or fallback data if available).
    """
    for attempt in range(max_retries):
        try:
            return await _run_sync_with_timeout(fetch_func, *args, timeout=timeout, **kwargs)
        except asyncio.TimeoutError:
            logger.warning('Timeout fetching data (attempt %d/%d) for %s', attempt + 1, max_retries, args[0] if args else '?')
        except Exception as exc:
            logger.warning('Error fetching data (attempt %d/%d) for %s: %s', attempt + 1, max_retries, args[0] if args else '?', exc)
        if attempt < max_retries - 1:
            await asyncio.sleep(1)

    # ── Fallback to alternative provider (S10) ──
    if fallback_symb:
        from services.fallback import fallback_get_stock_info, fallback_get_stock_history
        func_name = getattr(fetch_func, '__name__', str(fetch_func))
        logger.warning('Falling back to alternative provider for %s (%s)', fallback_symb, func_name)
        if 'info' in func_name.lower() or func_name == 'get_stock_info':
            return fallback_get_stock_info(fallback_symb)
        if 'history' in func_name.lower() or func_name == 'get_stock_history':
            return fallback_get_stock_history(fallback_symb)

    return None


# ── Redis-cached stock data helpers ──

STOCK_DATA_TTL = {
    'history_3mo': 600,    # 10 min
    'history_6mo': 900,    # 15 min
    'info': 600,           # 10 min
}
STALE_THRESHOLD = 3600     # 1 hour — data older than this is stale


def _cached_stock_key(prefix: str, symbol: str, *extra) -> str:
    s = symbol.upper().replace('.JK', '').strip()
    parts = [prefix, s]
    parts.extend(str(x) for x in extra)
    return ':'.join(parts)


def _mark_stale_if_needed(data: Any) -> Any:
    """If data is a dict, add stale=True when older than threshold.
    For DataFrames, returns unchanged (DataFrame not JSON-serialisable for Redis).
    """
    if isinstance(data, dict):
        ts = data.get('_cached_at', 0)
        if ts and (time.time() - ts) > STALE_THRESHOLD:
            data['stale'] = True
        else:
            data.setdefault('stale', False)
    return data


async def _cached_stock_history(symbol: str, period: str = '3mo') -> Optional[pd.DataFrame]:
    """Get stock history with Redis check. Falls back to get_stock_history + yfinance + fallback."""
    # DataFrame is not Redis-serialisable, so we bypass Redis for history
    # (in-memory cache in stock_data.py handles it)
    return await _fetch_stock_data_with_retry(get_stock_history, symbol, period, fallback_symb=symbol)


async def _cached_stock_info(symbol: str) -> dict:
    """Get stock info with Redis check + fallback."""
    cache_key = _cached_stock_key('info', symbol)
    cached = _redis.get_stock_data(cache_key)
    if cached is not None:
        return _mark_stale_if_needed(cached)

    info = await _fetch_stock_data_with_retry(get_stock_info, symbol, fallback_symb=symbol)
    if info:
        _redis.set_stock_data(cache_key, info, ttl=STOCK_DATA_TTL['info'])
    return info or {}

