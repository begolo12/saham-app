import asyncio
import logging
import time
from typing import Optional, Dict, Any, List

import pandas as pd
import numpy as np

from analysis import (
    calc_rsi, calc_macd, calc_sma, calc_bollinger, analyze_fundamentals,
    generate_technical_signal, generate_fundamental_signal, combine_signals,
    calc_vwap, calc_atr, detect_market_regime, calc_sl_tp,
)
from stock_data import get_stock_history, get_stock_info, SECTOR_MAP
from services.db import (
    VOLUME_THRESHOLD, LIQUIDITY_TIER_100K, LIQUIDITY_TIER_1M, LIQUIDITY_TIER_5M,
    TRADE_HORIZON_DAYS, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    _now_iso, _learning_bias_for_symbol, _record_recommendation,
)
from services.stock_service import (
    _ensure_symbol, _fetch_stock_data_with_retry, _run_sync_with_timeout,
    _fetch_news_for_symbol, _apply_news_bias, _news_cache, _executor,
)

logger = logging.getLogger('saham-api')


# ── Stock bias / signal helpers ──

def _stock_bias(stock: Dict[str, Any]) -> Dict[str, float]:
    volume = float(stock.get('volume') or 0)
    avg_volume = float(stock.get('avg_volume') or 0)
    price = float(stock.get('price') or 0)
    potential = float(stock.get('potential_score') or 0)
    volume_bias = 0.0
    price_bias = 0.0
    # Tiered volume bias (new 10K baseline, finer granularity up to 5M)
    if volume >= LIQUIDITY_TIER_5M or avg_volume >= LIQUIDITY_TIER_5M:
        volume_bias += 8
    elif volume >= LIQUIDITY_TIER_1M or avg_volume >= LIQUIDITY_TIER_1M:
        volume_bias += 6
    elif volume >= LIQUIDITY_TIER_100K or avg_volume >= LIQUIDITY_TIER_100K:
        volume_bias += 4
    elif volume >= VOLUME_THRESHOLD or avg_volume >= VOLUME_THRESHOLD:
        volume_bias += 2
    else:
        volume_bias -= 8
    if 50 <= price < 200:
        price_bias += 2
    if potential >= 70:
        volume_bias += 3
    elif potential and potential < 45:
        volume_bias -= 5
    return {'volume_bias': volume_bias, 'price_bias': price_bias}


def _fast_list_signal(s: Dict[str, Any]) -> tuple:
    """Balanced list signal from lightweight technicals, not liquidity score alone."""
    change = float(s.get('change_percent') or 0)
    trend_5d = float(s.get('trend_5d') or 0)
    trend_20d = float(s.get('trend_20d') or 0)
    rsi = float(s.get('rsi14') or 50)
    volume_ratio = float(s.get('volume_ratio') or 1)
    volume = float(s.get('volume') or 0)
    avg_volume = float(s.get('avg_volume') or 0)

    strength = 50.0
    strength += max(-12, min(12, trend_5d * 1.6))
    strength += max(-10, min(10, trend_20d * 0.7))
    strength += 6 if change > 1 else -6 if change < -1 else 0
    strength += 5 if volume_ratio >= 1.3 else -4 if volume_ratio < 0.7 else 0

    if rsi < 30:
        strength += 10
    elif rsi > 75:
        strength -= 14
    elif rsi > 68:
        strength -= 7

    if volume < VOLUME_THRESHOLD and avg_volume < VOLUME_THRESHOLD:
        strength -= 10
    strength = max(1, min(100, round(strength)))

    if strength >= 60 and trend_5d > 2 and trend_20d > -8 and rsi < 70:
        signal = 'BUY'
    elif strength <= 38 or (trend_5d <= -5 and rsi > 35) or change <= -4 or rsi >= 78:
        signal = 'SELL'
    else:
        signal = 'NEUTRAL'
    return signal, strength


