import asyncio
import logging
import math
import re
from typing import Optional, Dict, Any

import pandas as pd
import yfinance as yf
from fastapi import HTTPException
from fastapi import Depends

from app import app
from stock_data import get_top_stocks, get_stock_history, get_stock_info, SECTOR_MAP, INDONESIAN_STOCKS, _fetch_stock_card
from analysis import (
    calc_rsi, calc_macd, calc_sma, calc_bollinger, analyze_fundamentals,
    generate_fundamental_signal, combine_signals,
)
from services.db import (
    VOLUME_THRESHOLD, _now_iso, _record_recommendation, _db_conn, current_user,
)
from services.stock_service import (
    _ensure_symbol, _fetch_stock_data_with_retry, _fetch_news_for_symbol,
    _apply_news_bias, _news_cache, _executor,
)
from services.analysis_service import (
    _fast_list_signal, _apply_learning_signal, _make_trade_plan,
    _daily_check_from_plan,
)

logger = logging.getLogger('saham-api')


# ──────────────────────────────────────────────
# NaN/Inf sanitization (S17)
# ──────────────────────────────────────────────

def _clean_float(v):
    """Replace NaN / +Inf / -Inf with None so JSON serialization never 500s.

    Non-float values (None, int, str, list, dict, ...) are returned as-is.
    Recurses into dicts and lists so nested numeric fields (e.g. 'pe_ratio'
    inside 'fundamental') are also covered.
    """
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, dict):
        return {k: _clean_float(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_clean_float(item) for item in v]
    if isinstance(v, tuple):
        return tuple(_clean_float(item) for item in v)
    return v


def _sanitize_stock_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively walk a stock result dict and replace any NaN/Inf floats with None."""
    return _clean_float(d)


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get('/api/stocks')
async def list_stocks(limit: Optional[int] = None, all: bool = False):
    """Fast stock list. Heavy detail analysis runs only on detail page."""
    stocks = get_top_stocks()
    updated_at = _now_iso()

    def _quick_signal(s):
        return _fast_list_signal(s)

    results = []
    for s in stocks:
        signal, strength = _quick_signal(s)
        symbol = s['symbol'].replace('.JK', '')
        results.append({
            'symbol': symbol,
            'name': s.get('name') or symbol,
            'price': s.get('price'),
            'change_percent': s.get('change_percent', 0),
            'signal': signal,
            'signal_strength': strength,
            'sector': s.get('sector', 'Lainnya'),
            'volume': s.get('volume', 0),
            'avg_volume': s.get('avg_volume', 0),
            'potential_score': s.get('potential_score', 0),
            'trend_5d': s.get('trend_5d', 0),
            'trend_20d': s.get('trend_20d', 0),
            'rsi14': s.get('rsi14', 50),
            'volume_ratio': s.get('volume_ratio', 1),
            'trade_plan': _make_trade_plan(symbol, float(s.get('price') or 0), signal, strength),
        })

    results.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
    if not all:
        results = results[:(limit if limit is not None else 50)]
    return _sanitize_stock_dict({'stocks': results, 'updated_at': updated_at, 'mode': 'fast'})


@app.get('/api/stocks/search')
async def search_stocks(q: str):
    """Search full tracked IDX universe, including tickers not in current top snapshot."""
    if not q or q.strip() == '':
        return {'stocks': [], 'query': q, 'updated_at': _now_iso()}

    # Sanitize: length limit + strip shell/metacharacters
    q = q.strip()[:100]
    q = re.sub(r'[;\'\\"<>|&`$]', '', q)
    q_lower = q.lower().replace('.jk', '')
    if not q_lower:
        return {'stocks': [], 'query': q, 'updated_at': _now_iso()}
    updated_at = _now_iso()

    # Start from cached/top data, then add direct universe ticker/name/sector matches.
    matching_by_symbol = {}
    for s in get_top_stocks():
        sym = s['symbol'].replace('.JK', '')
        if q_lower in sym.lower() or q_lower in (s.get('name') or '').lower() or q_lower in (s.get('sector') or '').lower():
            matching_by_symbol[sym] = s

    direct_symbols = []
    for full_symbol in INDONESIAN_STOCKS:
        sym = full_symbol.replace('.JK', '')
        sector = SECTOR_MAP.get(full_symbol, 'Lainnya')
        if q_lower in sym.lower() or q_lower in sector.lower():
            direct_symbols.append(full_symbol)

    # Direct fetch makes CUAN/BREN/PTRO searchable even when not in top list.
    for full_symbol in direct_symbols[:20]:
        sym = full_symbol.replace('.JK', '')
        if sym in matching_by_symbol:
            continue
        card = _fetch_stock_card(full_symbol)
        if card:
            matching_by_symbol[sym] = card
        else:
            matching_by_symbol[sym] = {
                'symbol': sym,
                'name': sym,
                'price': 0,
                'change_percent': 0,
                'sector': SECTOR_MAP.get(full_symbol, 'Lainnya'),
                'volume': 0,
                'avg_volume': 0,
                'avg_value': 0,
                'potential_score': 0,
            }

    def _quick_result(s):
        signal, strength = _fast_list_signal(s)
        symbol = s['symbol'].replace('.JK', '')
        return {
            'symbol': symbol,
            'name': s.get('name') or symbol,
            'price': s.get('price'),
            'change_percent': s.get('change_percent', 0),
            'signal': signal,
            'signal_strength': strength,
            'sector': s.get('sector', 'Lainnya'),
            'volume': s.get('volume', 0),
            'avg_volume': s.get('avg_volume', 0),
            'potential_score': s.get('potential_score', 0),
            'trend_5d': s.get('trend_5d', 0),
            'trend_20d': s.get('trend_20d', 0),
            'rsi14': s.get('rsi14', 50),
            'volume_ratio': s.get('volume_ratio', 1),
            'trade_plan': _make_trade_plan(symbol, float(s.get('price') or 0), signal, strength),
        }

    results = [_quick_result(s) for s in matching_by_symbol.values()]
    results.sort(key=lambda x: (x.get('signal_strength', 0), x.get('volume', 0)), reverse=True)
    return _sanitize_stock_dict({'stocks': results, 'query': q, 'count': len(results), 'updated_at': updated_at})


@app.get('/api/stocks/batch')
async def stocks_batch(symbols: Optional[str] = None):
    """
    Return detailed analysis for ALL 10 stocks in ONE call.
    Uses ThreadPoolExecutor (max_workers=5) to parallelize yfinance calls.

    Optional query param:
      - symbols: comma-separated list of tickers (e.g. "BBCA,BBRI"). When provided,
        only stocks whose symbol (with .JK suffix) appears in the list are analyzed.
    """
    all_stocks = get_top_stocks()
    if symbols:
        wanted = {s.strip().upper() for s in symbols.split(',') if s.strip()}
        wanted_full = {f'{s}.JK' for s in wanted}
        wanted_full.update(wanted)  # tolerate both "BBCA" and "BBCA.JK" inputs
        stocks = [s for s in all_stocks if s['symbol'].upper() in wanted_full]
    else:
        stocks = all_stocks
    results = []
    errors = []
    updated_at = _now_iso()

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'

            # Fetch with retry + timeout via executor
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo', fallback_symb=symbol_full)
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full, fallback_symb=symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal, df=df)

            # RSI
            rsi_val = None
            if df is not None and not df.empty:
                rsi_series = calc_rsi(df['close'])
                rsi_val = round(float(rsi_series.iloc[-1]), 2) if not pd.isna(rsi_series.iloc[-1]) else None

            # Fundamental vals
            pe_ratio = None
            pbv = None
            if info:
                # Explicit None-check: a negative PE is valid (loss-making company)
                # and must not collapse to 0 just because it is truthy-falsy.
                pe_val = info.get('trailingPE')
                if pe_val is None:
                    pe_val = info.get('forwardPE')
                if pe_val is not None:
                    try:
                        pe_ratio = round(float(pe_val), 2)
                    except (TypeError, ValueError):
                        pe_ratio = None
                pbv_val = info.get('priceToBook')
                if pbv_val is not None:
                    try:
                        pbv = round(float(pbv_val), 2)
                    except (TypeError, ValueError):
                        pbv = None

            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'name': s['name'],
                'price': s['price'],
                'change_percent': s['change_percent'],
                'sector': s['sector'],
                'technical': {
                    'signal': tech_signal['signal'],
                    'strength': tech_signal['strength'],
                    'rsi': rsi_val,
                },
                'fundamental': {
                    'signal': fund_signal['signal'],
                    'strength': fund_signal['strength'],
                    'pe_ratio': pe_ratio,
                    'pbv': pbv,
                },
                'overall_signal': overall['signal'],
                'overall_strength': overall['strength'],
            }
        except Exception as exc:
            logger.error('Batch analysis failed for %s: %s', s['symbol'], exc)
            errors.append(s['symbol'])
            return None

    tasks = [_analyze_one(s) for s in stocks]
    outcomes = await asyncio.gather(*tasks)

    for result in outcomes:
        if result is not None:
            results.append(result)

    # Sort by overall strength descending (best recommendations first)
    results.sort(key=lambda x: x.get('overall_strength', 0), reverse=True)

    if errors:
        logger.warning('Batch endpoint: %d stocks failed analysis: %s', len(errors), errors)

    return _sanitize_stock_dict({'stocks': results, 'updated_at': updated_at})


@app.get('/api/live/summary')
async def live_summary():
    """
    Super lightweight endpoint — returns just prices + signals for all stocks.
    Sorted by overall strength descending. Should complete in < 5 seconds.
    """
    stocks = get_top_stocks()
    updated_at = _now_iso()

    async def _analyze_one(s):
        try:
            symbol_full = s['symbol']
            if not symbol_full.endswith('.JK'):
                symbol_full = symbol_full + '.JK'
            df = await _fetch_stock_data_with_retry(get_stock_history, symbol_full, '3mo', fallback_symb=symbol_full)
            info = await _fetch_stock_data_with_retry(get_stock_info, symbol_full, fallback_symb=symbol_full)

            tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
            fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

            if df is not None and not df.empty:
                tech_signal = _apply_learning_signal(df, s)
            if info:
                fund_signal = generate_fundamental_signal(info)

            overall = combine_signals(tech_signal, fund_signal, df=df)

            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'price': s['price'],
                'change_percent': s['change_percent'],
                'overall_signal': overall['signal'],
                'overall_strength': overall['strength'],
            }
        except Exception as exc:
            logger.warning('Live summary failed for %s: %s', s['symbol'], exc)
            return {
                'symbol': s['symbol'].replace('.JK', ''),
                'price': s['price'],
                'change_percent': s['change_percent'],
                'overall_signal': 'NEUTRAL',
                'overall_strength': 50,
            }

    tasks = [_analyze_one(s) for s in stocks]
    outcomes = await asyncio.gather(*tasks)
    results = [r for r in outcomes if r is not None]

    # Sort by overall strength descending
    results.sort(key=lambda x: x.get('overall_strength', 0), reverse=True)

    # Market data (IHSG)
    ihsg_price = None
    ihsg_change = 0.0
    try:
        ihsg = yf.Ticker('^JKSE')
        info_ihsg = ihsg.info
        history_ihsg = ihsg.history(period='2d')
        ihsg_price = info_ihsg.get('currentPrice') or info_ihsg.get('regularMarketPrice')
        if ihsg_price is None and not history_ihsg.empty:
            ihsg_price = float(history_ihsg['Close'].iloc[-1])
        prev_close = info_ihsg.get('previousClose')
        if prev_close is None and len(history_ihsg) >= 2:
            prev_close = float(history_ihsg['Close'].iloc[-2])
        if ihsg_price and prev_close:
            ihsg_change = round(((ihsg_price - prev_close) / prev_close) * 100, 2)
    except Exception as exc:
        logger.error('Failed to fetch IHSG for live summary: %s', exc)

    return _sanitize_stock_dict({
        'stocks': results,
        'market': {
            'ihsg_price': ihsg_price,
            'ihsg_change': ihsg_change,
        },
        'updated_at': updated_at,
    })


@app.get('/api/stocks/{symbol}')
async def stock_detail(symbol: str):
    """
    Return detailed analysis for a single stock.
    """
    sym = _ensure_symbol(symbol)

    try:
        info, df = await asyncio.gather(
            _fetch_stock_data_with_retry(get_stock_info, sym, timeout=6, fallback_symb=sym),
            _fetch_stock_data_with_retry(get_stock_history, sym, '6mo', timeout=7, fallback_symb=sym),
        )
        info = info or {}
        df = df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.error('stock_detail failed for %s: %s', symbol, e)
        raise HTTPException(status_code=404, detail=f'Saham {symbol} tidak ditemukan')

    if df.empty:
        raise HTTPException(status_code=404, detail=f'Data historis untuk {symbol} tidak tersedia')

    # ── Prices ──
    close = df['close']
    high = df['high']
    low = df['low']
    latest_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
    change = round(latest_close - prev_close, 2)
    change_percent = round((change / prev_close) * 100, 2) if prev_close else 0.0

    # ── Technical Analysis ──
    rsi_series = calc_rsi(close)
    macd_line, macd_signal, macd_hist = calc_macd(close)
    sma20 = calc_sma(close, 20) if len(close) >= 20 else pd.Series([None])
    sma50 = calc_sma(close, 50) if len(close) >= 50 else pd.Series([None])
    upper_bb, middle_bb, lower_bb = calc_bollinger(close) if len(close) >= 20 else (pd.Series([None]), pd.Series([None]), pd.Series([None]))

    recent_volume = int(df['volume'].iloc[-1]) if not df.empty and 'volume' in df.columns else 0
    tech_signal = _apply_learning_signal(df, {'symbol': sym, 'price': latest_close, 'volume': recent_volume, 'avg_volume': int(df['volume'].tail(20).mean()) if 'volume' in df.columns else 0})

    # ── Volume Threshold Check ──
    if recent_volume < VOLUME_THRESHOLD:
        tech_signal['reasons'].append('Volume rendah — sinyal kurang reliable')
        tech_signal['strength'] = max(1, tech_signal['strength'] - 10)
        # Recalculate signal after strength adjustment
        if tech_signal['strength'] >= 65:
            tech_signal['signal'] = 'BUY'
        elif tech_signal['strength'] <= 35:
            tech_signal['signal'] = 'SELL'
        else:
            tech_signal['signal'] = 'NEUTRAL'

    # ── Fundamental Analysis ──
    fundamentals = analyze_fundamentals(info)
    fund_signal = generate_fundamental_signal(info)

    # ── Combined signal ──
    overall = combine_signals(tech_signal, fund_signal, df=df)
    # news sentiment: fetch if cached, else background non-blocking. Use short timeout for detail not to stall.
    news_sentiment = None
    cache_key_news = f'news:{sym}:6'
    cached_news = _news_cache.get(cache_key_news)
    if cached_news and (time.time() - cached_news['timestamp']) < 1800:
        news_sentiment = cached_news['data']
        overall = _apply_news_bias(overall, news_sentiment)
    else:
        try:
            ns = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _fetch_news_for_symbol, sym, 6),
                timeout=5.0
            )
            if ns:
                news_sentiment = ns
                _news_cache[cache_key_news] = {'data': ns, 'timestamp': time.time()}
                overall = _apply_news_bias(overall, ns)
        except (asyncio.TimeoutError, Exception) as _:
            pass
    volatility_pct = round(float(close.pct_change().tail(20).std() * 100), 2) if len(close) >= 20 else None
    trade_plan = _make_trade_plan(symbol.upper().replace('.JK', ''), latest_close, overall['signal'], overall['strength'], volatility_pct)
    daily_check = _daily_check_from_plan(latest_close, trade_plan)

    def _decision_copy(signal: str) -> Dict[str, Any]:
        label = 'HOLD' if signal == 'NEUTRAL' else signal
        if signal == 'BUY':
            headline = f"Layak BUY hari ini karena momentum teknikal dan risk/reward 7 hari masih menarik. Kekuatan {overall['strength']}/100."
        elif signal == 'SELL':
            headline = f"Layak SELL / hindari entry hari ini karena tekanan harga atau risiko turun masih dominan. Kekuatan {overall['strength']}/100."
        else:
            headline = f"Layak HOLD / tunggu dulu. Belum ada edge cukup kuat untuk BUY atau SELL. Kekuatan {overall['strength']}/100."
        drivers = []

        def _safe_metric(val):
            return None if (val is None or (isinstance(val, float) and pd.isna(val))) else round(float(val), 2)
        rsi_now = _safe_metric(rsi_series.iloc[-1])
        sma20_now = _safe_metric(sma20.iloc[-1])
        sma50_now = _safe_metric(sma50.iloc[-1])
        if rsi_now is not None:
            drivers.append(f'RSI 14 di {rsi_now}: ' + ('oversold, peluang rebound tapi tetap tunggu konfirmasi' if rsi_now < 30 else 'overbought, rawan koreksi' if rsi_now > 70 else 'zona normal'))
        if sma20_now and latest_close >= sma20_now:
            drivers.append('Harga di atas SMA 20: momentum pendek masih positif')
        elif sma20_now:
            drivers.append('Harga di bawah SMA 20: momentum pendek masih lemah')
        if sma50_now and latest_close >= sma50_now:
            drivers.append('Harga di atas SMA 50: tren menengah mendukung')
        elif sma50_now:
            drivers.append('Harga di bawah SMA 50: tren menengah belum kuat')
        if recent_volume < VOLUME_THRESHOLD:
            drivers.append('Volume di bawah 10.000: sinyal diturunkan karena likuiditas rendah')
        else:
            drivers.append('Volume memenuhi batas likuiditas minimum')
        risks = []
        if volatility_pct and volatility_pct >= 6:
            risks.append(f'Volatilitas tinggi {volatility_pct}%: gunakan posisi kecil dan disiplin stop loss')
        if fund_signal.get('signal') == 'SELL':
            risks.append('Fundamental memberi tekanan, jangan agresif walau teknikal membaik')
        if not risks:
            risks.append('Risiko utama: perubahan harga mendadak dan data pasar tertunda dari sumber eksternal')
        return {'label': label, 'headline': headline, 'key_drivers': drivers[:5], 'risk_notes': risks[:4]}

    decision = _decision_copy(overall['signal'])

    name = info.get('longName', info.get('shortName', symbol.replace('.JK', '')))
    _record_recommendation({
        'symbol': sym,
        'name': name,
        'price': latest_close,
        'volume': recent_volume,
        'avg_volume': int(df['volume'].tail(20).mean()) if 'volume' in df.columns else 0,
        'potential_score': 0,
    }, overall)
    sector = SECTOR_MAP.get(sym, info.get('sector', 'Lainnya'))
    industry = info.get('industry', None)
    market_cap = info.get('marketCap')

    def _safe(val):
        if val is None:
            return None
        try:
            f = float(val)
        except (TypeError, ValueError):
            return None
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)

    payload = {
        'symbol': symbol.upper().replace('.JK', ''),
        'name': name,
        'price': _safe(latest_close),
        'change': _safe(change),
        'change_percent': _safe(change_percent),
        'sector': sector,
        'industry': industry,
        'market_cap': _safe(market_cap) if market_cap is not None else None,
        'technical': {
            'rsi': _safe(rsi_series.iloc[-1]),
            'macd_line': _safe(macd_line.iloc[-1]),
            'macd_signal': _safe(macd_signal.iloc[-1]),
            'macd_histogram': _safe(macd_hist.iloc[-1]),
            'sma_20': _safe(sma20.iloc[-1]),
            'sma_50': _safe(sma50.iloc[-1]),
            'bollinger_upper': _safe(upper_bb.iloc[-1]),
            'bollinger_middle': _safe(middle_bb.iloc[-1]),
            'bollinger_lower': _safe(lower_bb.iloc[-1]),
            'signal': tech_signal['signal'],
            'strength': tech_signal['strength'],
            'reasons': tech_signal['reasons'],
        },
        'fundamental': {
            'pe_ratio': _safe(fundamentals.get('pe_ratio')),
            'pbv': _safe(fundamentals.get('pbv')),
            'dividend_yield': _safe(fundamentals.get('dividend_yield')),
            'eps': _safe(fundamentals.get('eps')),
            'market_cap': _safe(fundamentals.get('market_cap')),
            'high_52w': _safe(fundamentals.get('high_52w')),
            'low_52w': _safe(fundamentals.get('low_52w')),
            'signal': fund_signal['signal'],
            'strength': fund_signal['strength'],
            'reasons': fund_signal['reasons'],
        },
        'overall_signal': overall['signal'],
        'overall_label': decision['label'],
        'overall_strength': overall['strength'],
        'overall_reasons': overall['reasons'],
        'decision_summary': decision['headline'],
        'key_drivers': decision['key_drivers'],
        'risk_notes': decision['risk_notes'],
        'trade_plan': _sanitize_stock_dict(trade_plan) if isinstance(trade_plan, dict) else trade_plan,
        'daily_check': _sanitize_stock_dict(daily_check) if isinstance(daily_check, dict) else daily_check,
        'news_sentiment': _sanitize_stock_dict(news_sentiment) if isinstance(news_sentiment, dict) else news_sentiment,
        'volatility_pct': _safe(volatility_pct),
        'updated_at': _now_iso(),
    }
    return _sanitize_stock_dict(payload)


@app.get('/api/stocks/{symbol}/history')
async def stock_history(symbol: str, period: str = '6mo'):
    """
    Return OHLCV chart data for a stock.
    Falls back progressively when short periods return empty:
    1d -> 5d -> 1mo -> 3mo -> 6mo.
    """
    sym = _ensure_symbol(symbol)
    period = period.lower()
    # Normalize short period aliases
    period_map = {'1m': '1mo', '3m': '3mo'}
    period = period_map.get(period, period)
    original_period = period

    # Progressive fallback chain
    FALLBACK_CHAIN = ['1d', '5d', '1mo', '3mo', '6mo']

    df = pd.DataFrame()
    tried_periods = []

    for p in [period] + FALLBACK_CHAIN:
        if p in tried_periods:
            continue
        tried_periods.append(p)
        try:
            df = get_stock_history(sym, period=p)
            if not df.empty:
                period = p
                logger.info('History for %s: found data with period=%s', sym, p)
                break
            logger.warning('History for %s: empty data with period=%s, trying longer...', sym, p)
        except Exception as exc:
            logger.warning('History for %s: error with period=%s: %s', sym, p, exc)
            continue

    if df.empty:
        logger.error('History for %s: no data found after trying periods %s', sym, tried_periods)
        raise HTTPException(status_code=404, detail=f'Tidak ada data untuk {symbol} dengan periode {original_period}')

    dates = [d.strftime('%Y-%m-%d') for d in df.index]
    opens = [round(float(v), 2) for v in df['open']]
    highs = [round(float(v), 2) for v in df['high']]
    lows = [round(float(v), 2) for v in df['low']]
    closes = [round(float(v), 2) for v in df['close']]
    volumes = [int(v) for v in df['volume']]

    payload = {
        'symbol': symbol.upper().replace('.JK', ''),
        'period': period,
        'dates': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
        'updated_at': _now_iso(),
    }
    return _sanitize_stock_dict(payload)


@app.get('/api/stocks/{symbol}/signals')
async def stock_signals(symbol: str):
    """
    Lightweight endpoint returning just technical + fundamental signals summary.
    Faster than full detail endpoint.
    """
    sym = _ensure_symbol(symbol)

    try:
        info = get_stock_info(sym)
        df = get_stock_history(sym, period='6mo')
    except Exception as e:
        raise HTTPException(status_code=404, detail=f'Saham {symbol} tidak ditemukan')

    tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
    fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    if not df.empty:
        tech_signal = _apply_learning_signal(df, {'symbol': sym, 'price': float(df['close'].iloc[-1]) if not df.empty else 0, 'volume': int(df['volume'].iloc[-1]) if not df.empty and 'volume' in df.columns else 0})
    if info:
        fund_signal = generate_fundamental_signal(info)

    overall = combine_signals(tech_signal, fund_signal, df=df)

    return _sanitize_stock_dict({
        'symbol': symbol.upper().replace('.JK', ''),
        'overall_signal': overall['signal'],
        'overall_strength': overall['strength'],
        'technical': {
            'signal': tech_signal['signal'],
            'strength': tech_signal['strength'],
        },
        'fundamental': {
            'signal': fund_signal['signal'],
            'strength': fund_signal['strength'],
        },
        'updated_at': _now_iso(),
    })


@app.get('/api/stocks/{symbol}/news')
async def stock_news(symbol: str, limit: int = 8):
    return _fetch_news_for_symbol(symbol, max(1, min(20, int(limit or 8))))


@app.get('/api/stocks/{symbol}/recommendation-history')
async def stock_recommendation_history(symbol: str, limit: int = 20):
    sym = symbol.upper().replace('.JK', '')
    with _db_conn() as conn:
        rows = conn.execute(
            """SELECT symbol, recommendation, strength, price, future_price, return_pct, outcome, is_correct, created_at, evaluated_at
               FROM signal_recommendations
               WHERE REPLACE(symbol, '.JK', '') = ?
               ORDER BY id DESC
               LIMIT ?""",
            (sym, limit),
        ).fetchall()
    return {'symbol': sym, 'history': [dict(r) for r in rows], 'updated_at': _now_iso()}
