"""
Multi-Timeframe Analysis — check signal consistency across daily, weekly, hourly data.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

import pandas as pd
import yfinance as yf

from analysis import calc_rsi, calc_macd, calc_sma, calc_bollinger

logger = logging.getLogger('saham-api')


# ── Fetching ──


def fetch_multi_timeframe(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """Fetch daily, weekly, and hourly data for a symbol.

    Args:
        symbol: Full yfinance symbol (e.g. 'BBCA.JK')

    Returns:
        dict with keys 'daily', 'weekly', 'hourly'. Each value is a DataFrame
        or None on failure.
    """
    result: Dict[str, Optional[pd.DataFrame]] = {}
    try:
        ticker = yf.Ticker(symbol)
    except Exception as exc:
        logger.warning('multitf: failed to create ticker for %s: %s', symbol, exc)
        return {'daily': None, 'weekly': None, 'hourly': None}

    # Daily (3 months)
    try:
        df_daily = ticker.history(period='3mo', interval='1d', timeout=6)
        result['daily'] = df_daily if not df_daily.empty else None
    except Exception as exc:
        logger.debug('multitf daily fail %s: %s', symbol, exc)
        result['daily'] = None

    # Weekly (1 year)
    try:
        df_weekly = ticker.history(period='1y', interval='1wk', timeout=6)
        result['weekly'] = df_weekly if not df_weekly.empty else None
    except Exception as exc:
        logger.debug('multitf weekly fail %s: %s', symbol, exc)
        result['weekly'] = None

    # Hourly (7 days)
    try:
        df_hourly = ticker.history(period='7d', interval='1h', timeout=6)
        result['hourly'] = df_hourly if not df_hourly.empty else None
    except Exception as exc:
        logger.debug('multitf hourly fail %s: %s', symbol, exc)
        result['hourly'] = None

    return result


# ── Signal on each timeframe ──


def _signal_from_df(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate a simple BUY/SELL/NEUTRAL signal from a DataFrame.

    Uses RSI + SMA50/close comparison. Returns dict with signal, strength, reasons.
    """
    if df is None or df.empty:
        return {'signal': 'NEUTRAL', 'strength': 50, 'reasons': ['Data tidak tersedia']}

    close_col = 'Close' if 'Close' in df.columns else 'close'
    close = df[close_col]
    strength = 50
    reasons = []

    # RSI
    rsi_series = calc_rsi(pd.Series(close.values, name='close'))
    if rsi_series is not None and not rsi_series.isna().all():
        rsi_val = rsi_series.iloc[-1]
        if rsi_val < 35:
            reasons.append(f'RSI {rsi_val:.1f} — oversold')
            strength += 15
        elif rsi_val > 70:
            reasons.append(f'RSI {rsi_val:.1f} — overbought')
            strength -= 15

    # SMA50 position
    if len(close) >= 50:
        sma50 = calc_sma(pd.Series(close.values, name='close'), 50)
        if not sma50.isna().all():
            latest_close = close.iloc[-1]
            latest_sma50 = sma50.iloc[-1]
            if latest_close > latest_sma50 * 1.02:
                reasons.append('Harga di atas SMA50 — tren naik')
                strength += 10
            elif latest_close < latest_sma50 * 0.98:
                reasons.append('Harga di bawah SMA50 — tren turun')
                strength -= 10

    # MACD
    if len(close) >= 26:
        try:
            macd_line, signal_line, _ = calc_macd(pd.Series(close.values, name='close'))
            if len(macd_line) >= 2 and not macd_line.isna().all() and not signal_line.isna().all():
                macd_now = macd_line.iloc[-1]
                macd_prev = macd_line.iloc[-2]
                sig_now = signal_line.iloc[-1]
                sig_prev = signal_line.iloc[-2]
                if macd_prev <= sig_prev and macd_now > sig_now:
                    reasons.append('MACD golden cross')
                    strength += 10
                elif macd_prev >= sig_prev and macd_now < sig_now:
                    reasons.append('MACD death cross')
                    strength -= 10
        except Exception:
            pass

    # Trend from recent price action (5-period)
    if len(close) >= 5:
        pct_5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
        if pct_5 > 3:
            reasons.append(f'Naik {pct_5:.1f}% dalam 5 periode')
            strength += 5
        elif pct_5 < -3:
            reasons.append(f'Turun {pct_5:.1f}% dalam 5 periode')
            strength -= 5

    strength = max(1, min(100, strength))
    signal = 'BUY' if strength >= 65 else 'SELL' if strength <= 35 else 'NEUTRAL'
    return {'signal': signal, 'strength': strength, 'reasons': reasons}


# ── Multi-timeframe agreement ──


