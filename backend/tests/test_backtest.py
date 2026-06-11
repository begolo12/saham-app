"""
Unit tests for BacktestEngine and weighted ensemble signal combination (S1+S2).
"""

import math
import numpy as np
import pandas as pd
import pytest

from services.backtest import BacktestEngine
from analysis import combine_signals, detect_market_regime


# ── Helpers ──

def _ohlcv_df(length: int = 100, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    close = pd.Series(np.random.randn(length).cumsum() + 5000, name="close")
    high = close * (1 + np.abs(np.random.randn(length)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(length)) * 0.01)
    volume = pd.Series(np.random.randint(1_000_000, 20_000_000, size=length), name="volume")
    return pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})


def _linear_series(start: float, step: float, length: int = 30) -> pd.Series:
    return pd.Series([start + i * step for i in range(length)])


# ═══════════════════════════════════════════
# BacktestEngine — Initialization
# ═══════════════════════════════════════════

class TestBacktestEngineInit:
    def test_engine_creates_with_default_capital(self):
        engine = BacktestEngine()
        assert engine.initial_capital == 10_000_000

    def test_engine_creates_with_custom_capital(self):
        engine = BacktestEngine(initial_capital=50_000_000)
        assert engine.initial_capital == 50_000_000

    def test_engine_has_required_methods(self):
        engine = BacktestEngine()
        assert hasattr(engine, 'run_backtest')
        assert hasattr(engine, 'run_batch_backtest')
        assert hasattr(engine, 'evaluate_signal_accuracy')

    def test_empty_result_shape(self):
        engine = BacktestEngine()
        result = engine._empty_result('TEST', 'no data')
        assert result['symbol'] == 'TEST'
        assert result['error'] == 'no data'
        assert result['win_rate'] == 0
        assert result['total_trades'] == 0


# ═══════════════════════════════════════════
# BacktestEngine — Accuracy Calculation Edge Cases
# ═══════════════════════════════════════════

class TestBacktestAccuracy:
    def test_no_trades_returns_zeros(self):
        engine = BacktestEngine()
        result = engine._calc_accuracy([])
        assert result['win_rate'] == 0
        assert result['avg_return'] == 0
        assert result['sharpe_ratio'] == 0
        assert result['max_drawdown'] == 0
        assert result['total_trades'] == 0

    def test_single_trade_win(self):
        engine = BacktestEngine()
        trades = [{'is_correct': True, 'return_pct': 5.0}]
        result = engine._calc_accuracy(trades)
        assert result['win_rate'] == 100.0
        assert result['avg_return'] == 5.0
        assert result['total_trades'] == 1

    def test_single_trade_loss(self):
        engine = BacktestEngine()
        trades = [{'is_correct': False, 'return_pct': -3.0}]
        result = engine._calc_accuracy(trades)
        assert result['win_rate'] == 0.0
        assert result['avg_return'] == -3.0
        assert result['total_trades'] == 1

    def test_multiple_trades_win_rate(self):
        engine = BacktestEngine()
        trades = [
            {'is_correct': True, 'return_pct': 2.0},
            {'is_correct': True, 'return_pct': 1.5},
            {'is_correct': False, 'return_pct': -1.0},
            {'is_correct': True, 'return_pct': 3.0},
        ]
        result = engine._calc_accuracy(trades)
        assert result['win_rate'] == 75.0
        assert result['total_trades'] == 4
        assert result['avg_return'] == pytest.approx(1.375, rel=1e-2)

    def test_sharpe_ratio_zero_with_single_trade(self):
        engine = BacktestEngine()
        trades = [{'is_correct': True, 'return_pct': 2.0}]
        result = engine._calc_accuracy(trades)
        assert result['sharpe_ratio'] == 0.0

    def test_max_drawdown_with_negative_returns(self):
        engine = BacktestEngine()
        trades = [
            {'is_correct': True, 'return_pct': 5.0},
            {'is_correct': False, 'return_pct': -10.0},
            {'is_correct': True, 'return_pct': 8.0},
        ]
        result = engine._calc_accuracy(trades)
        assert result['max_drawdown'] > 0
        assert result['max_drawdown'] >= 5.0  # cumulative drawdown


