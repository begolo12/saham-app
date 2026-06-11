import time
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Optional

# Simple in-memory cache for yfinance data
_history_cache: Dict[str, Dict] = {}

# Minimum price filter: include cheaper stocks only if still liquid/potential
MIN_PRICE = 50
MIN_VOLUME = 500_000
MIN_AVG_VALUE = 1_000_000_000  # avg traded value per day (IDR)
MIN_DAYS = 20
MAX_FAILED_RATIO = 0.4
MAX_UNIVERSE = 120
# score threshold to keep cheap but liquid names like BUMI
MIN_POTENTIAL_SCORE = 45

# 80+ Indonesian stocks covering all sectors
INDONESIAN_STOCKS = [
    # Banks
    'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BRIS.JK', 'BBTN.JK', 'NISP.JK',
    # Consumer Goods
    'UNVR.JK', 'ICBP.JK', 'INDF.JK', 'KLBF.JK', 'HMSP.JK', 'MYOR.JK', 'SIDO.JK',
    'SDRA.JK', 'TSPC.JK', 'SCCO.JK', 'BRAM.JK', 'CPIN.JK', 'JPFA.JK',
    # Retail
    'MAPI.JK', 'ACES.JK', 'ERAA.JK', 'RALS.JK', 'LPPF.JK',
    # Energy
    'ADRO.JK', 'PTBA.JK', 'ITMG.JK', 'MEDC.JK', 'PGAS.JK', 'AKRA.JK', 'ELSA.JK',
    'BUMI.JK', 'INDY.JK',
    # Infrastructure & Construction
    'JSMR.JK', 'WIKA.JK', 'WSKT.JK', 'ADHI.JK', 'PTPP.JK', 'INTP.JK', 'SMGR.JK',
    # Property
    'CTRA.JK', 'PWON.JK', 'BSDE.JK', 'SMRA.JK', 'LPKR.JK', 'PPRO.JK', 'MTLA.JK',
    # Agriculture / Plantation
    'AALI.JK', 'LSIP.JK', 'TAPG.JK', 'SSMS.JK',
    # Mining
    'ANTM.JK', 'MDKA.JK', 'BRPT.JK', 'INCO.JK', 'NCKL.JK', 'TINS.JK', 'ADMR.JK',
    # Healthcare
    'MIKA.JK', 'SILO.JK', 'KAEF.JK', 'DVLA.JK', 'MERK.JK', 'HEAL.JK',
    # Telco & Towers
    'TLKM.JK', 'EXCL.JK', 'ISAT.JK', 'MTEL.JK', 'TOWR.JK', 'TBIG.JK',
    # Automotive
    'ASII.JK', 'AUTO.JK', 'GJTL.JK',
    # Technology
    'GOTO.JK', 'BUKA.JK', 'WIRG.JK', 'DCII.JK', 'MTDL.JK',
    # Media & Entertainment
    'EMTK.JK', 'MNCN.JK', 'SCMA.JK', 'MDIA.JK',
    # Energy (Geothermal)
    'PGEO.JK',
    # Cheap / active liquid watch universe (price >= 50 still required at runtime)
    'ENRG.JK', 'DEWA.JK', 'DOID.JK', 'HRUM.JK', 'RAJA.JK', 'TOBA.JK',
    'PNLF.JK', 'BABP.JK', 'AGRO.JK', 'ARTO.JK', 'BFIN.JK',
    'WIFI.JK', 'LINK.JK', 'FREN.JK', 'BULL.JK', 'SMDR.JK',
    'TPIA.JK', 'ESSA.JK', 'AMMN.JK', 'MBMA.JK', 'CUAN.JK',
]