def analyze_multi_timeframe(
    df_daily: Optional[pd.DataFrame],
    df_weekly: Optional[pd.DataFrame],
    df_hourly: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    """Analyze signal consistency across timeframes.

    Returns:
        dict with:
          - multi_tf_agreement: 'high' | 'medium' | 'low'
          - adjusted_strength: int (1-100)
          - timeframe_details: list of per-timeframe signal dicts
          - agreement_pct: float 0.0-1.0
    """
    signals = {
        'daily': _signal_from_df(df_daily),
        'weekly': _signal_from_df(df_weekly),
        'hourly': _signal_from_df(df_hourly),
    }

    # Count how many agree on same direction (BUY, SELL, or NEUTRAL)
    daily_s = signals['daily']['signal']
    weekly_s = signals['weekly']['signal']
    hourly_s = signals['hourly']['signal']

    all_signals = [daily_s, weekly_s, hourly_s]
    valid_signals = [s for s in all_signals if s != 'NEUTRAL']
    total_valid = len(valid_signals)

    # Find the most common non-neutral signal
    if total_valid == 0:
        dominant = 'NEUTRAL'
        agreement_count = 0
    else:
        buy_count = all_signals.count('BUY')
        sell_count = all_signals.count('SELL')
        if buy_count >= sell_count:
            dominant = 'BUY'
            agreement_count = buy_count
        else:
            dominant = 'SELL'
            agreement_count = sell_count
        # If tie, use daily as tiebreaker
        if buy_count == sell_count and buy_count > 0:
            dominant = daily_s if daily_s != 'NEUTRAL' else weekly_s if weekly_s != 'NEUTRAL' else hourly_s

    # Agreement level
    # 3/3 agree → high, 2/3 → medium, 1/3 → low, 0/3 → neutral
    if agreement_count >= 3:
        agreement = 'high'
        agreement_pct = 1.0
    elif agreement_count == 2:
        agreement = 'medium'
        agreement_pct = 0.7
    elif agreement_count == 1:
        agreement = 'low'
        agreement_pct = 0.4
    else:
        agreement = 'none'
        agreement_pct = 0.0
        dominant = 'NEUTRAL'

    # Adjusted strength
    if dominant == 'NEUTRAL':
        adjusted_strength = 50
    elif dominant == 'BUY':
        # Base strength from daily signal, adjusted by agreement
        base = signals['daily']['strength']
        adjusted_strength = max(51, int(round(base * (0.6 + agreement_pct * 0.4))))
    else:  # SELL
        base = signals['daily']['strength']
        adjusted_strength = min(49, int(round(base * (0.6 + agreement_pct * 0.4))))

    adjusted_strength = max(1, min(100, adjusted_strength))

    return {
        'multi_tf_agreement': agreement,
        'agreement_pct': agreement_pct,
        'adjusted_strength': adjusted_strength,
        'dominant_signal': dominant,
        'timeframe_details': {
            'daily': signals['daily'],
            'weekly': signals['weekly'],
            'hourly': signals['hourly'],
        },
    }


def multi_tf_signal(technical_signal: Dict[str, Any],
                    multi_tf: Dict[str, Any]) -> Dict[str, Any]:
    """Downgrade/enhance a technical signal based on multi-timeframe agreement.

    Rules:
      - 3/3 same direction → full strength
      - 2/3 agree → 70% strength of original
      - 1/3 agree → 40% strength of original
      - 0/3 → NEUTRAL
    """
    result = dict(technical_signal)
    agreement = multi_tf.get('multi_tf_agreement', 'none')
    dominant = multi_tf.get('dominant_signal', 'NEUTRAL')
    orig_signal = technical_signal.get('signal', 'NEUTRAL')
    orig_strength = technical_signal.get('strength', 50)

    if agreement == 'high':
        # Full strength — add confidence
        result['reasons'] = list(technical_signal.get('reasons', []))
        result['reasons'].append('✅ Konfirmasi kuat: semua timeframe searah (3/3)')
        result['strength'] = max(1, min(100, orig_strength))
    elif agreement == 'medium':
        # 70% strength
        factor = 0.7
        result['strength'] = max(1, min(100, int(round(orig_strength * factor))))
        result['reasons'] = list(technical_signal.get('reasons', []))
        result['reasons'].append('⚠️ Konfirmasi sedang: 2/3 timeframe searah — sinyal dikurangi')
    elif agreement == 'low':
        # 40% strength
        factor = 0.4
        result['strength'] = max(1, min(100, int(round(orig_strength * factor))))
        result['reasons'] = list(technical_signal.get('reasons', []))
        result['reasons'].append('⚠️ Konfirmasi lemah: hanya 1/3 timeframe searah — sinyal diturunkan')
        # If dominant contradicts original, flip to NEUTRAL
        if dominant != orig_signal and dominant != 'NEUTRAL':
            result['signal'] = 'NEUTRAL'
            result['strength'] = 50
    else:
        # 0/3 → NEUTRAL
        result['signal'] = 'NEUTRAL'
        result['strength'] = 50
        result['reasons'] = list(technical_signal.get('reasons', []))
        result['reasons'].append('❌ Tidak ada konfirmasi antar timeframe — sinyal direset ke NEUTRAL')

    return result
