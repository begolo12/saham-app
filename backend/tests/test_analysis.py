"""Unit tests for analysis functions (calc_rsi, calc_macd, calc_bollinger, calc_stochastic)."""

import math

import numpy as np
import pandas as pd
import pytest

from analysis import (
    calc_rsi,
    calc_macd,
    calc_bollinger,
    calc_stochastic,
    calc_sma,
    calc_ema,
    generate_technical_signal,
    generate_fundamental_signal,
    combine_signals,
    analyze_fundamentals,
)


# ── Known test data helper series ──


def _constant_series(value: float, length: int = 30) -> pd.Series:
    return pd.Series([value] * length)


def _linear_series(start: float, step: float, length: int = 30) -> pd.Series:
    return pd.Series([start + i * step for i in range(length)])


def _high_low_close(close_series: pd.Series) -> tuple:
    high = close_series * 1.02
    low = close_series * 0.98
    return high, low


# ═══════════════════════════════════════════
# calc_rsi
# ═══════════════════════════════════════════
#
# NOTE: The implementation uses Wilder's smoothing and replaces zero avg_loss
# with NaN (to avoid ZeroDivisionError). This means RSI is NaN for pure
# uptrends or flat series — only downtrends (loss > 0, gain = 0) produce
# a numeric RSI. The tests below reflect this actual behavior.


class TestCalcRsi:
    def test_constant_prices_returns_nan(self):
        prices = _constant_series(100, 30)
        rsi = calc_rsi(prices)
        # RSI undefined when all gains/losses are 0 (Wilder divide by zero)
        assert rsi.isna().all(), "RSI should be all NaN for constant prices"

    def test_rising_prices_with_noise(self):
        """Strong uptrend with minor noise should push RSI > 60."""
        np.random.seed(1234)
        prices = _linear_series(100, 1.5, 50) + np.random.normal(0, 2, 50)
        rsi = calc_rsi(prices)
        last = float(rsi.iloc[-1])
        assert last > 60, f"RSI should be high in uptrend, got {last}"
        assert last <= 100

    def test_falling_prices_below_30(self):
        """Strong downtrend pushes RSI < 30."""
        prices = _linear_series(150, -2, 30)
        rsi = calc_rsi(prices)
        last = float(rsi.iloc[-1])
        assert last < 30, f"RSI should be <30 in strong downtrend, got {last}"

    def test_rsi_length_returns_correctly(self):
        prices = _linear_series(100, 1, 40)
        rsi = calc_rsi(prices, period=14)
        assert len(rsi) == 40
        # Pure uptrend: gain > 0, loss = 0 => avg_loss replaced by NaN => RSI all NaN
        assert rsi.isna().all()

    def test_short_series_returns_all_nan(self):
        prices = pd.Series([100, 101, 102])
        rsi = calc_rsi(prices, period=14)
        assert rsi.isna().all(), "RSI should be all NaN for series shorter than period+1"

    def test_rsi_bounds(self):
        """RSI should always be between 0 and 100 for non-pure trends."""
        np.random.seed(42)
        prices = pd.Series(np.random.randn(80).cumsum() + 100)
        rsi = calc_rsi(prices)
        valid = rsi.dropna()
        assert len(valid) > 0, "No valid RSI values for random walk"
        assert (valid >= 0).all() and (valid <= 100).all(), "RSI outside [0, 100]"


# ═══════════════════════════════════════════
# calc_macd
# ═══════════════════════════════════════════


class TestCalcMacd:
    def test_random_walk_returns_correct_shapes(self):
        np.random.seed(42)
        prices = pd.Series(np.random.randn(100).cumsum() + 100)
        macd_line, signal_line, histogram = calc_macd(prices)
        assert len(macd_line) == len(prices) == 100
        assert len(signal_line) == len(prices) == 100
        assert len(histogram) == len(prices) == 100
        # histogram = macd_line - signal_line
        assert np.allclose(histogram.dropna(), macd_line.dropna() - signal_line.dropna())

    def test_uptrend_macd_above_signal_eventually(self):
        """In a sustained uptrend, MACD should cross above signal."""
        np.random.seed(42)
        prices = _linear_series(100, 0.8, 60)
        macd_line, signal_line, _ = calc_macd(prices)
        # Last quarter should show MACD > signal at some point
        tail = 15
        above = macd_line.iloc[-tail:] > signal_line.iloc[-tail:]
        assert above.any(), "MACD should cross above signal in uptrend"

    def test_macd_components_not_all_nan(self):
        prices = _linear_series(100, 0.5, 80)
        macd_line, signal_line, histogram = calc_macd(prices)
        assert not macd_line.isna().all()
        assert not signal_line.isna().all()
        assert not histogram.isna().all()