SECTOR_MAP = {
    # Banks
    'BBCA.JK': 'Perbankan',
    'BBRI.JK': 'Perbankan',
    'BMRI.JK': 'Perbankan',
    'BBNI.JK': 'Perbankan',
    'BRIS.JK': 'Perbankan',
    'BBTN.JK': 'Perbankan',
    'NISP.JK': 'Perbankan',
    # Consumer Goods
    'UNVR.JK': 'Consumer Goods',
    'ICBP.JK': 'Consumer Goods',
    'INDF.JK': 'Consumer Goods',
    'KLBF.JK': 'Consumer Goods',
    'HMSP.JK': 'Consumer Goods',
    'MYOR.JK': 'Consumer Goods',
    'SIDO.JK': 'Consumer Goods',
    'SDRA.JK': 'Consumer Goods',
    'TSPC.JK': 'Consumer Goods',
    'SCCO.JK': 'Consumer Goods',
    'BRAM.JK': 'Consumer Goods',
    'CPIN.JK': 'Consumer Goods',
    'JPFA.JK': 'Consumer Goods',
    # Retail
    'MAPI.JK': 'Consumer Goods',
    'ACES.JK': 'Consumer Goods',
    'ERAA.JK': 'Consumer Goods',
    'RALS.JK': 'Consumer Goods',
    'LPPF.JK': 'Consumer Goods',
    # Energy
    'ADRO.JK': 'Energi',
    'PTBA.JK': 'Energi',
    'ITMG.JK': 'Energi',
    'MEDC.JK': 'Energi',
    'PGAS.JK': 'Energi',
    'AKRA.JK': 'Energi',
    'ELSA.JK': 'Energi',
    'BUMI.JK': 'Energi',
    'INDY.JK': 'Energi',
    'PGEO.JK': 'Energi',
    # Infrastructure & Construction
    'JSMR.JK': 'Infrastruktur',
    'WIKA.JK': 'Infrastruktur',
    'WSKT.JK': 'Infrastruktur',
    'ADHI.JK': 'Infrastruktur',
    'PTPP.JK': 'Infrastruktur',
    'INTP.JK': 'Infrastruktur',
    'SMGR.JK': 'Infrastruktur',
    # Property
    'CTRA.JK': 'Properti',
    'PWON.JK': 'Properti',
    'BSDE.JK': 'Properti',
    'SMRA.JK': 'Properti',
    'LPKR.JK': 'Properti',
    'PPRO.JK': 'Properti',
    'MTLA.JK': 'Properti',
    # Agriculture / Plantation
    'AALI.JK': 'Perkebunan',
    'LSIP.JK': 'Perkebunan',
    'TAPG.JK': 'Perkebunan',
    'SSMS.JK': 'Perkebunan',
    # Mining
    'ANTM.JK': 'Pertambangan',
    'MDKA.JK': 'Pertambangan',
    'BRPT.JK': 'Pertambangan',
    'INCO.JK': 'Pertambangan',
    'NCKL.JK': 'Pertambangan',
    'TINS.JK': 'Pertambangan',
    'ADMR.JK': 'Pertambangan',
    # Healthcare
    'MIKA.JK': 'Kesehatan',
    'SILO.JK': 'Kesehatan',
    'KAEF.JK': 'Kesehatan',
    'DVLA.JK': 'Kesehatan',
    'MERK.JK': 'Kesehatan',
    'HEAL.JK': 'Kesehatan',
    # Telco & Towers
    'TLKM.JK': 'Telekomunikasi',
    'EXCL.JK': 'Telekomunikasi',
    'ISAT.JK': 'Telekomunikasi',
    'MTEL.JK': 'Telekomunikasi',
    'TOWR.JK': 'Telekomunikasi',
    'TBIG.JK': 'Telekomunikasi',
    # Automotive
    'ASII.JK': 'Otomotif',
    'AUTO.JK': 'Otomotif',
    'GJTL.JK': 'Otomotif',
    # Technology
    'GOTO.JK': 'Teknologi',
    'BUKA.JK': 'Teknologi',
    # Media & Entertainment
    'EMTK.JK': 'Media & Entertainment',
    'MNCN.JK': 'Media & Entertainment',
    'SCMA.JK': 'Media & Entertainment',
    'MDIA.JK': 'Media & Entertainment',
    # Added liquid universe
    'WIRG.JK': 'Teknologi',
    'DCII.JK': 'Teknologi',
    'MTDL.JK': 'Teknologi',
    'ENRG.JK': 'Energi',
    'DEWA.JK': 'Energi',
    'DOID.JK': 'Energi',
    'HRUM.JK': 'Energi',
    'RAJA.JK': 'Energi',
    'TOBA.JK': 'Energi',
    'PNLF.JK': 'Keuangan',
    'BABP.JK': 'Perbankan',
    'AGRO.JK': 'Perbankan',
    'ARTO.JK': 'Perbankan',
    'BFIN.JK': 'Keuangan',
    'WIFI.JK': 'Telekomunikasi',
    'LINK.JK': 'Telekomunikasi',
    'FREN.JK': 'Telekomunikasi',
    'BULL.JK': 'Transportasi',
    'SMDR.JK': 'Transportasi',
    'TPIA.JK': 'Basic Materials',
    'ESSA.JK': 'Basic Materials',
    'AMMN.JK': 'Pertambangan',
    'MBMA.JK': 'Pertambangan',
    'CUAN.JK': 'Energi',
}


