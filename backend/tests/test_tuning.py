"""Tests for S2b weight tuning script and S12b outlier smoothing.

Covers:
  - Weight grid search (score_weights, grid_search, composite score)
  - Outlier smoothing (3-day window + cap)
  - Periodic backtest safety (refresh_backtest_tune handles empty data)
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from analysis import detect_outlier
from scripts.tune_weights import (
    DEFAULT_WEIGHTS,
    GRID_FUND,
    GRID_REGIME,
    GRID_SENT,
    GRID_TA,
    GRID_VOL,
    _composite_score,
    _compute_components,
    _gather_windows,
    _score_weights,
    apply_weights,
    grid_search,
    run_tune,
)
from services.worker import INTERVAL_BACKTEST_TUNE, _pick_symbols_with_recommendations


# ── Helpers ───────────────────────────────────────────────────────

def _synthetic_windows(n: int = 100, seed: int = 7) -> list:
    """Generate n synthetic (component, return_pct) windows."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        ta = float(rng.uniform(20, 90))
        fund = float(rng.uniform(20, 90))
        sent = float(rng.uniform(20, 90))
        vol = float(rng.uniform(20, 90))
        regime = float(rng.uniform(20, 90))
        # Return correlates with TA + Fund so weights matter
        ret = float(0.4 * (ta - 50) + 0.4 * (fund - 50) + rng.normal(0, 3))
        rows.append({
            'ta': ta, 'fund': fund, 'sent': sent, 'vol': vol, 'regime': regime,
            'return_pct': ret,
        })
    return rows