def _apply_learning_signal(df: pd.DataFrame, stock: Dict[str, Any]) -> Dict[str, Any]:
    bias = _stock_bias(stock)
    learning_bias = _learning_bias_for_symbol(stock.get('symbol', ''))
    signal = generate_technical_signal(
        df,
        volume_bias=bias['volume_bias'] + learning_bias,
        price_bias=bias['price_bias'],
    )
    if bias['volume_bias'] > 0:
        signal['reasons'].append('Volume/likuiditas mendukung — sinyal lebih dipercaya')
    elif bias['volume_bias'] < 0:
        signal['reasons'].append('Volume rendah — sinyal diturunkan')
    if learning_bias > 0:
        signal['reasons'].append(f'Learning historis positif (+{learning_bias:.1f}) untuk saham ini')
    elif learning_bias < 0:
        signal['reasons'].append(f'Learning historis negatif ({learning_bias:.1f}) untuk saham ini')
    return signal


def _fmt_action(signal: str) -> str:
    return 'BUY' if signal == 'BUY' else 'SELL' if signal == 'SELL' else 'WAIT'


def _make_trade_plan(symbol: str, price: float, signal: str, strength: float, volatility_pct: Optional[float] = None) -> Dict[str, Any]:
    vol = max(3.0, min(12.0, float(volatility_pct or 5.0)))
    action = _fmt_action(signal)
    if action == 'BUY':
        target_pct = max(4.0, min(12.0, 3.0 + (strength - 50) * 0.18 + vol * 0.25))
        stop_pct = min(-3.0, max(-8.0, -vol * 0.9))
        target_price = round(price * (1 + target_pct / 100), 2)
        stop_loss = round(price * (1 + stop_pct / 100), 2)
        instruction = f'BUY area Rp {price:,.0f}. Target jual 7 hari Rp {target_price:,.0f} (+{target_pct:.1f}%). Stop loss Rp {stop_loss:,.0f} ({stop_pct:.1f}%). Cek tiap hari.'
    elif action == 'SELL':
        target_pct = max(3.0, min(10.0, 2.5 + (50 - strength) * 0.15 + vol * 0.20))
        stop_pct = max(3.0, min(8.0, vol * 0.8))
        target_price = round(price * (1 - target_pct / 100), 2)
        stop_loss = round(price * (1 + stop_pct / 100), 2)
        instruction = f'SELL / hindari entry. Target turun 7 hari Rp {target_price:,.0f} (-{target_pct:.1f}%). Invalid jika naik ke Rp {stop_loss:,.0f} (+{stop_pct:.1f}%). Cek tiap hari.'
    else:
        target_price = round(price * 1.04, 2)
        stop_loss = round(price * 0.96, 2)
        instruction = f'WAIT. Belum ada edge kuat. Range pantau Rp {stop_loss:,.0f} - Rp {target_price:,.0f}. Cek tiap hari.'
    return {
        'action': action,
        'entry_price': round(float(price), 2),
        'target_price': target_price,
        'stop_loss': stop_loss,
        'horizon_days': TRADE_HORIZON_DAYS,
        'check_every': 'daily',
        'take_profit_pct': round(((target_price - price) / price) * 100, 2) if price else 0,
        'stop_loss_pct': round(((stop_loss - price) / price) * 100, 2) if price else 0,
        'instruction': instruction.replace(',', '.'),
        'confidence': 'tinggi' if strength >= 75 or strength <= 25 else 'sedang' if strength >= 62 or strength <= 38 else 'rendah',
    }


def _daily_check_from_plan(price: float, plan: Dict[str, Any]) -> Dict[str, Any]:
    action = plan.get('action')
    target = float(plan.get('target_price') or 0)
    stop = float(plan.get('stop_loss') or 0)
    if action == 'BUY':
        if target and price >= target:
            return {'status': 'TAKE_PROFIT', 'message': 'Target 7 hari kena. Realisasi profit / trailing stop.'}
        if stop and price <= stop:
            return {'status': 'STOP_LOSS', 'message': 'Stop loss kena. Cut loss, jangan averaging.'}
        return {'status': 'HOLD', 'message': 'Masih dalam rencana. Cek ulang besok.'}
    if action == 'SELL':
        if target and price <= target:
            return {'status': 'SELL_VALID', 'message': 'Sinyal jual valid, harga turun sesuai rencana.'}
        if stop and price >= stop:
            return {'status': 'SELL_INVALID', 'message': 'Sinyal jual invalid, harga tembus batas atas.'}
        return {'status': 'WAIT', 'message': 'Masih hindari entry sampai sinyal membaik.'}
    return {'status': 'WATCH', 'message': 'Belum entry. Tunggu sinyal lebih jelas.'}


