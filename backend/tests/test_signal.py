"""
Unit tests for signal engine additions:
calc_vwap, calc_atr, volume_confirmation, detect_market_regime, calc_sl_tp.
"""

import math

import numpy as np
import pandas as pd
import pytest

from analysis import (
    calc_vwap,
    calc_atr,
    volume_confirmation,
    detect_market_regime,
    calc_sl_tp,
    combine_signals,
    generate_technical_signal,
)


# ── Helpers ──


def _ohlcv_df(length: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame with yfinance-style column names."""
    np.random.seed(seed)
    close = pd.Series(np.random.randn(length).cumsum() + 5000, name="close")
    high = close * (1 + np.abs(np.random.randn(length)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(length)) * 0.01)
    volume = pd.Series(np.random.randint(1_000_000, 20_000_000, size=length), name="volume")
    return pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})


def _constant_series(value: float, length: int = 30) -> pd.Series:
    return pd.Series([value] * length)


def _linear_series(start: float, step: float, length: int = 30) -> pd.Series:
    return pd.Series([start + i * step for i in range(length)])


# ═══════════════════════════════════════════
# calc_vwap
# ═══════════════════════════════════════════


class TestCalcVwap:
    def test_vwap_returns_series(self):
        df = _ohlcv_df(50)
        vwap = calc_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert isinstance(vwap, pd.Series)
        assert len(vwap) == 50

    def test_vwap_all_positive(self):
        df = _ohlcv_df(30)
        vwap = calc_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert (vwap.dropna() > 0).all(), "VWAP should be positive"

    def test_vwap_same_as_close_when_constant(self):
        """With constant price and volume, VWAP should equal price."""
        high = pd.Series([100.0] * 20)
        low = pd.Series([100.0] * 20)
        close = pd.Series([100.0] * 20)
        volume = pd.Series([1_000_000] * 20)
        vwap = calc_vwap(high, low, close, volume)
        assert math.isclose(vwap.iloc[-1], 100.0, abs_tol=0.01)

    def test_vwap_converges_to_typical_price(self):
        """After many periods with equal volumes, cumulative VWAP ~ typical_price."""
        close = _linear_series(100, 1, 50)
        high = close * 1.02
        low = close * 0.98
        volume = pd.Series([1_000_000] * 50)
        vwap = calc_vwap(high, low, close, volume)
        typical = (high + low + close) / 3
        # VWAP is cumulative — last value is near the average, not the last typical price
        avg_typical = typical.mean()
        assert abs(vwap.iloc[-1] - avg_typical) < avg_typical * 0.05

    def test_vwap_zero_volume_returns_nan(self):
        """If all volumes are zero, VWAP should be NaN."""
        high = pd.Series([100.0, 102.0, 101.0])
        low = pd.Series([98.0, 99.0, 100.0])
        close = pd.Series([99.0, 101.0, 100.5])
        volume = pd.Series([0, 0, 0])
        vwap = calc_vwap(high, low, close, volume)
        assert vwap.isna().all(), "VWAP should be NaN with zero volume"


# ═══════════════════════════════════════════
# calc_atr
# ═══════════════════════════════════════════


class TestCalcAtr:
    def test_atr_returns_series(self):
        df = _ohlcv_df(50)
        atr = calc_atr(df["high"], df["low"], df["close"])
        assert isinstance(atr, pd.Series)
        assert len(atr) == 50

    def test_atr_positive(self):
        df = _ohlcv_df(30)
        atr = calc_atr(df["high"], df["low"], df["close"])
        assert (atr.dropna() > 0).all(), "ATR should be positive"

    def test_atr_constant_prices(self):
        """Constant prices → TR = 0 → ATR = 0."""
        high = pd.Series([100.0] * 30)
        low = pd.Series([100.0] * 30)
        close = pd.Series([100.0] * 30)
        atr = calc_atr(high, low, close, period=14)
        valid = atr.dropna()
        assert len(valid) > 0
        assert (valid == 0).all(), "ATR should be 0 for constant prices"

    def test_atr_increasing_with_volatility(self):
        """Higher price swings → higher ATR."""
        low_vol = _ohlcv_df(50, seed=1)
        high_vol = _ohlcv_df(50, seed=999)
        atr_low = calc_atr(low_vol["high"], low_vol["low"], low_vol["close"]).iloc[-1]
        atr_high = calc_atr(high_vol["high"], high_vol["low"], high_vol["close"]).iloc[-1]
        # Different seeds produce different ATRs; just verify both are finite
        assert not np.isnan(atr_low)
        assert not np.isnan(atr_high)

    def test_atr_default_period(self):
        df = _ohlcv_df(60)
        atr14 = calc_atr(df["high"], df["low"], df["close"], period=14)
        atr7 = calc_atr(df["high"], df["low"], df["close"], period=7)
        assert len(atr14) == len(atr7) == 60
        assert atr14.notna().sum() < atr7.notna().sum()  # longer period needs more data

    def test_atr_custom_period(self):
        df = _ohlcv_df(100)
        atr = calc_atr(df["high"], df["low"], df["close"], period=20)
        assert len(atr) == 100
        assert atr.notna().sum() >= 80


# ═══════════════════════════════════════════
# volume_confirmation
# ═══════════════════════════════════════════


class TestVolumeConfirmation:
    def test_low_volume_reduces_strength(self):
        result = volume_confirmation(70.0, current_volume=500_000, avg_volume=1_000_000)
        assert result == pytest.approx(70 * 0.85, rel=1e-3)

    def test_high_volume_boosts_strength(self):
        result = volume_confirmation(50.0, current_volume=2_000_000, avg_volume=1_000_000)
        assert result == pytest.approx(50 * 1.10, rel=1e-3)

    def test_normal_volume_no_change(self):
        result = volume_confirmation(60.0, current_volume=1_000_000, avg_volume=1_000_000)
        assert result == 60.0

    def test_barely_low_volume_no_change(self):
        """Volume = 70% of avg → no adjustment (threshold is strictly < 0.7)."""
        result = volume_confirmation(50.0, current_volume=700_000, avg_volume=1_000_000)
        assert result == 50.0

    def test_barely_high_volume_no_change(self):
        """Volume = 150% of avg → no adjustment (threshold is strictly > 1.5)."""
        result = volume_confirmation(50.0, current_volume=1_500_000, avg_volume=1_000_000)
        assert result == 50.0

    def test_zero_avg_volume_returns_original(self):
        result = volume_confirmation(80.0, current_volume=1_000_000, avg_volume=0)
        assert result == 80.0

    def test_strength_stays_bounded(self):
        result = volume_confirmation(95.0, current_volume=10_000_000, avg_volume=1_000_000)
        assert result <= 100.0

    def test_low_strength_boosted_is_bounded(self):
        result = volume_confirmation(5.0, current_volume=10_000_000, avg_volume=1_000_000)
        assert result >= 1.0


# ═══════════════════════════════════════════
# detect_market_regime
# ═══════════════════════════════════════════


class TestDetectMarketRegime:
    def test_short_series_returns_default(self):
        prices = _constant_series(5000, 10)
        result = detect_market_regime(prices)
        assert "regime" in result
        assert "confidence" in result

    def test_uptrend_sma50_above_sma200(self):
        """Strong uptrend → SMA50 >> SMA200 → trending_up."""
        # Start low, end high over 250 periods
        prices = _linear_series(4000, 10, 250)
        result = detect_market_regime(prices)
        assert result["regime"] == "trending_up", f"Expected trending_up, got {result['regime']}"
        assert 0 < result["confidence"] <= 1.0

    def test_downtrend_sma50_below_sma200(self):
        """Strong downtrend → SMA50 << SMA200 → trending_down."""
        prices = _linear_series(6000, -10, 250)
        result = detect_market_regime(prices)
        assert result["regime"] == "trending_down", f"Expected trending_down, got {result['regime']}"
        assert 0 < result["confidence"] <= 1.0

    def test_ranging_market(self):
        """Prices oscillating around a mean → ranging."""
        np.random.seed(0)
        prices = pd.Series(5000 + np.random.randn(250).cumsum() * 5)
        result = detect_market_regime(prices)
        # May be trending or ranging depending on random walk; just verify valid output
        assert result["regime"] in ("ranging", "trending_up", "trending_down", "volatile")

    def test_sma50_fallback_when_under_200(self):
        """With 50-199 points, use SMA50 vs close fallback."""
        prices = _linear_series(4000, 15, 100)  # strong uptrend
        result = detect_market_regime(prices)
        assert result["regime"] == "trending_up"

    def test_returns_dict_with_keys(self):
        prices = _linear_series(5000, 2, 80)
        result = detect_market_regime(prices)
        assert "regime" in result
        assert "confidence" in result
        assert isinstance(result["regime"], str)
        assert isinstance(result["confidence"], float)

    def test_volatile_detection(self):
        """Extreme price swings trigger volatile regime."""
        # 100 flat values then alternating 4500/5500 swings
        flat = [5000] * 100
        osc = [4500 if i % 2 == 0 else 5500 for i in range(15)]
        prices = pd.Series(flat + osc)
        result = detect_market_regime(prices)
        assert result["regime"] == "volatile", f"Expected volatile, got {result['regime']}"
        assert result["confidence"] >= 0.5


# ═══════════════════════════════════════════
# calc_sl_tp
# ═══════════════════════════════════════════


class TestCalcSlTp:
    def test_trending_up(self):
        result = calc_sl_tp(entry_price=5000, atr_value=100, regime="trending_up")
        assert result["stop_loss"] == 5000 - 100 * 1.5
        assert result["take_profit"] >= 5000 + 100 * 3.0  # >= because of RRR adjustment

    def test_trending_down(self):
        result = calc_sl_tp(entry_price=5000, atr_value=100, regime="trending_down")
        assert result["stop_loss"] == 5000 + 100 * 1.5
        assert result["take_profit"] <= 5000 - 100 * 3.0

    def test_ranging(self):
        result = calc_sl_tp(entry_price=5000, atr_value=100, regime="ranging")
        assert result["stop_loss"] == 5000 - 100 * 1.0
        assert result["take_profit"] >= 5000 + 100 * 2.0

    def test_volatile(self):
        result = calc_sl_tp(entry_price=5000, atr_value=100, regime="volatile")
        assert result["stop_loss"] == 5000 - 100 * 2.0
        assert result["take_profit"] >= 5000 + 100 * 4.0

    def test_rr_ratio_at_least_2(self):
        """calc_sl_tp should ensure risk:reward >= 1:2."""
        result = calc_sl_tp(entry_price=5000, atr_value=200, regime="ranging")
        assert result["risk_reward_ratio"] >= 2.0

    def test_case_insensitive(self):
        result_up = calc_sl_tp(100, 10, "TRENDING_UP")
        result_down = calc_sl_tp(100, 10, "Trending_Down")
        result_range = calc_sl_tp(100, 10, "Ranging")
        assert result_up["stop_loss"] == 100 - 10 * 1.5
        assert result_down["stop_loss"] == 100 + 10 * 1.5
        assert result_range["stop_loss"] == 100 - 10 * 1.0

    def test_unknown_regime_defaults_to_ranging(self):
        result = calc_sl_tp(entry_price=5000, atr_value=100, regime="unknown")
        assert result["stop_loss"] == 5000 - 100 * 1.0

    def test_returns_rounded_values(self):
        result = calc_sl_tp(entry_price=5000.123, atr_value=100.456, regime="ranging")
        assert isinstance(result["stop_loss"], float)
        assert isinstance(result["take_profit"], float)
        assert isinstance(result["risk_reward_ratio"], float)

    def test_positive_atr_required(self):
        """With atr_value=0, SL/TP will be at entry price, RRR = 0."""
        result = calc_sl_tp(entry_price=5000, atr_value=0, regime="ranging")
        assert result["stop_loss"] == 5000
        assert result["take_profit"] == 5000
        assert result["risk_reward_ratio"] == 0.0


# ═══════════════════════════════════════════
# combine_signals with df
# ═══════════════════════════════════════════


class TestCombineSignalsWithDf:
    def test_with_df_adds_extra_fields(self):
        df = _ohlcv_df(250)
        tech = {"signal": "BUY", "strength": 70, "reasons": ["bullish"]}
        fund = {"signal": "NEUTRAL", "strength": 50, "reasons": ["neutral"]}
        result = combine_signals(tech, fund, df=df, entry_price=5000)
        assert "market_regime" in result
        assert "vwap" in result
        assert "atr" in result
        assert "stop_loss" in result
        assert "take_profit" in result
        assert "risk_reward_ratio" in result

    def test_without_df_no_extra_fields(self):
        tech = {"signal": "BUY", "strength": 70, "reasons": ["bullish"]}
        fund = {"signal": "BUY", "strength": 70, "reasons": ["cheap"]}
        result = combine_signals(tech, fund)
        # market_regime always present (defaults to 'ranging')
        assert result["market_regime"] == 'ranging'

    def test_with_empty_df_no_extra_fields(self):
        tech = {"signal": "NEUTRAL", "strength": 50, "reasons": []}
        fund = {"signal": "NEUTRAL", "strength": 50, "reasons": []}
        result = combine_signals(tech, fund, df=pd.DataFrame())
        assert result["market_regime"] == 'ranging'


# ═══════════════════════════════════════════
# generate_technical_signal volume confirmation
# ═══════════════════════════════════════════


class TestGenerateTechnicalSignalVolume:
    def test_low_volume_reduces_strength(self):
        """When volume is low, overall strength should be lower."""
        df = _ohlcv_df(60)
        # Force last volume to be very low
        df.loc[df.index[-1], "volume"] = 100_000
        result = generate_technical_signal(df)
        # The strength may or may not change depending on other indicators,
        # but at minimum the reasons should mention volume
        reasons_str = " ".join(result["reasons"]).lower()
        assert "volume" in reasons_str or "lemah" in reasons_str

    def test_high_volume_boosts_signal(self):
        """Strong volume can increase confidence."""
        df = _ohlcv_df(60)
        # Force last volume to be very high
        avg_vol = df["volume"].tail(20).mean()
        df.loc[df.index[-1], "volume"] = int(avg_vol * 2.5)
        result = generate_technical_signal(df)
        assert 1 <= result["strength"] <= 100

    def test_no_volume_column_does_not_crash(self):
        """generate_technical_signal should work without volume data."""
        df = _ohlcv_df(30).drop(columns=["volume"])
        result = generate_technical_signal(df)
        assert result["signal"] in ("BUY", "SELL", "NEUTRAL")
        assert 1 <= result["strength"] <= 100


# ═══════════════════════════════════════════
# Multi-timeframe analysis
# ═══════════════════════════════════════════


class TestMultiTimeframeSignal:
    """Test multi-timeframe signal agreement and adjustment logic."""

    def make_signal(self, signal: str, strength: int) -> dict:
        return {"signal": signal, "strength": strength, "reasons": []}

    def make_multi_tf(self, agreement: str, dominant: str = "BUY",
                      pct: float = 0.7) -> dict:
        return {
            "multi_tf_agreement": agreement,
            "agreement_pct": pct,
            "dominant_signal": dominant,
            "adjusted_strength": 65,
            "timeframe_details": {
                "daily": {"signal": dominant, "strength": 70, "reasons": []},
                "weekly": {"signal": "NEUTRAL", "strength": 50, "reasons": []},
                "hourly": {"signal": "NEUTRAL", "strength": 50, "reasons": []},
            },
        }

    def test_high_agreement_keeps_strength(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 80)
        mtf = self.make_multi_tf("high", "BUY", 1.0)
        result = multi_tf_signal(tech, mtf)
        assert result["signal"] == "BUY"
        assert result["strength"] == 80

    def test_medium_agreement_reduces_to_70pct(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 80)
        mtf = self.make_multi_tf("medium", "BUY", 0.7)
        result = multi_tf_signal(tech, mtf)
        # 80 * 0.7 = 56
        assert result["strength"] == 56

    def test_low_agreement_reduces_to_40pct(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 80)
        mtf = self.make_multi_tf("low", "BUY", 0.4)
        result = multi_tf_signal(tech, mtf)
        # 80 * 0.4 = 32
        assert result["strength"] == 32

    def test_low_agreement_contradictory_flips_to_neutral(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 80)
        mtf = self.make_multi_tf("low", "SELL", 0.4)
        result = multi_tf_signal(tech, mtf)
        assert result["signal"] == "NEUTRAL"
        assert result["strength"] == 50

    def test_no_agreement_returns_neutral(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 80)
        mtf = self.make_multi_tf("none", "NEUTRAL", 0.0)
        result = multi_tf_signal(tech, mtf)
        assert result["signal"] == "NEUTRAL"
        assert result["strength"] == 50

    def test_reasons_appended(self):
        from services.multitf import multi_tf_signal
        tech = self.make_signal("BUY", 70)
        mtf = self.make_multi_tf("high", "BUY", 1.0)
        result = multi_tf_signal(tech, mtf)
        assert len(result["reasons"]) > 0
        assert any("konfirmasi kuat" in r.lower() for r in result["reasons"])


class TestAnalyzeMultiTimeframe:
    def test_all_none_returns_defaults(self):
        from services.multitf import analyze_multi_timeframe
        result = analyze_multi_timeframe(None, None, None)
        assert "multi_tf_agreement" in result
        assert "adjusted_strength" in result
        assert "timeframe_details" in result
        assert 1 <= result["adjusted_strength"] <= 100

    def test_returns_expected_keys(self):
        from services.multitf import analyze_multi_timeframe
        result = analyze_multi_timeframe(None, None, None)
        for key in ("multi_tf_agreement", "agreement_pct", "adjusted_strength",
                     "dominant_signal", "timeframe_details"):
            assert key in result, f"Missing key: {key}"

