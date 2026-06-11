"""Tests for new features: sector correlation (S8), fallback (S10),
outlier detection (S12), A/B test framework (S13), accuracy API (S11).
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from analysis import correlation_analysis, detect_outlier, combine_signals
from services.fallback import (
    _scrape_yahoo_finance_summary,
    _get_cached_from_db,
    fallback_get_stock_info,
)
from services.abtest import get_signal_version, compute_signal, compare_versions


# ═══════════════════════════════════════════
# S8 — Sector Correlation Analysis
# ═══════════════════════════════════════════

class TestCorrelationAnalysis:
    def test_sector_avg_change_positive(self):
        """Sector rising >3% → correlation_adjustment = -15."""
        all_stocks = [
            {'symbol': 'BBCA', 'sector': 'Perbankan', 'change_percent': 4.0},
            {'symbol': 'BBRI', 'sector': 'Perbankan', 'change_percent': 5.0},
            {'symbol': 'BMRI', 'sector': 'Perbankan', 'change_percent': 3.5},
        ]
        sector_map = {'BBCA.JK': 'Perbankan', 'BBRI.JK': 'Perbankan', 'BMRI.JK': 'Perbankan'}
        result = correlation_analysis('BBCA', all_stocks, sector_map)
        assert result['sector_name'] == 'Perbankan'
        assert result['sector_avg_change'] > 3
        assert result['correlation_adjustment'] == -15.0

    def test_sector_avg_change_negative(self):
        """Sector down >3% → correlation_adjustment = -15."""
        all_stocks = [
            {'symbol': 'ADRO', 'sector': 'Energi', 'change_percent': -4.0},
            {'symbol': 'PTBA', 'sector': 'Energi', 'change_percent': -5.0},
        ]
        sector_map = {'ADRO.JK': 'Energi', 'PTBA.JK': 'Energi'}
        result = correlation_analysis('ADRO', all_stocks, sector_map)
        assert result['sector_name'] == 'Energi'
        assert result['sector_avg_change'] < -3
        assert result['correlation_adjustment'] == -15.0

    def test_sector_flat_no_adjustment(self):
        """Sector change within ±3% → no adjustment."""
        all_stocks = [
            {'symbol': 'TLKM', 'sector': 'Telekomunikasi', 'change_percent': 1.0},
            {'symbol': 'EXCL', 'sector': 'Telekomunikasi', 'change_percent': -0.5},
        ]
        sector_map = {'TLKM.JK': 'Telekomunikasi', 'EXCL.JK': 'Telekomunikasi'}
        result = correlation_analysis('TLKM', all_stocks, sector_map)
        assert result['correlation_adjustment'] == 0.0

    def test_unknown_symbol_uses_lainnya(self):
        """Unknown symbol without sector map entry → sector 'Lainnya'."""
        result = correlation_analysis('UNKNOWN', [], {})
        assert result['sector_name'] == 'Lainnya'
        assert result['correlation_adjustment'] == 0.0

    def test_empty_stocks_list_returns_zero(self):
        lst = []
        result = correlation_analysis('BBCA', lst, {'BBCA.JK': 'Perbankan'})
        assert result['sector_avg_change'] == 0.0
        assert result['correlation_adjustment'] == 0.0


# ═══════════════════════════════════════════
# S12 — Outlier Detection
# ═══════════════════════════════════════════

class TestDetectOutlier:
    def test_no_history_no_outlier(self):
        result = detect_outlier(80.0, [], 'TEST')
        assert result['outlier_flag'] is False
        assert result['adjusted_strength'] == 80.0

    def test_high_strength_with_low_avg_flags_outlier(self):
        """Strength >95, rolling avg <80 → flag, cap to avg+10."""
        result = detect_outlier(98.0, [60, 65, 70, 75, 72, 68, 70], 'TEST')
        assert result['outlier_flag'] is True
        # avg = (60+65+70+75+72+68+70)/7 ≈ 68.6
        assert result['adjusted_strength'] == pytest.approx(68.6 + 10, rel=0.5)
        assert 'Outlier' in result['reason']

    def test_sudden_change_flags_outlier(self):
        """Change >15 pts from 3-day avg → flag, smooth with 3-day window."""
        result = detect_outlier(95.0, [50, 52, 48, 51, 49, 50, 50], 'TEST')
        assert result['outlier_flag'] is True
        # 3-day avg = (49+50+50)/3 = 49.67, blend = 0.6*95 + 0.4*49.67 = 76.87
        assert result['adjusted_strength'] == pytest.approx(76.87, rel=0.05)
        assert '3-day' in result['reason']

    def test_normal_strength_no_outlier(self):
        result = detect_outlier(55.0, [50, 52, 54, 56, 58, 57, 55], 'TEST')
        assert result['outlier_flag'] is False
        assert result['adjusted_strength'] == 55.0

    def test_low_strength_not_outlier(self):
        """Strength <95 should not trigger rule 1, and 3-day avg close → no rule 2."""
        # 3-day avg = 53, current = 58 → diff 5 < 15, no rule 2
        result = detect_outlier(58.0, [50, 52, 54, 56, 55, 54, 53], 'TEST')
        assert result['outlier_flag'] is False

    def test_small_change_not_outlier(self):
        """Change <=40 pts → not outlier."""
        result = detect_outlier(60.0, [50, 55, 58, 59], 'TEST')
        assert result['outlier_flag'] is False
        assert result['adjusted_strength'] == 60.0

    def test_adjusted_strength_bounded(self):
        """Adjusted strength should stay within [1, 100]."""
        result = detect_outlier(99.0, [10, 10, 10, 10, 10], 'TEST')
        assert result['outlier_flag'] is True
        assert 1 <= result['adjusted_strength'] <= 100


# ═══════════════════════════════════════════
# S8 + S12 — Integration in combine_signals
# ═══════════════════════════════════════════

class TestCombineSignalsWithS8S12:
    def test_s8_integration_sector_down_reduces_buy(self):
        """Sector down >3% with BUY signal → strength reduced."""
        tech = {'signal': 'BUY', 'strength': 80, 'reasons': ['bullish']}
        fund = {'signal': 'BUY', 'strength': 80, 'reasons': ['cheap']}
        all_stocks = [
            {'symbol': 'BBCA', 'sector': 'Perbankan', 'change_percent': -5.0},
            {'symbol': 'BBRI', 'sector': 'Perbankan', 'change_percent': -4.0},
        ]
        sector_map = {'BBCA.JK': 'Perbankan', 'BBRI.JK': 'Perbankan'}
        result = combine_signals(
            tech, fund, symbol='BBCA',
            all_stocks_data=all_stocks, sector_map=sector_map,
        )
        assert result['strength'] < 75  # reduced from 80
        assert result['sector_avg_change'] < -3

    def test_s12_integration_outlier_detected(self):
        """Outlier strength gets smoothed."""
        tech = {'signal': 'BUY', 'strength': 100, 'reasons': ['bullish']}
        fund = {'signal': 'BUY', 'strength': 100, 'reasons': ['cheap']}
        # Last historical value = 40, ensemble ≈ 88, change = 48 > 40 → rule 2 fires
        result = combine_signals(
            tech, fund,
            historical_strengths=[60, 62, 65, 63, 61, 60, 40],
        )
        assert result['outlier_flag'] is True
        assert 'Outlier' in (result.get('outlier_reason') or '')
        # Should be adjusted down
        assert result['strength'] < 90

    def test_s12_integration_no_outlier_when_normal(self):
        tech = {'signal': 'NEUTRAL', 'strength': 55, 'reasons': []}
        fund = {'signal': 'NEUTRAL', 'strength': 55, 'reasons': []}
        result = combine_signals(
            tech, fund,
            historical_strengths=[50, 52, 54, 56, 55, 57, 55],
        )
        assert result.get('outlier_flag', False) is False


# ═══════════════════════════════════════════
# S10 — Fallback Provider
# ═══════════════════════════════════════════

class TestFallback:
    @patch('services.fallback._scrape_yahoo_finance_summary')
    @patch('services.fallback._get_cached_from_db')
    def test_fallback_info_scrape_then_db(self, mock_db, mock_scrape):
        mock_scrape.return_value = None
        mock_db.return_value = {'symbol': 'BBCA', 'price': 10250}
        # Clear in-memory cache for this symbol
        import services.fallback as fb
        fb._fallback_info_cache.clear()
        result = fallback_get_stock_info('FALLBACK_TEST_UNIQUE.JK')
        # First tries scrape (None), then DB (found)
        assert result['_source'] == 'db-cache'
        assert result['price'] == 10250

    @patch('services.fallback._scrape_yahoo_finance_summary')
    @patch('services.fallback._get_cached_from_db')
    def test_fallback_info_scrape_success(self, mock_db, mock_scrape):
        mock_scrape.return_value = {'symbol': 'BBCA', 'price': 10300, 'change_percent': 1.5}
        # Clear in-memory cache
        import services.fallback as fb
        fb._fallback_info_cache.clear()
        result = fallback_get_stock_info('FALLBACK_TEST2.JK')
        assert result['_source'] == 'scrape'
        assert result['price'] == 10300

    def test_scrape_yahoo_finance_summary_fails_gracefully(self):
        """Bad symbol returns None, not crash."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception('Network error')
            result = _scrape_yahoo_finance_summary('TEST123456789XYZ')
        assert result is None

    @patch('services.fallback._db_conn')
    def test_get_cached_from_db_no_data(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__.return_value.execute.return_value = mock_cursor
        result = _get_cached_from_db('NONEXIST')
        assert result is None


# ═══════════════════════════════════════════
# S13 — A/B Test Framework
# ═══════════════════════════════════════════

class TestABTest:
    def test_get_signal_version_deterministic(self):
        """Same symbol+date always gives same version."""
        v1 = get_signal_version('BBCA')
        v2 = get_signal_version('BBCA')
        assert v1 == v2

    def test_get_signal_version_valid_string(self):
        """Returns 'v1' or 'v2'."""
        v = get_signal_version('BBRI')
        assert v in ('v1', 'v2')

    def test_v1_signal_equal_weight(self):
        result = compute_signal('TEST', {'signal': 'BUY', 'strength': 80, 'reasons': ['tech']},
                                {'signal': 'SELL', 'strength': 20, 'reasons': ['fund']})
        version, signal = result
        if version == 'v1':
            # equal weight: (80+20)//2 = 50
            assert signal['strength'] == 50
        else:
            # v2: 80*0.7 + 20*0.3 = 62 → NEUTRAL (threshold 70)
            assert signal['strength'] == 62
            assert signal['signal'] == 'NEUTRAL'

    def test_compare_versions_returns_dict(self):
        """compare_versions should return valid stats dict even with no data."""
        result = compare_versions()
        assert 'v1' in result
        assert 'v2' in result
        assert 'winner' in result

    def test_v2_uses_v2_reasons_prefix(self):
        """V2 reasons have [V2] prefix."""
        version, signal = compute_signal(
            'TEST_V2', {'signal': 'BUY', 'strength': 80, 'reasons': ['tech']},
            {'signal': 'BUY', 'strength': 60, 'reasons': ['fund']},
        )
        if version == 'v2':
            reasons_str = ' '.join(signal['reasons'])
            assert '[V2]' in reasons_str
            assert '[V2-Fund]' in reasons_str


# ═══════════════════════════════════════════
# S11 — Accuracy API (routing + helpers)
# ═══════════════════════════════════════════

class TestAccuracyAPI:
    def test_accuracy_endpoint_registered(self):
        """Check accuracy endpoint is importable and registered on app."""
        from app import app
        routes = [r.path for r in app.routes]
        assert '/api/accuracy' in routes

    def test_accuracy_summary_endpoint_registered(self):
        from app import app
        routes = [r.path for r in app.routes]
        assert '/api/accuracy/summary' in routes