# ── Full stock analysis ──

def _analyze_stock(s: dict) -> dict:
    """Analyze a single stock dict (from get_top_stocks) and return enriched data."""
    symbol_full = s['symbol']
    if not symbol_full.endswith('.JK'):
        symbol_full = symbol_full + '.JK'

    df = get_stock_history(symbol_full, period='3mo')
    info = get_stock_info(symbol_full)

    tech_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
    fund_signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}

    if not df.empty:
        tech_signal = _apply_learning_signal(df, s)
    if info:
        fund_signal = generate_fundamental_signal(info)

    overall = combine_signals(tech_signal, fund_signal, df=df, entry_price=float(s.get('price', 0)))

    # RSI from technical analysis
    rsi_val = None
    if not df.empty:
        rsi_series = calc_rsi(df['close'])
        rsi_val = round(float(rsi_series.iloc[-1]), 2) if not pd.isna(rsi_series.iloc[-1]) else None

    # Fundamental vals
    pe_ratio = None
    pbv = None
    if info:
        pe_ratio = round(info.get('trailingPE') or info.get('forwardPE') or 0, 2) if (info.get('trailingPE') or info.get('forwardPE')) else None
        pbv = round(info.get('priceToBook') or 0, 2) if info.get('priceToBook') else None

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


# ── Multi-timeframe & macro integration ──


def analyze_with_multitf(symbol: str, df: pd.DataFrame, info: dict,
                         s: dict) -> Dict[str, Any]:
    """Full analysis with multi-timeframe confirmation and macro bias.

    Runs the standard _analyze_stock flow, then enhances with:
      - Multi-timeframe signal agreement (daily/weekly/hourly)
      - Macro economic bias by sector
    """
    from services.multitf import fetch_multi_timeframe, analyze_multi_timeframe, multi_tf_signal

    result = _analyze_stock(s)
    sector = result.get('sector', 'Lainnya')

    # Multi-timeframe
    try:
        tf_data = fetch_multi_timeframe(s['symbol'])
        multi_tf = analyze_multi_timeframe(
            tf_data.get('daily'),
            tf_data.get('weekly'),
            tf_data.get('hourly'),
        )
        result['multi_timeframe'] = {
            'agreement': multi_tf['multi_tf_agreement'],
            'agreement_pct': multi_tf['agreement_pct'],
            'dominant_signal': multi_tf['dominant_signal'],
            'details': multi_tf['timeframe_details'],
        }
        # Adjust technical signal
        tech_signal = {
            'signal': result['technical']['signal'],
            'strength': result['technical']['strength'],
            'reasons': [],
        }
        adjusted_tech = multi_tf_signal(tech_signal, multi_tf)
        result['technical']['signal'] = adjusted_tech['signal']
        result['technical']['strength'] = adjusted_tech['strength']
        result['technical']['reasons'].extend(
            [r for r in adjusted_tech['reasons'] if r.startswith('✅') or r.startswith('⚠️') or r.startswith('❌')]
        )
    except Exception as exc:
        logger.debug('multitf failed for %s: %s', symbol, exc)
        result['multi_timeframe'] = None

    # Macro bias
    try:
        from services.macro import apply_macro_bias
        overall = {
            'signal': result['overall_signal'],
            'strength': result['overall_strength'],
            'reasons': [],
        }
        biased = apply_macro_bias(overall, sector)
        result['overall_signal'] = biased['signal']
        result['overall_strength'] = biased['strength']
        result['macro_bias'] = biased['reasons'][-3:] if biased['reasons'] else []
    except Exception as exc:
        logger.debug('macro bias failed for %s: %s', symbol, exc)
        result['macro_bias'] = []

    return result
