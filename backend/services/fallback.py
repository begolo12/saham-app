"""Fallback data provider (S10).

When yfinance fails, try scraping Yahoo Finance via requests + html parsing.
If all fails, return last cached data from signal_recommendations table.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from services.db import _db_conn

logger = logging.getLogger('saham-api')

# ── In-memory fallback cache ──
_fallback_info_cache: Dict[str, Dict] = {}
_fallback_history_cache: Dict[str, Dict] = {}


def _scrape_yahoo_finance_summary(symbol: str) -> Optional[Dict[str, Any]]:
    """Scrape summary/quote data from Yahoo Finance HTML page.

    Uses requests + simple regex parsing (no BeautifulSoup dependency).
    Returns dict with price, change, volume etc, or None on failure.
    """
    try:
        import urllib.request
        clean = symbol.replace('.JK', '')
        url = f'https://finance.yahoo.com/quote/{clean}.JK/'
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(200000).decode('utf-8', errors='replace')

        result: Dict[str, Any] = {'symbol': clean}

        # Try to extract price from various JSON-LD / data patterns
        price_match = re.search(
            r'"regularMarketPrice":\s*\{\s*"raw":\s*([\d.]+)',
            html,
        )
        if price_match:
            result['price'] = float(price_match.group(1))

        change_match = re.search(
            r'"regularMarketChangePercent":\s*\{\s*"raw":\s*([\d.-]+)',
            html,
        )
        if change_match:
            result['change_percent'] = float(change_match.group(1))

        volume_match = re.search(
            r'"regularMarketVolume":\s*\{\s*"raw":\s*(\d+)',
            html,
        )
        if volume_match:
            result['volume'] = int(volume_match.group(1))

        name_match = re.search(r'"shortName":\s*"([^"]+)"', html)
        if name_match:
            result['name'] = name_match.group(1)

        # Market cap
        mcap_match = re.search(r'"marketCap":\s*\{\s*"raw":\s*(\d+)', html)
        if mcap_match:
            result['market_cap'] = float(mcap_match.group(1))

        # Sector from page
        sector_match = re.search(r'"sector":\s*"([^"]+)"', html)
        if sector_match:
            result['sector'] = sector_match.group(1)

        if 'price' in result:
            return result

        logger.info('Fallback scrape for %s: no price found in HTML', clean)
        return None
    except Exception as exc:
        logger.info('Fallback scrape failed for %s: %s', symbol, exc)
        return None


def _get_cached_from_db(symbol: str) -> Optional[Dict[str, Any]]:
    """Get last cached stock data from signal_recommendations table."""
    try:
        clean = symbol.upper().replace('.JK', '')
        with _db_conn() as conn:
            row = conn.execute(
                '''SELECT symbol, name, recommendation as signal,
                          strength, price, volume, outcome,
                          return_pct, created_at
                   FROM signal_recommendations
                   WHERE REPLACE(symbol, '.JK', '') = ?
                   ORDER BY id DESC LIMIT 1''',
                (clean,),
            ).fetchone()
        if row:
            return dict(row)
        return None
    except Exception as exc:
        logger.warning('Fallback DB query failed for %s: %s', symbol, exc)
        return None


def _get_cached_history_from_db(symbol: str) -> Optional[pd.DataFrame]:
    """Get last cached history from signal_recommendations (limited data).

    Returns a minimal DataFrame or None.
    """
    cached = _get_cached_from_db(symbol)
    if cached and cached.get('price'):
        # Build a 1-row DataFrame with the cached price
        df = pd.DataFrame({
            'open': [float(cached['price'])],
            'high': [float(cached['price'])],
            'low': [float(cached['price'])],
            'close': [float(cached['price'])],
            'volume': [int(cached.get('volume', 0))],
        })
        return df
    return None


def fallback_get_stock_info(symbol: str) -> Dict[str, Any]:
    """Get stock info via fallback chain: scrape HTML -> DB cache -> empty.

    Returns at minimum a dict with 'symbol' key.
    """
    now = time.time()
    cache_key = f'fallback_info:{symbol}'
    cached = _fallback_info_cache.get(cache_key)
    if cached and (now - cached['_ts']) < 600:
        return cached['data']

    # Step 1: Try scraping Yahoo Finance
    scraped = _scrape_yahoo_finance_summary(symbol)
    if scraped:
        scraped['_source'] = 'scrape'
        _fallback_info_cache[cache_key] = {'data': scraped, '_ts': now}
        logger.info('Fallback info for %s: scraped from Yahoo Finance', symbol)
        return scraped

    # Step 2: Try DB cache
    db_cached = _get_cached_from_db(symbol)
    if db_cached:
        db_cached['_source'] = 'db-cache'
        _fallback_info_cache[cache_key] = {'data': db_cached, '_ts': now}
        logger.info('Fallback info for %s: from DB cache', symbol)
        return db_cached

    # Step 3: Return minimal placeholder
    logger.warning('Fallback info for %s: no data available', symbol)
    return {'symbol': symbol.replace('.JK', ''), '_source': 'empty'}


def fallback_get_stock_history(symbol: str) -> pd.DataFrame:
    """Get stock history via fallback chain: scrape -> DB cache -> empty DF.

    Returns a DataFrame (possibly empty).
    """
    now = time.time()
    cache_key = f'fallback_hist:{symbol}'
    cached = _fallback_history_cache.get(cache_key)
    if cached and (now - cached['_ts']) < 600:
        return cached['data']

    # Step 1: Try DB cache (yfinance history not easily scraped)
    db_df = _get_cached_history_from_db(symbol)
    if db_df is not None and not db_df.empty:
        _fallback_history_cache[cache_key] = {'data': db_df, '_ts': now}
        logger.info('Fallback history for %s: from DB cache', symbol)
        return db_df

    # Step 2: Try scraping summary page for at least current price
    scraped = _scrape_yahoo_finance_summary(symbol)
    if scraped and 'price' in scraped:
        df = pd.DataFrame({
            'open': [float(scraped['price'])],
            'high': [float(scraped['price'])],
            'low': [float(scraped['price'])],
            'close': [float(scraped['price'])],
            'volume': [int(scraped.get('volume', 0))],
        })
        _fallback_history_cache[cache_key] = {'data': df, '_ts': now}
        logger.info('Fallback history for %s: from scrape single price', symbol)
        return df

    logger.warning('Fallback history for %s: returning empty DF', symbol)
    return pd.DataFrame()