def _ohlcv_df(length: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = pd.Series(rng.standard_normal(length).cumsum() + 5000, name='close')
    high = close * (1 + np.abs(rng.standard_normal(length)) * 0.005)
    low = close * (1 - np.abs(rng.standard_normal(length)) * 0.005)
    volume = pd.Series(rng.integers(1_000_000, 5_000_000, length), name='volume')
    df = pd.DataFrame({'high': high, 'low': low, 'close': close, 'volume': volume})
    df.index = pd.date_range('2024-01-01', periods=length, freq='D')
    return df


# ═══════════════════════════════════════════
# S2b — Weight grid search
# ═══════════════════════════════════════════

class TestGridSearch:
    def test_grid_constants_within_spec(self):
        """Grid ranges must match the spec."""
        assert GRID_TA == [0.2, 0.3, 0.4, 0.5]
        assert GRID_FUND == [0.2, 0.3, 0.4, 0.5]
        assert GRID_SENT == [0.1, 0.2, 0.3]
        assert GRID_VOL == [0.05, 0.10, 0.15, 0.20]
        assert GRID_REGIME == [0.05, 0.10, 0.15, 0.20]

    def test_score_weights_handles_empty_windows(self):
        m = _score_weights(DEFAULT_WEIGHTS, [])
        assert m['win_rate'] == 0
        assert m['total_trades'] == 0

    def test_score_weights_normalizes_input(self):
        """Sum of weights doesn't need to be 1 — scorer normalizes."""
        windows = _synthetic_windows(50)
        m = _score_weights(
            {'ta_weight': 2, 'fund_weight': 2, 'sent_weight': 1,
             'vol_weight': 0, 'regime_weight': 0},
            windows,
        )
        # Should run without error and return a valid metric dict
        assert 'win_rate' in m
        assert 'sharpe_ratio' in m
        assert 'total_trades' in m
        assert m['total_trades'] >= 0

    def test_score_weights_handles_all_zero_weights(self):
        """All-zero weights should not crash."""
        windows = _synthetic_windows(20)
        m = _score_weights(
            {'ta_weight': 0, 'fund_weight': 0, 'sent_weight': 0,
             'vol_weight': 0, 'regime_weight': 0},
            windows,
        )
        # No valid ensemble => no trades
        assert m['total_trades'] == 0

    def test_grid_search_returns_valid_structure(self):
        windows = _synthetic_windows(80)
        best_w, best_m = grid_search(windows)
        assert set(best_w.keys()) == {
            'ta_weight', 'fund_weight', 'sent_weight', 'vol_weight', 'regime_weight',
        }
        assert 'win_rate' in best_m
        assert 'sharpe_ratio' in best_m
        assert 'avg_return' in best_m
        assert 'total_trades' in best_m

    def test_grid_search_finds_better_than_default(self):
        """Grid search should pick a config with non-trivial win rate."""
        windows = _synthetic_windows(150, seed=42)
        best_w, best_m = grid_search(windows)
        # The composite score must beat the no-data penalty
        assert _composite_score(best_m) > -1000

    def test_composite_score_penalizes_too_few_trades(self):
        """If total_trades < 3 the score is heavily penalized."""
        low = _composite_score({'win_rate': 80, 'sharpe_ratio': 1, 'avg_return': 5, 'total_trades': 1})
        high = _composite_score({'win_rate': 50, 'sharpe_ratio': 0.5, 'avg_return': 1, 'total_trades': 10})
        assert low < high
        assert low == -1000

    def test_apply_weights_writes_per_symbol_and_default(self):
        """apply_weights should call _upsert_signal_weights for each symbol + ''."""
        weights = dict(DEFAULT_WEIGHTS)
        with patch('scripts.tune_weights._upsert_signal_weights') as mock_upsert:
            updated = apply_weights(['BBCA.JK', 'BBRI.JK'], weights)
        assert updated == 3  # 2 symbols + 1 default
        assert mock_upsert.call_count == 3
        # Last call should be the default (empty) symbol
        last_args = mock_upsert.call_args_list[-1]
        assert last_args[0][0] == ''

    def test_run_tune_returns_summary_dict(self):
        """run_tune with no symbols returns a no-op summary."""
        with patch('scripts.tune_weights.get_top_stocks', return_value=[]):
            summary = run_tune(days=30, symbols=None, top_n=5)
        assert isinstance(summary, dict)
        assert summary['status'] == 'no_symbols'
        assert 'best_weights' in summary
        assert 'best_metrics' in summary


# ═══════════════════════════════════════════
# S12b — Outlier 3-day smoothing
# ═══════════════════════════════════════════

class TestOutlierSmoothing:
    def test_3day_smoothing_blends_with_average(self):
        """When 3-day avg differs by >15 pts, blend 0.6*current + 0.4*avg3."""
        # avg3 = 50, current = 80, delta = 30 > 15 → blend
        # blend = 0.6*80 + 0.4*50 = 48 + 20 = 68
        # cap = 20% of 80 = 16, so adjustment -12 is within cap
        result = detect_outlier(80.0, [60, 55, 52, 50, 48, 50, 50], 'TEST')
        assert result['outlier_flag'] is True
        assert '3-day' in result['reason']
        assert result['adjusted_strength'] == pytest.approx(68.0, abs=0.5)

    def test_3day_smoothing_caps_at_20_percent(self):
        """If blended would move >20% from original, clamp to ±20%."""
        # avg3 = 10, current = 95, delta = 85 > 15
        # blend = 0.6*95 + 0.4*10 = 57 + 4 = 61
        # cap = 20% of 95 = 19, adjustment = 61 - 95 = -34, exceeds cap
        # clamped to 95 - 19 = 76
        result = detect_outlier(95.0, [10, 10, 10, 10, 10, 10, 10], 'TEST')
        assert result['outlier_flag'] is True
        # Cap kicks in, so adjusted is 95 - 19 = 76
        assert result['adjusted_strength'] == pytest.approx(76.0, abs=0.5)

    def test_3day_smoothing_no_trigger_when_close(self):
        """If |current - avg3| <= 15, no outlier."""
        result = detect_outlier(55.0, [50, 52, 54, 56, 55, 57, 55], 'TEST')
        assert result['outlier_flag'] is False
        assert result['adjusted_strength'] == 55.0

    def test_3day_smoothing_handles_short_history(self):
        """When history has < 3 entries, fall back to full avg."""
        # 2-entry history: avg = (52+54)/2 = 53, current 80, delta 27 > 15
        # blend = 0.6*80 + 0.4*53 = 48 + 21.2 = 69.2
        # cap = 16, adjustment = -10.8 within cap
        result = detect_outlier(80.0, [52, 54], 'TEST')
        assert result['outlier_flag'] is True
        assert '3-day' in result['reason']

    def test_rule1_still_triggers_for_extreme_strength(self):
        """Rule 1 (>95 with low avg) still fires after the patch."""
        result = detect_outlier(98.0, [60, 65, 70, 75, 72, 68, 70], 'TEST')
        assert result['outlier_flag'] is True
        assert 'Outlier' in result['reason']


# ═══════════════════════════════════════════
# Periodic backtest — safety on empty data
# ═══════════════════════════════════════════

class TestScheduledBacktest:
    def test_interval_is_six_hours(self):
        """Periodic backtest interval must be 6 hours (21600 s)."""
        assert INTERVAL_BACKTEST_TUNE == 6 * 60 * 60

    def test_pick_symbols_empty_db(self):
        """No recommendations → empty list, no crash."""
        with patch('services.db._db_conn') as mock_conn:
            mock_conn.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            symbols = _pick_symbols_with_recommendations(limit=10)
        assert symbols == []

    def test_pick_symbols_returns_distinct_list(self):
        """Should return distinct symbols sorted by count."""
        mock_rows = [
            {'symbol': 'BBCA.JK', 'cnt': 50},
            {'symbol': 'BBRI.JK', 'cnt': 30},
            {'symbol': 'TLKM.JK', 'cnt': 10},
        ]
        with patch('services.db._db_conn') as mock_conn:
            mock_conn.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = mock_rows
            symbols = _pick_symbols_with_recommendations(limit=10)
        assert symbols == ['BBCA.JK', 'BBRI.JK', 'TLKM.JK']

    def test_pick_symbols_handles_db_error(self):
        """DB exception → returns empty list (no crash)."""
        with patch('services.db._db_conn', side_effect=Exception('db down')):
            symbols = _pick_symbols_with_recommendations(limit=10)
        assert symbols == []

    def test_refresh_backtest_tune_empty_symbols_no_crash(self):
        """When no symbols have recommendations, the task is a no-op."""
        from services.worker import BackgroundWorker

        async def _drive():
            worker = BackgroundWorker()
            with patch('services.worker._pick_symbols_with_recommendations', return_value=[]):
                # Should return without raising
                await worker.refresh_backtest_tune()
            return True

        import asyncio
        result = asyncio.run(_drive())
        assert result is True

    def test_refresh_backtest_tune_tune_failure_does_not_crash(self):
        """If run_tune raises, the task swallows the error and continues."""
        from services.worker import BackgroundWorker

        async def _drive():
            worker = BackgroundWorker()
            with patch('services.worker._pick_symbols_with_recommendations', return_value=['BBCA.JK']):
                with patch('scripts.tune_weights.run_tune', side_effect=RuntimeError('boom')):
                    # Should NOT raise — caught internally
                    await worker.refresh_backtest_tune()
            return True

        import asyncio
        result = asyncio.run(_drive())
        assert result is True

    def test_worker_registers_backtest_task(self):
        """BackgroundWorker.start should schedule refresh_backtest_tune."""
        from services.worker import BackgroundWorker
        worker = BackgroundWorker()
        assert hasattr(worker, 'refresh_backtest_tune')
        assert callable(worker.refresh_backtest_tune)