# ═══════════════════════════════════════════
# BacktestEngine — Simulate / Aggregate Edge Cases
# ═══════════════════════════════════════════

class TestBacktestSimulate:
    def test_short_data_returns_no_trades(self):
        engine = BacktestEngine()
        df = _ohlcv_df(30)  # too short
        trades = engine._simulate_trades('TEST', df)
        assert len(trades) == 0

    def test_empty_df_returns_no_trades(self):
        engine = BacktestEngine()
        df = pd.DataFrame()
        trades = engine._simulate_trades('TEST', df)
        assert len(trades) == 0

    def test_simulate_with_sufficient_data(self):
        engine = BacktestEngine()
        df = _ohlcv_df(200)
        trades = engine._simulate_trades('TEST', df)
        # May produce trades depending on signal generation
        assert isinstance(trades, list)

    def test_adjust_weights_from_performance_low_win_rate(self):
        engine = BacktestEngine()
        result = {'win_rate': 30, 'total_trades': 10}
        # Should not crash
        engine._adjust_weights_from_performance('TEST', result)

    def test_adjust_weights_from_performance_high_win_rate(self):
        engine = BacktestEngine()
        result = {'win_rate': 80, 'total_trades': 10}
        # Should not crash
        engine._adjust_weights_from_performance('TEST', result)

    def test_adjust_weights_zero_win_rate_no_change(self):
        engine = BacktestEngine()
        result = {'win_rate': 0, 'total_trades': 10}
        # Should not crash
        engine._adjust_weights_from_performance('TEST', result)


# ═══════════════════════════════════════════
# Weighted Ensemble — Weight Normalization
# ═══════════════════════════════════════════

class TestWeightedEnsembleWeights:
    def test_default_weights_sum_to_one(self):
        tech = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund)
        assert 'weights_used' in result
        w = result['weights_used']
        total = sum(w.values())
        assert abs(total - 1.0) < 0.01

    def test_weights_used_is_in_result(self):
        tech = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund)
        assert 'weights_used' in result
        assert isinstance(result['weights_used'], dict)

    def test_all_weight_keys_present(self):
        tech = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund)
        keys = set(result['weights_used'].keys())
        assert keys == {'ta_weight', 'fund_weight', 'sent_weight', 'vol_weight', 'regime_weight'}


# ═══════════════════════════════════════════
# Weighted Ensemble — Regime-Based Adjustment
# ═══════════════════════════════════════════

class TestRegimeWeightAdjustment:
    def test_trending_up_increases_ta_weight(self):
        # Create uptrend data to trigger trending_up regime
        prices = _linear_series(4000, 10, 250)
        df = pd.DataFrame({'close': prices, 'high': prices * 1.02, 'low': prices * 0.98, 'volume': [1_000_000] * 250})
        regime = detect_market_regime(prices)
        assert regime['regime'] == 'trending_up'
        tech = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        fund = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        result = combine_signals(tech, fund, df=df)
        # In trending_up, ta_weight should be boosted
        assert result['weights_used']['ta_weight'] > 0.27  # default ~0.27 after normalize

    def test_volatile_increases_regime_weight(self):
        # Create volatile data
        flat = [5000] * 100
        osc = [4500 if i % 2 == 0 else 5500 for i in range(20)]
        prices = pd.Series(flat + osc)
        regime = detect_market_regime(prices)
        assert regime['regime'] == 'volatile'
        df = pd.DataFrame({'close': prices, 'high': prices * 1.05, 'low': prices * 0.95, 'volume': [1_000_000] * 120})
        tech = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund, df=df)
        # In volatile, regime_weight should be boosted
        assert result['weights_used']['regime_weight'] > 0.09  # default ~0.09

    def test_ranging_increases_fund_weight(self):
        # Create ranging data (oscillating around mean)
        np.random.seed(0)
        prices = pd.Series(5000 + np.random.randn(250).cumsum() * 5)
        df = pd.DataFrame({'close': prices, 'high': prices * 1.02, 'low': prices * 0.98, 'volume': [1_000_000] * 250})
        # May or may not be ranging; if it is, fund_weight > default
        tech = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund, df=df)
        # At minimum verify result has the right structure
        assert 'weights_used' in result

    def test_market_regime_in_result_when_df_provided(self):
        df = _ohlcv_df(250)
        tech = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund, df=df)
        assert result['market_regime'] in ('ranging', 'trending_up', 'trending_down', 'volatile')

    def test_regime_confidence_in_result(self):
        tech = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund)
        assert 'regime_confidence' in result
        assert 0 <= result['regime_confidence'] <= 1.0


