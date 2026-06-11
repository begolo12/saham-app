"""Integration tests for FastAPI endpoints using TestClient with mocked dependencies."""

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

SAMPLE_STOCK = {
    "symbol": "BBCA.JK",
    "name": "Bank Central Asia Tbk.",
    "price": 10250,
    "change_percent": 0.5,
    "sector": "Perbankan",
    "volume": 1_000_000,
    "avg_volume": 1_500_000,
    "avg_value": 10_000_000_000,
    "potential_score": 88,
    "trend_5d": 1.2,
    "trend_20d": 0.8,
    "rsi14": 55,
    "volume_ratio": 1.1,
}

SAMPLE_INFO = {
    "trailingPE": 15.0,
    "priceToBook": 2.0,
    "marketCap": 100_000_000_000_000,
    "longName": "Test Stock",
    "sector": "Test Sector",
    "industry": "Test Industry",
}

HIST_DATES = pd.date_range("2025-01-01", periods=60, freq="D")
HIST_DF = pd.DataFrame({
    "open": [5000 + i * 10 for i in range(60)],
    "high": [5100 + i * 10 for i in range(60)],
    "low": [4900 + i * 10 for i in range(60)],
    "close": [5050 + i * 10 for i in range(60)],
    "volume": [1_000_000 + i * 1000 for i in range(60)],
}, index=HIST_DATES)


@pytest.fixture(autouse=True)
def _mock_client():
    """Create FastAPI TestClient with all external deps mocked."""
    ticker = MagicMock()
    ticker.info = SAMPLE_INFO
    ticker.history.return_value = HIST_DF

    # Patch at the module level where yfinance is imported
    with \
        patch("services.stock_service.yf") as mock_yf, \
        patch("routes.stocks.get_top_stocks", return_value=[SAMPLE_STOCK]), \
        patch("routes.stocks.get_stock_history", return_value=HIST_DF), \
        patch("routes.stocks.get_stock_info", return_value=SAMPLE_INFO):

        mock_yf.Ticker.return_value = ticker

        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        yield client


# ═══════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════

class TestHealth:
    def test_health_returns_ok(self, _mock_client):
        resp = _mock_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "saham-app-api"

    def test_health_has_database_field(self, _mock_client):
        resp = _mock_client.get("/health")
        assert "database" in resp.json()


class TestStocks:
    def test_list_stocks_returns_stocks(self, _mock_client):
        resp = _mock_client.get("/api/stocks")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data
        assert len(data["stocks"]) > 0
        assert data["stocks"][0]["symbol"] == "BBCA"

    def test_list_stocks_has_required_fields(self, _mock_client):
        resp = _mock_client.get("/api/stocks")
        stock = resp.json()["stocks"][0]
        assert "symbol" in stock
        assert "price" in stock
        assert "signal" in stock
        assert "signal_strength" in stock
        assert "trade_plan" in stock

    def test_search_stocks(self, _mock_client):
        resp = _mock_client.get("/api/stocks/search?q=BBCA")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data
        assert "query" in data

    def test_search_empty_query(self, _mock_client):
        resp = _mock_client.get("/api/stocks/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stocks"] == []


class TestAuth:
    def test_auth_me_without_token_returns_401(self, _mock_client):
        resp = _mock_client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_auth_me_with_bad_token_returns_401(self, _mock_client):
        resp = _mock_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert resp.status_code == 401

    def test_health_no_auth_required(self, _mock_client):
        resp = _mock_client.get("/health")
        assert resp.status_code == 200


class TestSecurityHeaders:
    def test_security_headers_present(self, _mock_client):
        resp = _mock_client.get("/health")
        h = resp.headers
        assert h.get("x-content-type-options") == "nosniff"
        assert h.get("x-frame-options") == "DENY"
        assert h.get("x-xss-protection") == "1; mode=block"
        assert h.get("referrer-policy") == "strict-origin-when-cross-origin"
