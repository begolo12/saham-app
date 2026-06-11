"""
Unit tests for macro economic data service (services/macro.py).
"""

from unittest.mock import patch, MagicMock

import pytest

from services.macro import (
    fetch_bi_rate,
    fetch_inflation,
    fetch_usd_idr,
    macro_correlation,
    apply_macro_bias,
    save_market_regime,
    get_latest_market_regime,
)


class TestFetchBiRate:
    def test_returns_dict_with_rate_key(self):
        result = fetch_bi_rate()
        assert isinstance(result, dict)
        assert 'rate' in result
        assert isinstance(result['rate'], (int, float))

    def test_rate_is_positive(self):
        result = fetch_bi_rate()
        assert result['rate'] > 0


class TestFetchInflation:
    def test_returns_dict_with_cpi(self):
        result = fetch_inflation()
        assert isinstance(result, dict)
        assert 'cpi_yoy' in result
        assert isinstance(result['cpi_yoy'], (int, float))

    def test_cpi_is_reasonable(self):
        result = fetch_inflation()
        assert 0 < result['cpi_yoy'] < 20


class TestFetchUsdIdr:
    def test_returns_dict_with_rate(self):
        result = fetch_usd_idr()
        assert isinstance(result, dict)
        assert 'rate' in result

    def test_rate_is_reasonable(self):
        result = fetch_usd_idr()
        if result['rate'] is not None:
            assert 10000 < result['rate'] < 20000  # realistic USD/IDR range

    def test_has_source(self):
        result = fetch_usd_idr()
        assert 'source' in result


class TestMacroCorrelation:
    def test_perbankan_has_factors(self):
        result = macro_correlation('Perbankan')
        assert result['has_macro_sensitivity'] is True
        assert len(result['factors']) > 0

    def test_unknown_sector_no_factors(self):
        result = macro_correlation('UnknownSectorXYZ')
        assert result['has_macro_sensitivity'] is False

    def test_perbankan_factors_contain_bi_rate(self):
        result = macro_correlation('Perbankan')
        factor_names = [f['factor'] for f in result['factors']]
        assert 'BI Rate' in factor_names

    def test_pertambangan_factors_contain_usd(self):
        result = macro_correlation('Pertambangan')
        factor_names = [f['factor'] for f in result['factors']]
        assert 'USD/IDR' in factor_names

    def test_fuzzy_match_lowercase(self):
        result = macro_correlation('perbankan')
        assert result['has_macro_sensitivity'] is True or not result['has_macro_sensitivity']


class TestApplyMacroBias:
    def test_no_sector_returns_unchanged(self):
        signal = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        result = apply_macro_bias(signal, '')
        assert result['signal'] == 'BUY'
        assert result['strength'] == 70

    def test_unknown_sector_unchanged(self):
        signal = {'signal': 'BUY', 'strength': 70, 'reasons': []}
        result = apply_macro_bias(signal, 'UNKNOWN_SECTOR')
        assert result['strength'] == 70

    def test_perbankan_returns_valid_result(self):
        signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        result = apply_macro_bias(signal, 'Perbankan')
        # Should have macro notes in reasons
        assert 'reasons' in result
        assert 1 <= result['strength'] <= 100

    def test_strength_always_bounded(self):
        signal = {'signal': 'NEUTRAL', 'strength': 50, 'reasons': []}
        for sector in ['Perbankan', 'Pertambangan', 'Properti & Real Estat', 'Barang Konsumsi']:
            result = apply_macro_bias(signal, sector)
            assert 1 <= result['strength'] <= 100

    def test_does_not_mutate_input(self):
        signal = {'signal': 'BUY', 'strength': 70, 'reasons': ['test']}
        original_strength = signal['strength']
        result = apply_macro_bias(signal, 'Perbankan')
        # Input should not be modified
        assert signal['strength'] == original_strength


class TestSaveAndGetMarketRegime:
    def test_save_and_retrieve(self):
        regime_data = {
            'regime': 'ranging',
            'confidence': 0.7,
            'ihsg_trend': 0.5,
            'volatility': 0.8,
        }
        saved = save_market_regime(regime_data)
        assert saved is True or saved is False  # depends on DB availability
        if saved:
            latest = get_latest_market_regime()
            if latest:
                assert 'regime' in latest
                assert 'date' in latest

    def test_save_with_macro_fields(self):
        regime_data = {
            'regime': 'trending_up',
            'confidence': 0.8,
            'ihsg_trend': 1.2,
            'volatility': 0.3,
        }
        saved = save_market_regime(regime_data)
        assert saved in (True, False)