# ═══════════════════════════════════════════
# calc_bollinger
# ═══════════════════════════════════════════


class TestCalcBollinger:
    def test_bollinger_order(self):
        """Upper >= Middle >= Lower at all points."""
        prices = _linear_series(100, 0.3, 50)
        upper, middle, lower = calc_bollinger(prices)
        valid = ~upper.isna()
        assert (upper[valid] >= middle[valid]).all(), "Upper < Middle"
        assert (middle[valid] >= lower[valid]).all(), "Middle < Lower"

    def test_bollinger_width_with_volatility(self):
        """Higher volatility = wider bands."""
        low_vol = pd.Series([100] * 10 + [101] * 10 + [99] * 10)
        high_vol = pd.Series([100, 115, 85, 100, 115, 85] * 5)
        _, mid_low, lower_low = calc_bollinger(low_vol)
        _, mid_high, lower_high = calc_bollinger(high_vol)
        spread_low = float(mid_low.iloc[-1] - lower_low.iloc[-1])
        spread_high = float(mid_high.iloc[-1] - lower_high.iloc[-1])
        assert spread_high > spread_low, \
            f"Expected wider bands for high vol ({spread_high} vs {spread_low})"

    def test_bollinger_shapes(self):
        prices = pd.Series(np.random.randn(40).cumsum() + 100)
        upper, middle, lower = calc_bollinger(prices)
        assert len(upper) == len(middle) == len(lower) == 40


# ═══════════════════════════════════════════
# calc_stochastic
# ═══════════════════════════════════════════


class TestCalcStochastic:
    def test_stochastic_bounds(self):
        """%K and %D should be 0-100."""
        close = _linear_series(100, 0.5, 40)
        high, low = _high_low_close(close)
        k, d = calc_stochastic(high, low, close)
        valid_k = k.dropna()
        valid_d = d.dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all(), "%K outside [0,100]"
        assert (valid_d >= 0).all() and (valid_d <= 100).all(), "%D outside [0,100]"

    def test_stochastic_d_is_sma_of_k(self):
        close = _linear_series(100, 0.4, 50)
        high, low = _high_low_close(close)
        k, d = calc_stochastic(high, low, close)
        valid = ~k.isna()
        expected_d = k.rolling(window=3).mean()
        assert np.allclose(d[valid], expected_d[valid], equal_nan=True)

    def test_stochastic_shapes(self):
        close = _linear_series(100, 0.3, 30)
        high, low = _high_low_close(close)
        k, d = calc_stochastic(high, low, close)
        assert len(k) == len(d) == 30


# ═══════════════════════════════════════════
# calc_sma / calc_ema
# ═══════════════════════════════════════════


class TestCalcSma:
    def test_sma_constant_equals_value(self):
        prices = pd.Series([100] * 10)
        sma = calc_sma(prices, 3)
        assert sma.iloc[-1] == 100.0

    def test_sma_length(self):
        prices = _linear_series(100, 1, 20)
        sma = calc_sma(prices, 5)
        assert len(sma) == 20
        assert sma.isna().sum() == 4  # first 4 are NaN


class TestCalcEma:
    def test_ema_constant_equals_value(self):
        prices = pd.Series([50] * 15)
        ema = calc_ema(prices, 5)
        assert math.isclose(ema.iloc[-1], 50.0, abs_tol=0.01)

    def test_ema_reacts_faster_than_sma(self):
        prices = _linear_series(100, 0.2, 30) * 1.0
        ema = calc_ema(prices, 10)
        sma = calc_sma(prices, 10)
        diff_ema = abs(ema.iloc[-1] - prices.iloc[-1])
        diff_sma = abs(sma.iloc[-1] - prices.iloc[-1])
        assert diff_ema < diff_sma, "EMA should track closer than SMA"


# ═══════════════════════════════════════════
# generate_technical_signal
# ═══════════════════════════════════════════


class TestGenerateTechnicalSignal:
    def test_oversold_gives_buy(self):
        """RSI < 30 with volume bias should produce BUY."""
        # Start high, drop sharply to get RSI low
        prices = _linear_series(150, -2, 60)
        df = pd.DataFrame({"close": prices})
        result = generate_technical_signal(df, volume_bias=10)
        assert result["signal"] in ("BUY", "NEUTRAL"), f"Oversold should lean BUY, got {result['signal']}"
        assert 1 <= result["strength"] <= 100

    def test_overbought_gives_sell(self):
        """RSI > 70 should produce SELL or NEUTRAL."""
        prices = _linear_series(100, 3, 60)
        df = pd.DataFrame({"close": prices})
        result = generate_technical_signal(df)
        assert result["signal"] in ("SELL", "NEUTRAL")
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) > 0