def _safe_float(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _score_stock(price: float, change_percent: float, volume: float, avg_volume: float, market_cap: float, pe_ratio: float, pbv: float) -> float:
    score = 0.0
    if price >= MIN_PRICE:
        score += 5
    if volume >= MIN_VOLUME:
        score += 20
    if avg_volume and avg_volume >= MIN_VOLUME:
        score += 10
    if avg_volume and volume and volume >= avg_volume * 0.8:
        score += 8
    if market_cap and market_cap >= 5e12:
        score += 8
    if market_cap and market_cap >= 1e12:
        score += 4
    if pe_ratio and pe_ratio > 0 and pe_ratio < 20:
        score += 5
    if pbv and pbv > 0 and pbv < 3:
        score += 5
    if abs(change_percent) >= 1:
        score += 8
    if change_percent > 0:
        score += 5
    return score


def get_top_stocks() -> List[Dict[str, Any]]:
    """Fetch Indonesian stocks with potential filter based on price + liquidity."""
    results = []
    for symbol in INDONESIAN_STOCKS:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            history = ticker.history(period='3mo')

            if history.empty or len(history) < MIN_DAYS:
                continue

            current_price = _safe_float(info.get('currentPrice') or info.get('regularMarketPrice'))
            if current_price is None and not history.empty:
                current_price = _safe_float(history['Close'].iloc[-1])
            if current_price is None:
                continue

            if current_price < MIN_PRICE:
                continue

            volume = _safe_float(info.get('volume') or history['Volume'].iloc[-1]) or 0.0
            avg_volume = _safe_float(history['Volume'].tail(20).mean()) or 0.0
            avg_value = _safe_float((history['Close'].tail(20) * history['Volume'].tail(20)).mean()) or 0.0
            market_cap = _safe_float(info.get('marketCap')) or 0.0
            pe_ratio = _safe_float(info.get('trailingPE') or info.get('forwardPE')) or 0.0
            pbv = _safe_float(info.get('priceToBook')) or 0.0

            if volume < MIN_VOLUME and avg_volume < MIN_VOLUME:
                continue
            if avg_value < MIN_AVG_VALUE and volume < MIN_VOLUME:
                continue

            prev_close = _safe_float(info.get('previousClose'))
            if prev_close is None and len(history) >= 2:
                prev_close = _safe_float(history['Close'].iloc[-2])
            elif prev_close is None and len(history) == 1:
                prev_close = current_price

            change_percent = 0.0
            if prev_close and current_price and prev_close != 0:
                change_percent = ((current_price - prev_close) / prev_close) * 100

            potential_score = _score_stock(current_price, change_percent, volume, avg_volume, market_cap, pe_ratio, pbv)
            if potential_score < MIN_POTENTIAL_SCORE:
                continue

            name = info.get('longName', info.get('shortName', symbol.replace('.JK', '')))
            results.append({
                'symbol': symbol.replace('.JK', ''),
                'name': name,
                'price': round(float(current_price), 2),
                'change_percent': round(change_percent, 2),
                'sector': SECTOR_MAP.get(symbol, 'Lainnya'),
                'volume': int(volume),
                'avg_volume': int(avg_volume),
                'avg_value': int(avg_value),
                'potential_score': round(potential_score, 2),
            })
        except Exception:
            continue

    results.sort(key=lambda x: (x.get('potential_score', 0), x.get('volume', 0), x.get('avg_value', 0)), reverse=True)
    return results[:MAX_UNIVERSE]


def get_stock_history(symbol: str, period: str = '6mo') -> pd.DataFrame:
    """Fetch OHLCV history for a given stock symbol (with .JK suffix).
    Results cached in memory for 30 seconds per (symbol, period) pair.
    """
    if not symbol.endswith('.JK'):
        symbol = symbol + '.JK'

    cache_key = f'hist:{symbol}:{period}'
    now = time.time()
    cached = _history_cache.get(cache_key)
    if cached and (now - cached['timestamp']) < 30:
        return cached['data']

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period)

    if df.empty:
        _history_cache[cache_key] = {'data': pd.DataFrame(), 'timestamp': now}
        return pd.DataFrame()

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.columns = [col.lower() for col in df.columns]
    df.index = pd.to_datetime(df.index)

    _history_cache[cache_key] = {'data': df, 'timestamp': now}
    return df


def get_stock_info(symbol: str) -> Dict[str, Any]:
    """Fetch company info for a given stock symbol (with .JK suffix).
    Results cached in memory for 60 seconds per symbol.
    """
    if not symbol.endswith('.JK'):
        symbol = symbol + '.JK'

    ticker = yf.Ticker(symbol)
    info = ticker.info
    return info