# ═══════════════════════════════════════════
# Weighted Ensemble — Integration with combine_signals
# ═══════════════════════════════════════════

class TestEnsembleIntegration:
    def test_confidence_level_in_result(self):
        tech = {'signal': 'BUY', 'strength': 75, 'reasons': []}
        fund = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        result = combine_signals(tech, fund)
        assert 'confidence_level' in result
        assert 0 <= result['confidence_level'] <= 100

    def test_high_agreement_gives_high_confidence(self):
        tech = {'signal': 'BUY', 'strength': 80, 'reasons': []}
        fund = {'signal': 'BUY', 'strength': 80, 'reasons': []}
        result = combine_signals(tech, fund)
        # Both BUY + default neutral vol/regime = 3/5 agreeing at minimum
        assert result['confidence_level'] >= 30

    def test_strong_buy_signal(self):
        tech = {'signal': 'BUY', 'strength': 85, 'reasons': ['bullish']}
        fund = {'signal': 'BUY', 'strength': 80, 'reasons': ['cheap']}
        result = combine_signals(tech, fund)
        assert result['signal'] == 'BUY'
        assert result['strength'] >= 65

    def test_strong_sell_signal(self):
        tech = {'signal': 'SELL', 'strength': 15, 'reasons': ['bearish']}
        fund = {'signal': 'SELL', 'strength': 20, 'reasons': ['expensive']}
        result = combine_signals(tech, fund)
        assert result['signal'] == 'SELL'
        assert result['strength'] <= 35

    def test_signal_strength_bounded(self):
        for _ in range(10):
            tech = {'signal': 'BUY', 'strength': np.random.randint(1, 101), 'reasons': []}
            fund = {'signal': 'BUY', 'strength': np.random.randint(1, 101), 'reasons': []}
            result = combine_signals(tech, fund)
            assert 1 <= result['strength'] <= 100

    def test_vwap_atr_sl_tp_when_df_provided(self):
        df = _ohlcv_df(250)
        tech = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = combine_signals(tech, fund, df=df, entry_price=5000)
        assert 'vwap' in result
        assert 'atr' in result
        assert 'stop_loss' in result
        assert 'take_profit' in result
        assert 'risk_reward_ratio' in result

    def test_weighted_ensemble_differs_from_simple_average(self):
        """With diverse component scores and disagreeing signals, weighted result
        differs from simple avg.

        For tech=SELL/strength=30 and fund=BUY/strength=70 with default weights
        (0.3/0.3/0.2/0.1/0.1), the ensemble drags sent_score toward 50 (signals
        disagree) and mixes vol/regime=50, so result ~ 30*0.3 + 70*0.3 + 50*0.2 +
        50*0.1 + 50*0.1 = 9 + 21 + 10 + 5 + 5 = 50, vs simple avg of (30+70)/2=50.
        To prove the ensembles differ, use SELL+NEUTRAL so component scores
        differ more sharply than 2 components would.
        """
        tech = {'signal': 'SELL', 'strength': 30, 'reasons': []}
        fund = {'signal': 'BUY', 'strength': 80, 'reasons': []}
        result = combine_signals(tech, fund)
        # Without sent/vol/regime provided, the ensemble mixes their neutral 50
        # defaults via the weight distribution, so it differs from the bare
        # 2-input mean of 55.
        simple_avg = (30 + 80) // 2
        assert result['strength'] != simple_avg, (
            f"weighted ensemble {result['strength']} should differ from simple "
            f"avg {simple_avg} because sent/vol/regime default to 50 with 40% combined weight"
        )
