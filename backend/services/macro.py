"""
Macro Economic Data Integration — BI rate, inflation, USD/IDR, sector correlation.
Data cached with 1-hour TTL.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import yfinance as yf

from services.cache import RedisClient
from services.db import _db_conn, _now_iso, USE_POSTGRES

logger = logging.getLogger('saham-api')

# Cache TTL = 1 hour
MACRO_CACHE_TTL = 3600

# In-memory fallback cache
_macro_cache: Dict[str, Dict[str, Any]] = {}
_redis = RedisClient()


# ── Data fetching ──


def fetch_bi_rate() -> Dict[str, Any]:
    """Fetch Bank Indonesia benchmark interest rate.

    Currently returns dummy data since BI does not offer a free API.
    In production, replace with scraping BI website or a paid data provider.
    """
    cache_key = 'macro:bi_rate'
    # Check Redis
    cached = _redis.get_json(cache_key)
    if cached is not None:
        return cached
    # Check in-memory
    now = time.time()
    local = _macro_cache.get(cache_key)
    if local and (now - local['_ts']) < MACRO_CACHE_TTL:
        return local

    # BI rate as of latest (dummy — update manually or via scraping)
    data = {
        'rate': 6.00,  # BI rate in percent (latest: 6.00%)
        'previous_rate': 6.00,
        'change': 0.0,
        'change_pct': 0.0,
        'updated_at': '2025-12-01T00:00:00Z',
        'source': 'dummy (BI website / scraping needed)',
    }
    # Try to fetch from public source
    try:
        import urllib.request
        import json
        # Try FRED API (free tier) — Federal Reserve Data
        # BI rate not directly available, but we can track it via USD/IDR relation
        pass
    except Exception:
        pass

    # Cache
    data['_ts'] = now
    _macro_cache[cache_key] = data
    _redis.set_json(cache_key, {k: v for k, v in data.items() if k != '_ts'}, ttl=MACRO_CACHE_TTL)
    return data


def fetch_inflation() -> Dict[str, Any]:
    """Fetch Indonesia inflation rate (CPI YoY%).

    Currently returns dummy data. In production, scrape BPS (BPS.go.id).
    """
    cache_key = 'macro:inflation'
    cached = _redis.get_json(cache_key)
    if cached is not None:
        return cached
    now = time.time()
    local = _macro_cache.get(cache_key)
    if local and (now - local['_ts']) < MACRO_CACHE_TTL:
        return local

    # Indonesia inflation — dummy
    data = {
        'cpi_yoy': 2.04,  # latest CPI YoY %
        'core_inflation': 2.26,
        'month': 'November',
        'year': 2025,
        'updated_at': '2025-12-01T00:00:00Z',
        'source': 'dummy (BPS scraping needed)',
    }
    data['_ts'] = now
    _macro_cache[cache_key] = data
    _redis.set_json(cache_key, {k: v for k, v in data.items() if k != '_ts'}, ttl=MACRO_CACHE_TTL)
    return data


def fetch_usd_idr() -> Dict[str, Any]:
    """Fetch USD/IDR exchange rate via yfinance."""
    cache_key = 'macro:usd_idr'
    cached = _redis.get_json(cache_key)
    if cached is not None:
        return cached
    now = time.time()
    local = _macro_cache.get(cache_key)
    if local and (now - local['_ts']) < MACRO_CACHE_TTL:
        return local

    data = {
        'rate': None,
        'change': 0.0,
        'change_pct': 0.0,
        'high_5d': None,
        'low_5d': None,
        'updated_at': _now_iso(),
        'source': 'yfinance (USDIDR=X)',
    }
    try:
        usdidr = yf.Ticker('USDIDR=X')
        hist = usdidr.history(period='5d', timeout=5)
        if not hist.empty:
            last_close = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else last_close
            data['rate'] = round(last_close, 2)
            data['change'] = round(last_close - prev_close, 2)
            data['change_pct'] = round(((last_close - prev_close) / prev_close) * 100, 4) if prev_close else 0.0
            data['high_5d'] = round(float(hist['High'].max()), 2)
            data['low_5d'] = round(float(hist['Low'].min()), 2)
    except Exception as exc:
        logger.warning('Failed to fetch USD/IDR: %s', exc)
        data['rate'] = 15500.0  # dummy fallback

    data['_ts'] = now
    _macro_cache[cache_key] = data
    _redis.set_json(cache_key, {k: v for k, v in data.items() if k != '_ts'}, ttl=MACRO_CACHE_TTL)
    return data


# ── Sector correlation ──


SECTOR_MACRO_FACTORS: Dict[str, List[Dict[str, Any]]] = {
    'Perbankan': [
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Suku bunga tinggi menekan kredit dan NIM'},
        {'factor': 'Inflasi', 'direction': 'negative', 'reason': 'Inflasi tinggi → BI rate naik → sektor tertekan'},
    ],
    'Keuangan Non-Bank': [
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Bunga tinggi => biaya dana naik'},
    ],
    'Pertambangan': [
        {'factor': 'USD/IDR', 'direction': 'positive', 'reason': 'IDR lemah = ekspor tambang lebih kompetitif'},
        {'factor': 'Inflasi', 'direction': 'neutral', 'reason': 'Dampak tidak langsung via biaya operasional'},
    ],
    'Perkebunan': [
        {'factor': 'USD/IDR', 'direction': 'positive', 'reason': 'Komoditas CPO/karet dihargai USD, IDR lemah = untung'},
    ],
    'Properti & Real Estat': [
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Bunga tinggi → KPR turun → daya beli properti turun'},
        {'factor': 'Inflasi', 'direction': 'negative', 'reason': 'Inflasi tinggi → biaya material naik'},
    ],
    'Infrastruktur': [
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Proyek infrastruktur sensitif suku bunga pinjaman'},
    ],
    'Barang Konsumsi': [
        {'factor': 'Inflasi', 'direction': 'negative', 'reason': 'Inflasi tinggi → daya beli turun'},
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Bunga tinggi → konsumsi tertahan'},
    ],
    'Teknologi': [
        {'factor': 'BI Rate', 'direction': 'negative', 'reason': 'Tech stocks sensitif terhadap suku bunga (discount rate)'},
    ],
    'Energi': [
        {'factor': 'USD/IDR', 'direction': 'mixed', 'reason': 'Harga migas di USD, IDR lemah = biaya impor naik'},
    ],
    'Transportasi': [
        {'factor': 'USD/IDR', 'direction': 'negative', 'reason': 'IDR lemah → biaya bahan bakar impor naik'},
        {'factor': 'Inflasi', 'direction': 'negative', 'reason': 'Biaya operasional naik'},
    ],
    'Farmasi': [
        {'factor': 'USD/IDR', 'direction': 'negative', 'reason': 'Impor bahan baku obat dalam USD'},
    ],
}


def macro_correlation(sector: str) -> Dict[str, Any]:
    """Return macro factors affecting a given sector."""
    factors = SECTOR_MACRO_FACTORS.get(sector, [])
    if not factors:
        # Try partial match
        for key, vals in SECTOR_MACRO_FACTORS.items():
            if key.lower() in sector.lower() or sector.lower() in key.lower():
                factors = vals
                break
    return {
        'sector': sector,
        'factors': factors,
        'has_macro_sensitivity': len(factors) > 0,
    }


def apply_macro_bias(signal_obj: Dict[str, Any], sector: str) -> Dict[str, Any]:
    """Adjust signal strength based on current macro conditions.

    Negative macro → reduce BUY strength; Positive macro → enhance.
    """
    result = dict(signal_obj)
    result['reasons'] = list(signal_obj.get('reasons', []))

    if not sector:
        return result

    # Get current macro data
    bi_rate = fetch_bi_rate()
    usd_idr = fetch_usd_idr()
    inflation = fetch_inflation()
    correlation = macro_correlation(sector)

    if not correlation['has_macro_sensitivity']:
        return result

    current_signal = result.get('signal', 'NEUTRAL')
    current_strength = result.get('strength', 50)
    adjustment = 0.0
    macro_notes = []

    for factor in correlation['factors']:
        f_name = factor['factor']
        f_dir = factor['direction']

        if f_name == 'BI Rate':
            rate = bi_rate.get('rate', 6.0)
            if rate > 6.0 and f_dir == 'negative':
                adj = -5
                macro_notes.append(f'BI Rate {rate}% — sektor {sector} tertekan bunga tinggi')
            elif rate < 5.0 and f_dir == 'negative':
                adj = 3  # rate turun, positive for most
                macro_notes.append(f'BI Rate turun ke {rate}% — sentimen positif untuk {sector}')
            else:
                adj = 0
            adjustment += adj

        elif f_name == 'USD/IDR':
            rate = usd_idr.get('rate', 0)
            if rate and rate > 16000 and f_dir in ('positive', 'mixed'):
                adj = 5  # Weak IDR helps mining/plantation
                macro_notes.append(f'USD/IDR {rate:.0f} — IDR lemah untung sektor {sector}')
            elif rate and rate < 15000 and f_dir in ('negative', 'mixed'):
                adj = 3  # Strong IDR helps transport/pharma
                macro_notes.append(f'USD/IDR {rate:.0f} — IDR kuat untung sektor {sector}')
            elif rate and rate > 16000 and f_dir == 'negative':
                adj = -5  # Weak IDR hurts transport/pharma
                macro_notes.append(f'USD/IDR {rate:.0f} — IDR lemah tekan sektor {sector}')
            else:
                adj = 0
            adjustment += adj

        elif f_name == 'Inflasi':
            cpi = inflation.get('cpi_yoy', 2.0)
            if cpi > 4.0 and f_dir == 'negative':
                adj = -5
                macro_notes.append(f'Inflasi {cpi}% — daya beli dan margin tertekan')
            elif cpi < 2.0 and f_dir == 'negative':
                adj = 3
                macro_notes.append(f'Inflasi rendah {cpi}% — sentimen positif')
            else:
                adj = 0
            adjustment += adj

    if adjustment != 0:
        result['strength'] = max(1, min(100, int(current_strength + adjustment)))
        for note in macro_notes[:3]:
            result['reasons'].append(f'[Makro] {note}')
        # Re-evaluate signal if needed
        if result['strength'] >= 65 and current_signal != 'BUY':
            result['signal'] = 'BUY'
        elif result['strength'] <= 35 and current_signal != 'SELL':
            result['signal'] = 'SELL'
        elif 36 <= result['strength'] <= 64:
            result['signal'] = 'NEUTRAL'

    return result


# ── Market regime persistence ──


def save_market_regime(regime_info: Dict[str, Any]) -> bool:
    """Save daily market regime data to market_regime table."""
    try:
        with _db_conn() as conn:
            date_str = _now_iso()[:10]
            conn.execute(
                _sql('''
                    INSERT OR REPLACE INTO market_regime
                    (date, regime, confidence, ihsg_trend, volatility)
                    VALUES (?, ?, ?, ?, ?)
                '''),
                (
                    date_str,
                    regime_info.get('regime', 'ranging'),
                    regime_info.get('confidence', 0.5),
                    regime_info.get('ihsg_trend', 0),
                    regime_info.get('volatility', 0),
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning('Failed to save market regime: %s', exc)
        return False


def _sql(sql: str) -> str:
    if not USE_POSTGRES:
        return sql
    return sql.replace('?', '%s')


def get_latest_market_regime() -> Optional[Dict[str, Any]]:
    """Get latest market regime from DB."""
    try:
        with _db_conn() as conn:
            row = conn.execute(
                'SELECT * FROM market_regime ORDER BY date DESC LIMIT 1'
            ).fetchone()
        if row:
            return dict(row)
    except Exception:
        pass
    return None
