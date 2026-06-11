import logging
import time

import pandas as pd
import yfinance as yf
from app import app
from services.db import USE_POSTGRES, _now_iso
from services.stock_service import _market_summary_cache

logger = logging.getLogger('saham-api')


def _valid_ihsg_price(value) -> bool:
    try:
        v = float(value)
        return 4500 <= v <= 9500
    except Exception:
        return False


@app.get('/api/market-summary')
async def market_summary():
    """
    Return IHSG index data (^JKSE). Cached for 15s.
    """
    now = time.time()
    cached = _market_summary_cache.get('data')
    if cached and (now - cached['timestamp']) < 15:
        return cached['data']

    fallback = {
        'name': 'IHSG — Indeks Harga Saham Gabungan',
        'symbol': '^JKSE',
        'price': None,
        'change': 0,
        'change_percent': 0,
        'high_52w': 9174.474,
        'low_52w': 4500.0,
        'volume': 0,
        'updated_at': _now_iso(),
        'stale': True,
    }
    try:
        ihsg = yf.Ticker('^JKSE')
        try:
            info = ihsg.fast_info or {}
        except Exception:
            info = {}
        # Google Finance shows intraday movement versus today's open.
        # Daily yfinance previous close can show positive gap (+0.74%) while
        # intraday chart is red (-1.90%). Prefer 1D intraday for user-facing IHSG.
        intraday = ihsg.history(period='1d', interval='1m', timeout=3)
        history = pd.DataFrame()
        if intraday.empty:
            history = ihsg.history(period='5d', timeout=3)
    except Exception as e:
        logger.warning('market_summary fallback: %s', e)
        _market_summary_cache['data'] = {'data': fallback, 'timestamp': now}
        return fallback

    current_price = None
    prev_close = None
    if not intraday.empty:
        closes = intraday['Close'].dropna()
        opens = intraday['Open'].dropna()
        if len(closes) and len(opens):
            current_price = float(closes.iloc[-1])
            prev_close = float(opens.iloc[0])
    if not _valid_ihsg_price(current_price):
        current_price = info.get('last_price') or info.get('regular_market_price')
    if not _valid_ihsg_price(current_price) and not history.empty:
        current_price = float(history['Close'].dropna().iloc[-1])
    if not _valid_ihsg_price(prev_close):
        prev_close = info.get('previous_close')
    if not _valid_ihsg_price(prev_close) and len(history) >= 2:
        prev_close = float(history['Close'].dropna().iloc[-2])
    if not _valid_ihsg_price(current_price):
        last_good = _market_summary_cache.get('last_good')
        if last_good:
            return last_good
        current_price = fallback['price']
        prev_close = fallback['price']

    change = 0.0
    change_percent = 0.0
    if prev_close and current_price:
        change = round(current_price - prev_close, 2)
        change_percent = round((change / prev_close) * 100, 2)

    result = {
        'name': 'IHSG — Indeks Harga Saham Gabungan',
        'symbol': '^JKSE',
        'price': current_price,
        'change': change,
        'change_percent': change_percent,
        'high_52w': info.get('year_high') or info.get('fiftyTwoWeekHigh') or fallback['high_52w'],
        'low_52w': info.get('year_low') or info.get('fiftyTwoWeekLow') or fallback['low_52w'],
        'volume': info.get('last_volume') or info.get('volume') or 0,
        'updated_at': _now_iso(),
    }
    if _valid_ihsg_price(result['price']):
        _market_summary_cache['last_good'] = result
    _market_summary_cache['data'] = {'data': result, 'timestamp': now}
    return result


@app.get('/health')
async def health():
    return {
        'status': 'ok',
        'service': 'saham-app-api',
        'database': 'postgres' if USE_POSTGRES else 'sqlite',
    }
