import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional

__all__ = [
    # Technical indicators
    'calc_sma', 'calc_ema', 'calc_rsi', 'calc_macd',
    'calc_bollinger', 'calc_stochastic',
    'calc_vwap', 'calc_atr',
    # Volume / regime / risk
    'volume_confirmation', 'detect_market_regime', 'calc_sl_tp',
    # Fundamental
    'analyze_fundamentals',
    # Signal generation
    'generate_technical_signal', 'generate_fundamental_signal',
    'combine_signals',
    # New features (S8, S12)
    'correlation_analysis', 'detect_outlier',
]


# ──────────────────────────────────────────────
# TECHNICAL ANALYSIS (manual, no pandas-ta)
# ──────────────────────────────────────────────

def calc_sma(prices: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return prices.rolling(window=period).mean()


def calc_vwap(high: pd.Series, low: pd.Series, close: pd.Series,
              volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price.

    Standard formula: sum(typical_price * volume) / sum(volume).
    Typical price = (high + low + close) / 3.
    Returns a cumulative Series (expanding window).
    """
    typical_price = (high + low + close) / 3
    pv = typical_price * volume
    cum_pv = pv.expanding(min_periods=1).sum()
    cum_vol = volume.expanding(min_periods=1).sum()
    return cum_pv / cum_vol.replace(0, np.nan)


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series,
             period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing).

    TR = max(high - low, |high - prev_close|, |low - prev_close|).
    ATR = EMA of TR using Wilder's alpha = 1/period.
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # Wilder smoothed EMA
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def volume_confirmation(signal_strength: float,
                        current_volume: float,
                        avg_volume: float) -> float:
    """Adjust signal strength based on volume confirmation.

    - Volume < 70% of average → reduce strength by 15%.
    - Volume > 150% of average → boost strength by 10%.
    Returns adjusted strength (bounded to [1, 100]).
    """
    if avg_volume <= 0:
        return max(1.0, min(100.0, signal_strength))
    ratio = current_volume / avg_volume
    if ratio < 0.7:
        signal_strength *= 0.85
    elif ratio > 1.5:
        signal_strength *= 1.10
    return max(1.0, min(100.0, signal_strength))


def detect_market_regime(prices: pd.Series) -> Dict[str, Any]:
    """Simple market regime detection using SMA50 vs SMA200 cross.

    Returns dict with:
      - 'regime': 'trending_up' | 'trending_down' | 'ranging' | 'volatile'
      - 'confidence': float 0.0-1.0

    Volatility override: if current ATR(14) > 1.5 × ATR(50) average → 'volatile'.
    """
    regime = 'ranging'
    confidence = 0.5
    # Need at least 200 data points for SMA200
    if len(prices) >= 50:
        sma50 = calc_sma(prices, 50)
        if len(prices) >= 200:
            sma200 = calc_sma(prices, 200)
            latest_sma50 = sma50.iloc[-1]
            latest_sma200 = sma200.iloc[-1]
            if not np.isnan(latest_sma50) and not np.isnan(latest_sma200) and latest_sma200 > 0:
                diff_pct = ((latest_sma50 - latest_sma200) / latest_sma200) * 100
                if diff_pct > 2:
                    regime = 'trending_up'
                    confidence = min(1.0, 0.5 + diff_pct / 20)
                elif diff_pct < -2:
                    regime = 'trending_down'
                    confidence = min(1.0, 0.5 + abs(diff_pct) / 20)
                else:
                    regime = 'ranging'
                    confidence = 0.6
        else:
            # Fallback: use SMA50 vs last price
            latest_close = prices.iloc[-1]
            latest_sma50 = sma50.iloc[-1]
            if not np.isnan(latest_sma50) and latest_sma50 > 0:
                diff_pct = ((latest_close - latest_sma50) / latest_sma50) * 100
                if diff_pct > 3:
                    regime = 'trending_up'
                    confidence = 0.5
                elif diff_pct < -3:
                    regime = 'trending_down'
                    confidence = 0.5

    # Volatility check — override if market is extremely volatile
    if len(prices) >= 50:
        # We need high/low for ATR; approximate with close-only ATR proxy
        close_prices = prices
        close_prev = close_prices.shift(1)
        tr_proxy = pd.concat([
            (close_prices - close_prev).abs(),
        ], axis=1).max(axis=1)
        atr_current = tr_proxy.rolling(14).mean().iloc[-1]
        atr_avg = tr_proxy.rolling(50).mean().iloc[-1]
        if not np.isnan(atr_current) and not np.isnan(atr_avg) and atr_avg > 0:
            if atr_current > atr_avg * 1.5:
                regime = 'volatile'
                confidence = min(1.0, confidence + 0.2)
    elif len(prices) >= 20:
        # Rough check with limited data
        returns = prices.pct_change().dropna()
        recent_vol = returns.tail(10).std()
        long_vol = returns.std()
        if long_vol > 0 and recent_vol > long_vol * 1.5:
            regime = 'volatile'
            confidence = 0.5

    return {'regime': regime, 'confidence': round(confidence, 2)}


def calc_sl_tp(entry_price: float, atr_value: float,
               regime: str) -> Dict[str, Any]:
    """ATR-based stop-loss and take-profit levels.

    Rules:
      trending_up:  SL = entry - ATR*1.5,  TP = entry + ATR*3
      trending_down: SL = entry + ATR*1.5, TP = entry - ATR*3
      ranging:      SL = entry - ATR*1,   TP = entry + ATR*2
      volatile:     SL = entry - ATR*2,   TP = entry + ATR*4

    Ensures risk:reward >= 1:2 by widening TP if needed.
    """
    regime = regime.lower()
    if regime == 'trending_up':
        sl = entry_price - atr_value * 1.5
        tp = entry_price + atr_value * 3.0
    elif regime == 'trending_down':
        sl = entry_price + atr_value * 1.5
        tp = entry_price - atr_value * 3.0
    elif regime == 'volatile':
        sl = entry_price - atr_value * 2.0
        tp = entry_price + atr_value * 4.0
    else:  # ranging or unknown
        sl = entry_price - atr_value * 1.0
        tp = entry_price + atr_value * 2.0

    # Compute risk:reward ratio (absolute)
    risk = abs(entry_price - sl)
    reward = abs(tp - entry_price)
    rrr = round(reward / risk, 2) if risk > 0 else 0.0

    # Ensure risk:reward >= 1:2
    if regime in ('trending_up', 'ranging', 'volatile') and rrr < 2.0 and risk > 0:
        # Widen TP to achieve 1:2
        tp = entry_price + risk * 2.0
        rrr = 2.0
    elif regime == 'trending_down' and rrr < 2.0 and risk > 0:
        # For short trades, widen downside TP
        tp = entry_price - risk * 2.0
        rrr = 2.0

    return {
        'stop_loss': round(sl, 2),
        'take_profit': round(tp, 2),
        'risk_reward_ratio': round(rrr, 2),
    }


def calc_ema(prices: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average using pandas ewm."""
    return prices.ewm(span=period, adjust=False).mean()


def calc_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # First: simple moving average for initial values
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing for subsequent values
    for i in range(period + 1, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, Signal line, Histogram."""
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd_line = ema12 - ema26
    signal_line = calc_ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(prices: pd.Series, period: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Upper, Middle, Lower Bollinger Bands (2 standard deviations)."""
    middle = calc_sma(prices, period)
    std = prices.rolling(window=period).std()
    upper = middle + (2 * std)
    lower = middle - (2 * std)
    return upper, middle, lower


def calc_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                    k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
    """Stochastic Oscillator %K and %D."""
    low_min = low.rolling(window=k_period).min()
    high_max = high.rolling(window=k_period).max()
    denom = high_max - low_min
    # Replace zero and near-zero denominators with NaN to prevent division by zero
    denom = denom.replace(0, np.nan)
    denom[denom.abs() < 1e-10] = np.nan
    k = 100 * ((close - low_min) / denom)
    d = k.rolling(window=d_period).mean()
    return k, d


# ──────────────────────────────────────────────
# FUNDAMENTAL ANALYSIS
# ──────────────────────────────────────────────

def analyze_fundamentals(info: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key fundamental metrics from yfinance info dict."""
    pe = info.get('trailingPE') or info.get('forwardPE')
    pbv = info.get('priceToBook')
    market_cap = info.get('marketCap')
    dividend_yield = info.get('dividendYield')
    eps = info.get('trailingEps') or info.get('forwardEps')

    # Convert dividend yield — yfinance sometimes returns decimal (0.06)
    # and sometimes percentage (6.0). Auto-detect.
    if dividend_yield is not None:
        dy_pct = dividend_yield if dividend_yield > 1 else dividend_yield * 100
        dividend_yield = round(dy_pct, 2)

    # 52-week range
    high_52 = info.get('fiftyTwoWeekHigh')
    low_52 = info.get('fiftyTwoWeekLow')

    return {
        'pe_ratio': round(pe, 2) if pe and pe != 0 else None,
        'pbv': round(pbv, 2) if pbv else None,
        'market_cap': market_cap,
        'dividend_yield': dividend_yield,
        'eps': round(eps, 2) if eps else None,
        'high_52w': high_52,
        'low_52w': low_52,
    }


# ──────────────────────────────────────────────
# SIGNAL GENERATION
# ──────────────────────────────────────────────

def generate_technical_signal(df: pd.DataFrame, volume_bias: float = 0.0, price_bias: float = 0.0) -> Dict[str, Any]:
    """
    Generate technical trading signal based on RSI, MACD, SMA, Bollinger Bands.
    Returns signal, strength (1-100), and reasons in Bahasa Indonesia.
    """
    reasons = []
    strength = 50  # start neutral
    signal = 'NEUTRAL'

    close = df['close']
    latest_close = close.iloc[-1]

    # ── RSI ──
    rsi_series = calc_rsi(close)
    latest_rsi = rsi_series.iloc[-1]

    if not np.isnan(latest_rsi):
        if latest_rsi < 30:
            reasons.append('RSI rendah ({:.1f}) — Oversold, potensi reversal naik'.format(latest_rsi))
            strength += 20
        elif latest_rsi > 70:
            reasons.append('RSI tinggi ({:.1f}) — Overbought, potensi reversal turun'.format(latest_rsi))
            strength -= 20

    # ── MACD ──
    macd_line, signal_line, histogram = calc_macd(close)
    if len(macd_line) >= 2 and not np.isnan(macd_line.iloc[-1]) and not np.isnan(macd_line.iloc[-2]):
        macd_now = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        sig_now = signal_line.iloc[-1]
        sig_prev = signal_line.iloc[-2]

        # Golden cross: MACD crosses above signal
        if macd_prev <= sig_prev and macd_now > sig_now:
            reasons.append('MACD golden cross — momentum bullish')
            strength += 15
        # Death cross: MACD crosses below signal
        elif macd_prev >= sig_prev and macd_now < sig_now:
            reasons.append('MACD death cross — momentum bearish')
            strength -= 15

    # ── SMA 50 ──
    if len(close) >= 50:
        sma50 = calc_sma(close, 50)
        latest_sma50 = sma50.iloc[-1]
        if not np.isnan(latest_sma50):
            if latest_close > latest_sma50:
                reasons.append('Harga di atas SMA 50 — tren naik')
                strength += 10
            else:
                reasons.append('Harga di bawah SMA 50 — tren turun')
                strength -= 10

    # ── SMA 20 / Bollinger Bands ──
    if len(close) >= 20:
        sma20 = calc_sma(close, 20)
        upper, middle, lower = calc_bollinger(close)

        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_sma20 = sma20.iloc[-1]

        if not np.isnan(latest_lower) and latest_close <= latest_lower * 1.01:
            reasons.append('Menyentuh lower Bollinger — potensi bounce')
            strength += 10
        elif not np.isnan(latest_upper) and latest_close >= latest_upper * 0.99:
            reasons.append('Menyentuh upper Bollinger — potensi koreksi')
            strength -= 10

    # ── Volume confirmation filter (using actual volume data) ──
    volume_col = None
    for col in ('volume', 'Volume', 'vol'):
        if col in df.columns:
            volume_col = col
            break
    if volume_col is not None and df[volume_col].notna().sum() >= 20:
        current_volume = float(df[volume_col].iloc[-1])
        avg_volume = float(df[volume_col].tail(20).mean())
        raw_strength = strength  # save before volume bias
        strength = volume_confirmation(strength, current_volume, avg_volume)
        # Add reason if volume adjusted the signal
        vol_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        if vol_ratio < 0.7:
            reasons.append('Volume {}% dari rata-rata — konfirmasi lemah, sinyal diturunkan'.format(round(vol_ratio * 100)))
        elif vol_ratio > 1.5:
            reasons.append('Volume {}% dari rata-rata — volume kuat, sinyal dinaikkan'.format(round(vol_ratio * 100)))

    # ── Volume / price bias (from pre-computed stock-level metrics) ──
    strength += volume_bias
    strength += price_bias

    # ── Determine final signal from strength ──
    strength = max(1, min(100, strength))
    if strength >= 65:
        signal = 'BUY'
    elif strength <= 35:
        signal = 'SELL'
    else:
        signal = 'NEUTRAL'

    return {
        'signal': signal,
        'strength': strength,
        'reasons': reasons if reasons else ['Data teknis terbatas — tidak ada sinyal jelas'],
    }


def generate_fundamental_signal(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate fundamental trading signal based on valuation metrics.
    Returns signal, strength (1-100), and reasons in Bahasa Indonesia.
    """
    reasons = []
    strength = 50
    signal = 'NEUTRAL'

    # ── PE Ratio ──
    pe = info.get('trailingPE') or info.get('forwardPE')
    if pe and pe > 0:
        if pe < 15:
            reasons.append('PER {:.1f}x — valuasi murah'.format(pe))
            strength += 15
        elif pe > 30:
            reasons.append('PER {:.1f}x — valuasi mahal'.format(pe))
            strength -= 15
        else:
            reasons.append('PER {:.1f}x — valuasi wajar'.format(pe))

    # ── PBV ──
    pbv = info.get('priceToBook')
    if pbv and pbv > 0:
        if pbv < 2:
            reasons.append('PBV {:.1f}x — valuasi wajar'.format(pbv))
            strength += 10
        elif pbv > 5:
            reasons.append('PBV {:.1f}x — valuasi premium'.format(pbv))
            strength -= 10

    # ── Dividend Yield ──
    dy_raw = info.get('dividendYield')
    dy_pct = None
    if dy_raw and dy_raw > 0:
        # yfinance sometimes returns decimal (0.06) and sometimes percentage (6.0)
        dy_pct = dy_raw if dy_raw > 1 else dy_raw * 100
        if dy_pct > 3:
            reasons.append('Dividend yield {:.1f}% — dividen menarik'.format(dy_pct))
            strength += 10
        elif dy_pct > 1:
            reasons.append('Dividend yield {:.1f}% — dividen cukup'.format(dy_pct))

    # ── Market Cap ──
    market_cap = info.get('marketCap')
    if market_cap:
        if market_cap >= 50_000_000_000_000:  # 50T IDR ~ big cap
            reasons.append('Market cap besar ({:.0f}T) — blue chip stabil'.format(market_cap / 1e12))
            strength += 5
        elif market_cap >= 10_000_000_000_000:  # 10T IDR
            reasons.append('Market cap menengah ({:.0f}T) — cukup likuid'.format(market_cap / 1e12))

    # ── EPS Growth hint ──
    eps = info.get('trailingEps') or info.get('forwardEps')
    if eps and eps > 0:
        reasons.append('EPS positif ({:.2f}) — perusahaan profitable'.format(eps))
        strength += 5

    # ── Determine final signal ──
    strength = max(1, min(100, strength))
    if strength >= 65:
        signal = 'BUY'
    elif strength <= 35:
        signal = 'SELL'
    else:
        signal = 'NEUTRAL'

    return {
        'signal': signal,
        'strength': strength,
        'reasons': reasons if reasons else ['Data fundamental terbatas'],
    }


# ──────────────────────────────────────────────
# SECTOR CORRELATION ANALYSIS (S8)
# ──────────────────────────────────────────────

def correlation_analysis(symbol: str, all_stocks_data: List[Dict[str, Any]],
                         sector_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Analyse sector correlation for a symbol.

    Calculates sector average performance from all_stocks_data.
    If sector_trend is down >3% and individual stock signal is BUY,
    reduce strength by 15%. If sector_trend is up >3% and stock is SELL,
    reduce strength by 15%.

    Returns dict with sector_name, sector_avg_change, correlation_adjustment.
    """
    sector_name = 'Lainnya'
    if sector_map:
        sym_full = symbol if symbol.endswith('.JK') else symbol + '.JK'
        sector_name = sector_map.get(sym_full, 'Lainnya')

    # Compute sector average change from all_stocks_data
    sector_stocks = [s for s in all_stocks_data if s.get('sector') == sector_name]
    sector_changes = [float(s.get('change_percent', 0)) for s in sector_stocks if s.get('change_percent') is not None]
    sector_avg_change = round(sum(sector_changes) / len(sector_changes), 2) if sector_changes else 0.0

    correlation_adjustment = 0.0
    if sector_avg_change < -3:
        correlation_adjustment = -15.0  # sector down, reduce BUY strength
    elif sector_avg_change > 3:
        correlation_adjustment = -15.0  # sector up, reduce SELL strength

    return {
        'sector_name': sector_name,
        'sector_avg_change': sector_avg_change,
        'correlation_adjustment': correlation_adjustment,
    }


# ──────────────────────────────────────────────
# OUTLIER DETECTION (S12)
# ──────────────────────────────────────────────

def detect_outlier(signal_strength: float, historical_strengths: List[float],
                   symbol: str = '') -> Dict[str, Any]:
    """Detect if current signal is an outlier vs historical signals.

    - If current strength > 95 but rolling avg < 80 → flag, reduce to avg+10
    - If strength suddenly changes by >40 points from last signal → flag
    - S12b: also smooth over 3-day window — if last 3-day avg differs from
      current by >15 pts, blend 0.6*current + 0.4*avg, capped at ±20% of original.
    Returns adjusted_strength, outlier_flag, reason.
    """
    adjusted = float(signal_strength)
    outlier_flag = False
    reason = ''

    if not historical_strengths:
        return {'adjusted_strength': adjusted, 'outlier_flag': False, 'reason': ''}

    rolling_avg = sum(historical_strengths) / len(historical_strengths)

    # Rule 1: Current strength > 95 but rolling avg < 80
    if signal_strength > 95 and rolling_avg < 80:
        outlier_flag = True
        adjusted = rolling_avg + 10
        adjusted = max(1, min(100, adjusted))
        reason = f'Outlier: strength {signal_strength} >> rolling avg {rolling_avg:.1f}. Capped to avg+10 ({adjusted:.0f}).'
        # S12b: apply 3-day smoothing on top
        adjusted, smooth_reason = _smooth_over_3day(
            adjusted, historical_strengths, signal_strength,
        )
        if smooth_reason:
            reason = f'{reason} {smooth_reason}'
        return {'adjusted_strength': adjusted, 'outlier_flag': True, 'reason': reason}

    # Rule 2 (S12b): 3-day smoothing. If last 3 days avg differs from current
    # by >15 pts, blend 0.6*current + 0.4*avg3, cap adjustment to ±20% max.
    last_n = historical_strengths[-3:] if len(historical_strengths) >= 3 else list(historical_strengths)
    avg3 = sum(last_n) / len(last_n) if last_n else rolling_avg
    delta3 = abs(signal_strength - avg3)
    if delta3 > 15:
        outlier_flag = True
        adjusted, smooth_reason = _smooth_over_3day(
            signal_strength, historical_strengths, signal_strength,
        )
        reason = (
            f'Outlier: 3-day avg {avg3:.1f} differs from current {signal_strength:.0f} '
            f'by {delta3:.1f} pts. {smooth_reason or f"Smoothed to {adjusted:.0f}."}'
        )
        return {'adjusted_strength': adjusted, 'outlier_flag': True, 'reason': reason}

    return {'adjusted_strength': adjusted, 'outlier_flag': False, 'reason': ''}


def _smooth_over_3day(current_value: float, historical_strengths: List[float],
                      original_signal: float) -> Tuple[float, str]:
    """S12b: blend current value with 3-day average, capped at ±20% of original.

    Returns (new_value, reason_fragment).
    """
    if not historical_strengths:
        return current_value, ''

    last_n = historical_strengths[-3:] if len(historical_strengths) >= 3 else list(historical_strengths)
    avg3 = sum(last_n) / len(last_n)

    blended = 0.6 * current_value + 0.4 * avg3

    # Cap adjustment to ±20% of original signal
    max_cap = abs(original_signal) * 0.20
    adjustment = blended - current_value
    if abs(adjustment) > max_cap:
        sign = 1 if adjustment > 0 else -1
        blended = current_value + sign * max_cap

    # Bound to [1, 100]
    blended = max(1.0, min(100.0, blended))
    return blended, f'3-day smoothing (avg={avg3:.1f}) → {blended:.0f}.'


# ──────────────────────────────────────────────
# COMBINE SIGNALS — Weighted Ensemble (S2)
# ──────────────────────────────────────────────

def combine_signals(tech: Dict[str, Any], fund: Dict[str, Any],
                    df: Optional[pd.DataFrame] = None,
                    entry_price: Optional[float] = None,
                    symbol: str = '',
                    all_stocks_data: Optional[List[Dict[str, Any]]] = None,
                    sector_map: Optional[Dict[str, str]] = None,
                    historical_strengths: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Weighted ensemble signal combination (S2).

    Uses 5 components (TA, Fundamental, Sentiment, Volume, Regime) with
    dynamic weights adjusted by market regime. Reads per-symbol weights
    from signal_weights DB table (falls back to defaults).

    Also applies sector correlation (S8) and outlier detection (S12)
    when the extra parameters are provided.
    """
    # ── 1. Read default weights (lazy DB import to avoid circular dep) ──
    try:
        from services.db import _get_signal_weights
        weights = _get_signal_weights(symbol)
    except Exception:
        weights = {'ta_weight': 0.3, 'fund_weight': 0.3, 'sent_weight': 0.2,
                   'vol_weight': 0.1, 'regime_weight': 0.1}
    w_ta = float(weights.get('ta_weight', 0.3))
    w_fund = float(weights.get('fund_weight', 0.3))
    w_sent = float(weights.get('sent_weight', 0.2))
    w_vol = float(weights.get('vol_weight', 0.1))
    w_regime = float(weights.get('regime_weight', 0.1))

    # ── 2. Compute market regime (needed for both component scores & weight adj) ──
    regime_info: Dict[str, Any] = {'regime': 'ranging', 'confidence': 0.5}
    vwap_val = None
    atr_val = None
    regime_str = 'ranging'

    if df is not None and not df.empty:
        close = df['close'] if 'close' in df.columns else df.get('Close', pd.Series(dtype=float))
        high = df['high'] if 'high' in df.columns else df.get('High', pd.Series(dtype=float))
        low = df['low'] if 'low' in df.columns else df.get('Low', pd.Series(dtype=float))
        volume = df['volume'] if 'volume' in df.columns else df.get('Volume', pd.Series(dtype=float))

        regime_info = detect_market_regime(close)
        regime_str = regime_info['regime']

        # VWAP
        if not volume.empty and volume.notna().any():
            vwap_series = calc_vwap(high, low, close, volume)
            vwap_val = round(float(vwap_series.iloc[-1]), 2) if not pd.isna(vwap_series.iloc[-1]) else None

        # ATR
        if not high.empty and not low.empty:
            atr_series = calc_atr(high, low, close)
            atr_val = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else None

    # ── 3. Dynamic regime-based weight adjustment ──
    if regime_str == 'trending_up':
        w_ta += 0.10
        w_sent -= 0.05
    elif regime_str == 'volatile':
        w_regime += 0.10
    elif regime_str == 'ranging':
        w_fund += 0.10

    # Clamp to [0.05, 0.6]
    w_ta = max(0.05, min(0.6, w_ta))
    w_fund = max(0.05, min(0.6, w_fund))
    w_sent = max(0.05, min(0.6, w_sent))
    w_vol = max(0.05, min(0.6, w_vol))
    w_regime = max(0.05, min(0.6, w_regime))

    # Normalize to sum 1.0
    total_w = w_ta + w_fund + w_sent + w_vol + w_regime
    if total_w > 0:
        w_ta /= total_w
        w_fund /= total_w
        w_sent /= total_w
        w_vol /= total_w
        w_regime /= total_w

    weights_used = {
        'ta_weight': round(w_ta, 4),
        'fund_weight': round(w_fund, 4),
        'sent_weight': round(w_sent, 4),
        'vol_weight': round(w_vol, 4),
        'regime_weight': round(w_regime, 4),
    }

    # ── 4. Compute component scores (each 1-100) ──
    ta_score = float(tech.get('strength', 50))
    fund_score = float(fund.get('strength', 50))

    # Sentiment score — derived from tech/fund signal agreement
    tech_sig = tech.get('signal', 'NEUTRAL')
    fund_sig = fund.get('signal', 'NEUTRAL')
    sent_signals = []
    sent_signals.append(1 if tech_sig == 'BUY' else (-1 if tech_sig == 'SELL' else 0))
    sent_signals.append(1 if fund_sig == 'BUY' else (-1 if fund_sig == 'SELL' else 0))
    avg_sent = np.mean(sent_signals) if sent_signals else 0
    sent_score = 50 + avg_sent * 40  # -1→10, 0→50, +1→90
    sent_score = max(1, min(100, sent_score))

    # Volume score — from df or default neutral
    vol_score = 50.0
    vol_ratio = 1.0
    if df is not None and not df.empty:
        volume_col = None
        for col in ('volume', 'Volume', 'vol'):
            if col in df.columns:
                volume_col = col
                break
        if volume_col is not None and df[volume_col].notna().sum() >= 20:
            current_vol = float(df[volume_col].iloc[-1])
            avg_vol = float(df[volume_col].tail(20).mean())
            if avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                if vol_ratio > 1.5:
                    vol_score = 75
                elif vol_ratio < 0.7:
                    vol_score = 25
                else:
                    vol_score = 50

    # Regime score — bias based on regime
    regime_score = 50.0
    if regime_str == 'trending_up':
        regime_score = 70
    elif regime_str == 'trending_down':
        regime_score = 30
    elif regime_str == 'volatile':
        regime_score = 40  # cautious
    else:
        regime_score = 50

    # ── 5. Weighted ensemble ──
    ensemble = (
        w_ta * ta_score
        + w_fund * fund_score
        + w_sent * sent_score
        + w_vol * vol_score
        + w_regime * regime_score
    )
    avg_strength = max(1, min(100, round(ensemble)))

    # ── 6. Confidence level based on component agreement ──
    component_signals = [
        'BUY' if ta_score >= 65 else 'SELL' if ta_score <= 35 else 'NEUTRAL',
        'BUY' if fund_score >= 65 else 'SELL' if fund_score <= 35 else 'NEUTRAL',
        'BUY' if sent_score >= 65 else 'SELL' if sent_score <= 35 else 'NEUTRAL',
        'BUY' if vol_score >= 65 else 'SELL' if vol_score <= 35 else 'NEUTRAL',
        'BUY' if regime_score >= 65 else 'SELL' if regime_score <= 35 else 'NEUTRAL',
    ]

    if avg_strength >= 65:
        majority = 'BUY'
    elif avg_strength <= 35:
        majority = 'SELL'
    else:
        majority = 'NEUTRAL'

    agreeing = sum(1 for s in component_signals if s == majority)
    total_components = len(component_signals)
    agreement_pct = (agreeing / total_components) * 100
    strength_extremity = abs(avg_strength - 50) / 50  # 0-1
    confidence_level = min(100, round(
        agreement_pct * 0.6 + strength_extremity * 100 * 0.4
    ))

    # ── 7. Determine overall signal ──
    if avg_strength >= 65:
        overall_signal = 'BUY'
    elif avg_strength <= 35:
        overall_signal = 'SELL'
    else:
        overall_signal = 'NEUTRAL'

    reasons = []
    reasons.extend(['[Teknikal] ' + r for r in tech.get('reasons', [])])
    reasons.extend(['[Fundamental] ' + r for r in fund.get('reasons', [])])
    if vol_ratio < 0.7:
        reasons.append('[Volume] Volume {}% dari rata-rata — konfirmasi lemah'.format(round(vol_ratio * 100)))
    elif vol_ratio > 1.5:
        reasons.append('[Volume] Volume {}% dari rata-rata — strong'.format(round(vol_ratio * 100)))
    if regime_str:
        reasons.append('[Regime] Market {} (confidence {})'.format(regime_str, regime_info.get('confidence', 0.5)))
    reasons.append('[Ensemble] Bobot TA={:.0f}% Fund={:.0f}% Sent={:.0f}% Vol={:.0f}% Regime={:.0f}%'.format(
        w_ta * 100, w_fund * 100, w_sent * 100, w_vol * 100, w_regime * 100,
    ))

    result: Dict[str, Any] = {
        'signal': overall_signal,
        'strength': avg_strength,
        'reasons': reasons,
        'weights_used': weights_used,
        'confidence_level': confidence_level,
        'market_regime': regime_str,
        'regime_confidence': regime_info.get('confidence', 0.5),
    }

    # ── 8. Optional: VWAP, ATR, SL/TP ──
    if df is not None and not df.empty:
        result['vwap'] = vwap_val
        if atr_val is not None:
            result['atr'] = round(atr_val, 2) if atr_val else None
        else:
            result['atr'] = None

        ep = entry_price if entry_price is not None else float(df['close'].iloc[-1])
        if atr_val and atr_val > 0:
            sl_tp = calc_sl_tp(ep, atr_val, regime_str)
            result.update(sl_tp)  # stop_loss, take_profit, risk_reward_ratio
        else:
            result['stop_loss'] = None
            result['take_profit'] = None
            result['risk_reward_ratio'] = None

    # ── 9. Sector correlation adjustment (S8) ──
    if symbol and all_stocks_data is not None:
        corr = correlation_analysis(symbol, all_stocks_data, sector_map)
        result['sector_name'] = corr['sector_name']
        result['sector_avg_change'] = corr['sector_avg_change']
        result['correlation_adjustment'] = corr['correlation_adjustment']
        if corr['correlation_adjustment'] != 0:
            if (overall_signal == 'BUY' and corr['sector_avg_change'] < -3) or \
               (overall_signal == 'SELL' and corr['sector_avg_change'] > 3):
                result['strength'] = max(1, min(100, int(result['strength'] + corr['correlation_adjustment'])))
                result['reasons'].append(
                    'Sektor {} ({:+.1f}%) berlawanan arah — strength dikurangi {}%'.format(
                        corr['sector_name'], corr['sector_avg_change'],
                        abs(int(corr['correlation_adjustment'])),
                    )
                )
                # Re-evaluate signal after adjustment
                if result['strength'] >= 65:
                    result['signal'] = 'BUY'
                elif result['strength'] <= 35:
                    result['signal'] = 'SELL'
                else:
                    result['signal'] = 'NEUTRAL'

    # ── 10. Outlier detection (S12) ──
    if historical_strengths is not None:
        outlier_result = detect_outlier(float(result['strength']), historical_strengths)
        result['outlier_flag'] = outlier_result['outlier_flag']
        result['outlier_reason'] = outlier_result['reason']
        if outlier_result['outlier_flag']:
            result['strength'] = outlier_result['adjusted_strength']
            result['reasons'].append(outlier_result['reason'])
            # Re-evaluate signal after outlier adjustment
            if result['strength'] >= 65:
                result['signal'] = 'BUY'
            elif result['strength'] <= 35:
                result['signal'] = 'SELL'
            else:
                result['signal'] = 'NEUTRAL'

    return result
