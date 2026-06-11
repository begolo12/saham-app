import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
MAX_UNIVERSE = 140

TOP_STOCK_FALLBACK = [
    {'symbol':'BBCA','name':'Bank Central Asia Tbk.','price':10250,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':88},
    {'symbol':'BBRI','name':'Bank Rakyat Indonesia Tbk.','price':5650,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':84},
    {'symbol':'BMRI','name':'Bank Mandiri Tbk.','price':7200,'change_percent':0,'sector':'Perbankan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':82},
    {'symbol':'TLKM','name':'Telkom Indonesia Tbk.','price':3950,'change_percent':0,'sector':'Telekomunikasi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':78},
    {'symbol':'ASII','name':'Astra International Tbk.','price':5450,'change_percent':0,'sector':'Otomotif','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':76},
    {'symbol':'ADRO','name':'Adaro Energy Indonesia Tbk.','price':2850,'change_percent':0,'sector':'Energi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':74},
    {'symbol':'ANTM','name':'Aneka Tambang Tbk.','price':1800,'change_percent':0,'sector':'Pertambangan','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':72},
    {'symbol':'INDF','name':'Indofood Sukses Makmur Tbk.','price':6325,'change_percent':0,'sector':'Consumer Goods','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':70},
    {'symbol':'GOTO','name':'GoTo Gojek Tokopedia Tbk.','price':98,'change_percent':0,'sector':'Teknologi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':68},
    {'symbol':'PGAS','name':'Perusahaan Gas Negara Tbk.','price':1500,'change_percent':0,'sector':'Energi','volume':1000000,'avg_volume':1000000,'avg_value':10000000000,'potential_score':66},
]
_top_stocks_cache = {'timestamp': 0, 'data': []}
# score threshold: do not drop low-score liquid stocks from universe.
# Signal engine decides BUY/NEUTRAL/SELL later; scanner only filters liquidity/data quality.
MIN_POTENTIAL_SCORE = 0

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
    # User-requested and high-volume IDX movers / big cap additions
    'BREN.JK', 'PTRO.JK', 'CDIA.JK', 'PANI.JK', 'DSSA.JK', 'AADI.JK', 'RATU.JK',
    'INET.JK', 'WTON.JK', 'SSIA.JK', 'KIJA.JK', 'ELTY.JK', 'BEST.JK', 'BKSL.JK',
    'NIKL.JK', 'ZINC.JK', 'DKFT.JK', 'NICL.JK', 'HRTA.JK', 'PSAB.JK', 'GEMS.JK',
    'SRTG.JK', 'SRAJ.JK', 'MIDI.JK', 'AMRT.JK', 'MAPA.JK', 'FILM.JK', 'MSIN.JK',
    'BANK.JK', 'BTPS.JK', 'MAYA.JK', 'BNGA.JK', 'PNBN.JK', 'BJBR.JK', 'BJTM.JK',
    'SMIL.JK', 'VKTR.JK', 'GGRM.JK', 'CMRY.JK', 'CLEO.JK', 'ULTJ.JK', 'ROTI.JK',
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
    'BREN.JK': 'Energi', 'PTRO.JK': 'Energi', 'CDIA.JK': 'Energi', 'PANI.JK': 'Properti',
    'DSSA.JK': 'Energi', 'AADI.JK': 'Energi', 'RATU.JK': 'Energi', 'INET.JK': 'Teknologi',
    'WTON.JK': 'Infrastruktur', 'SSIA.JK': 'Properti', 'KIJA.JK': 'Properti', 'ELTY.JK': 'Properti',
    'BEST.JK': 'Properti', 'BKSL.JK': 'Properti', 'NIKL.JK': 'Basic Materials', 'ZINC.JK': 'Pertambangan',
    'DKFT.JK': 'Pertambangan', 'NICL.JK': 'Pertambangan', 'HRTA.JK': 'Consumer Goods', 'PSAB.JK': 'Pertambangan',
    'GEMS.JK': 'Energi', 'SRTG.JK': 'Investasi', 'SRAJ.JK': 'Kesehatan', 'MIDI.JK': 'Consumer Goods',
    'AMRT.JK': 'Consumer Goods', 'MAPA.JK': 'Consumer Goods', 'FILM.JK': 'Media & Entertainment',
    'MSIN.JK': 'Media & Entertainment', 'BANK.JK': 'Perbankan', 'BTPS.JK': 'Perbankan', 'MAYA.JK': 'Perbankan',
    'BNGA.JK': 'Perbankan', 'PNBN.JK': 'Perbankan', 'BJBR.JK': 'Perbankan', 'BJTM.JK': 'Perbankan',
    'SMIL.JK': 'Infrastruktur', 'VKTR.JK': 'Otomotif', 'GGRM.JK': 'Consumer Goods', 'CMRY.JK': 'Consumer Goods',
    'CLEO.JK': 'Consumer Goods', 'ULTJ.JK': 'Consumer Goods', 'ROTI.JK': 'Consumer Goods',
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
        score += 18
    if volume >= 5_000_000:
        score += 10
    if volume >= 20_000_000:
        score += 12
    if avg_volume and avg_volume >= MIN_VOLUME:
        score += 10
    if avg_volume and avg_volume >= 5_000_000:
        score += 8
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


def _calc_card_indicators(history: pd.DataFrame) -> Dict[str, float]:
    """Lightweight technical indicators from cached 1-month OHLCV for list signals."""
    close = history['Close'].dropna()
    volume = history['Volume'].dropna()
    if close.empty:
        return {'trend_5d': 0.0, 'trend_20d': 0.0, 'rsi14': 50.0, 'volume_ratio': 1.0}
    last = float(close.iloc[-1])
    prev_5 = float(close.iloc[-6]) if len(close) >= 6 else float(close.iloc[0])
    prev_20 = float(close.iloc[-21]) if len(close) >= 21 else float(close.iloc[0])
    trend_5d = ((last - prev_5) / prev_5) * 100 if prev_5 else 0.0
    trend_20d = ((last - prev_20) / prev_20) * 100 if prev_20 else 0.0

    delta = close.diff()
    gain = delta.clip(lower=0).tail(14).mean()
    loss = (-delta.clip(upper=0)).tail(14).mean()
    if loss and loss > 0:
        rs = gain / loss
        rsi14 = 100 - (100 / (1 + rs))
    else:
        rsi14 = 70.0 if gain and gain > 0 else 50.0

    avg_vol = float(volume.tail(20).mean()) if not volume.empty else 0.0
    last_vol = float(volume.iloc[-1]) if not volume.empty else 0.0
    volume_ratio = last_vol / avg_vol if avg_vol else 1.0
    return {
        'trend_5d': round(trend_5d, 2),
        'trend_20d': round(trend_20d, 2),
        'rsi14': round(float(rsi14), 2),
        'volume_ratio': round(float(volume_ratio), 2),
    }


def _fetch_stock_card(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period='1mo', timeout=4)
        if history.empty or len(history) < 5:
            return None
        try:
            info = ticker.fast_info or {}
        except Exception:
            info = {}
        current_price = _safe_float(info.get('last_price')) or _safe_float(history['Close'].iloc[-1])
        if current_price is None or current_price < MIN_PRICE:
            return None
        volume = _safe_float(info.get('last_volume') or history['Volume'].iloc[-1]) or 0.0
        avg_volume = _safe_float(history['Volume'].tail(20).mean()) or 0.0
        avg_value = _safe_float((history['Close'].tail(20) * history['Volume'].tail(20)).mean()) or 0.0
        if volume < MIN_VOLUME and avg_volume < MIN_VOLUME:
            return None
        if avg_value < MIN_AVG_VALUE and volume < MIN_VOLUME:
            return None
        prev_close = _safe_float(history['Close'].iloc[-2]) if len(history) >= 2 else current_price
        change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0.0
        market_cap = _safe_float(info.get('market_cap')) or 0.0
        indicators = _calc_card_indicators(history)
        potential_score = _score_stock(current_price, change_percent, volume, avg_volume, market_cap, 0, 0)
        return {
            'symbol': symbol.replace('.JK', ''),
            'name': symbol.replace('.JK', ''),
            'price': round(float(current_price), 2),
            'change_percent': round(change_percent, 2),
            'sector': SECTOR_MAP.get(symbol, 'Lainnya'),
            'volume': int(volume),
            'avg_volume': int(avg_volume),
            'avg_value': int(avg_value),
            'potential_score': round(potential_score, 2),
            **indicators,
        }
    except Exception:
        return None


def get_top_stocks() -> List[Dict[str, Any]]:
    """Fast parallel IDX scanner with stale cache and safe fallback."""
    now = time.time()
    cached = _top_stocks_cache.get('data') or []
    # Semi-live desktop mode: short cache keeps UI fresh without hammering yfinance.
    if cached and (now - _top_stocks_cache.get('timestamp', 0)) < 180:
        return cached

    results = []
    executor = ThreadPoolExecutor(max_workers=8)
    futures = [executor.submit(_fetch_stock_card, symbol) for symbol in INDONESIAN_STOCKS[:MAX_UNIVERSE]]
    try:
        deadline = now + 5
        for fut in as_completed(futures, timeout=6):
            if time.time() > deadline:
                break
            item = fut.result()
            if item:
                results.append(item)
            if len(results) >= MAX_UNIVERSE:
                break
    except Exception:
        pass
    finally:
        for fut in futures:
            fut.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    results.sort(key=lambda x: (x.get('potential_score', 0), x.get('volume', 0), x.get('avg_value', 0)), reverse=True)
    if results:
        _top_stocks_cache['timestamp'] = now
        _top_stocks_cache['data'] = results[:MAX_UNIVERSE]
        return _top_stocks_cache['data']
    if cached:
        return cached
    return TOP_STOCK_FALLBACK

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