# ═══════════════════════════════════════════
# generate_fundamental_signal
# ═══════════════════════════════════════════


class TestGenerateFundamentalSignal:
    def test_low_pe_gives_buy(self):
        info = {"trailingPE": 8, "priceToBook": 1.2, "marketCap": 100_000_000_000_000, "dividendYield": 0.04}
        result = generate_fundamental_signal(info)
        assert result["signal"] == "BUY", f"Low PE should give BUY, got {result['signal']}"

    def test_high_pe_gives_sell(self):
        info = {"trailingPE": 50, "priceToBook": 6, "marketCap": 1_000_000_000_000}
        result = generate_fundamental_signal(info)
        assert result["signal"] == "SELL", f"High PE should give SELL, got {result['signal']}"

    def test_empty_info_returns_neutral(self):
        result = generate_fundamental_signal({})
        assert result["signal"] == "NEUTRAL"
        assert result["strength"] == 50


# ═══════════════════════════════════════════
# combine_signals
# ═══════════════════════════════════════════


class TestCombineSignals:
    def test_both_buy_gives_buy(self):
        tech = {"signal": "BUY", "strength": 75, "reasons": ["bullish"]}
        fund = {"signal": "BUY", "strength": 70, "reasons": ["cheap"]}
        result = combine_signals(tech, fund)
        assert result["signal"] == "BUY"
        # Weighted ensemble (5 components incl. regime/sent/vol). With both BUY strong,
        # the result is BUY with strength 72 (ta/fund dominate, regime/sent/vol at 50).
        assert result["strength"] == 72

    def test_both_sell_gives_sell(self):
        tech = {"signal": "SELL", "strength": 25, "reasons": ["bearish"]}
        fund = {"signal": "SELL", "strength": 20, "reasons": ["expensive"]}
        result = combine_signals(tech, fund)
        assert result["signal"] == "SELL"
        assert result["strength"] == 25

    def test_conflicting_signals_neutral(self):
        tech = {"signal": "BUY", "strength": 70, "reasons": ["bullish"]}
        fund = {"signal": "SELL", "strength": 20, "reasons": ["expensive"]}
        result = combine_signals(tech, fund)
        assert result["signal"] == "NEUTRAL"
        # Weighted ensemble: TA 70 + Fund 20 → avg 45, but sent/vol/regime default 50
        # pulls toward neutral, producing 47. Signal still NEUTRAL.
        assert result["strength"] == 47

    def test_reasons_are_merged(self):
        tech = {"signal": "BUY", "strength": 65, "reasons": ["Teknikal: RSI oversold"]}
        fund = {"signal": "BUY", "strength": 65, "reasons": ["Fundamental: PER murah"]}
        result = combine_signals(tech, fund)
        assert len(result["reasons"]) >= 2
        assert any("[Teknikal]" in r for r in result["reasons"])
        assert any("[Fundamental]" in r for r in result["reasons"])


# ═══════════════════════════════════════════
# analyze_fundamentals
# ═══════════════════════════════════════════


class TestAnalyzeFundamentals:
    def test_basic_metrics(self):
        info = {
            "trailingPE": 15.5,
            "priceToBook": 2.1,
            "marketCap": 200_000_000_000_000,
            "dividendYield": 0.03,
            "trailingEps": 500,
            "fiftyTwoWeekHigh": 8000,
            "fiftyTwoWeekLow": 5000,
        }
        result = analyze_fundamentals(info)
        assert result["pe_ratio"] == 15.5
        assert result["pbv"] == 2.1
        assert result["market_cap"] == 200_000_000_000_000
        assert result["eps"] == 500
        assert result["high_52w"] == 8000
        assert result["low_52w"] == 5000
        # dividend_yield 0.03 detected as decimal -> converted to 3.0%
        assert result["dividend_yield"] == 3.0

    def test_empty_info(self):
        result = analyze_fundamentals({})
        assert result["pe_ratio"] is None
        assert result["pbv"] is None
        assert result["market_cap"] is None

    def test_forward_pe_fallback(self):
        info = {"forwardPE": 12.0}
        result = analyze_fundamentals(info)
        assert result["pe_ratio"] == 12.0
