import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List


# ──────────────────────────────────────────────
# TECHNICAL ANALYSIS (manual, no pandas-ta)
# ──────────────────────────────────────────────

def calc_sma(prices: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return prices.rolling(window=period).mean()


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

    # ── Volume / price bias ──
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


def combine_signals(tech: Dict[str, Any], fund: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine technical and fundamental signals into one overall signal.
    Both signals weighted equally.
    """
    avg_strength = (tech['strength'] + fund['strength']) // 2
    avg_strength = max(1, min(100, avg_strength))

    reasons = []
    reasons.extend(['[Teknikal] ' + r for r in tech['reasons']])
    reasons.extend(['[Fundamental] ' + r for r in fund['reasons']])

    if avg_strength >= 65:
        overall_signal = 'BUY'
    elif avg_strength <= 35:
        overall_signal = 'SELL'
    else:
        overall_signal = 'NEUTRAL'

    return {
        'signal': overall_signal,
        'strength': avg_strength,
        'reasons': reasons,
    }
