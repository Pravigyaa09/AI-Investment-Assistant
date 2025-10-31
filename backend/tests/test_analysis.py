"""
Test suite for backend/app/routers/analysis.py
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from app.routers.analysis import (
    _sentiment_fallback,
    _sentiment,
    _daily_returns,
    _sentiment_index,
    _estimate_return_and_risk,
    _rule_signal,
    _analyze_one,
)


class TestSentimentFallback:
    """Test the fallback sentiment analyzer"""

    def test_positive_keywords(self):
        result = _sentiment_fallback("Stock surges on record profit")
        assert result["label"] == "positive"
        assert result["score"] == 0.66

    def test_negative_keywords(self):
        result = _sentiment_fallback("Company stock falls amid losses")
        assert result["label"] == "negative"
        assert result["score"] == 0.66

    def test_neutral_default(self):
        result = _sentiment_fallback("Company announces quarterly results")
        assert result["label"] == "neutral"
        assert result["score"] == 0.5

    def test_empty_title(self):
        result = _sentiment_fallback("")
        assert result["label"] == "neutral"
        assert result["score"] == 0.5


class TestSentiment:
    """Test the main sentiment analyzer (with FinBERT fallback)"""

    @patch('app.routers.analysis.FinBERT')
    def test_finbert_available(self, mock_finbert):
        mock_finbert.is_available.return_value = True
        mock_finbert.predict.return_value = {"label": "positive", "score": 0.95}

        result = _sentiment("Great earnings!")
        assert result["label"] == "positive"
        assert result["score"] == 0.95

    @patch('app.routers.analysis.FinBERT', None)
    def test_finbert_unavailable_fallback(self):
        result = _sentiment("Stock surges")
        assert result["label"] == "positive"
        assert result["score"] == 0.66


class TestDailyReturns:
    """Test daily returns calculation"""

    def test_basic_returns(self):
        closes = [100.0, 105.0, 103.0, 108.0]
        returns = _daily_returns(closes)

        assert len(returns) == 3
        assert abs(returns[0] - 0.05) < 0.001  # 5% gain
        assert abs(returns[1] - (-0.0190476)) < 0.001  # ~1.9% loss
        assert abs(returns[2] - 0.0485437) < 0.001  # ~4.85% gain

    def test_empty_list(self):
        returns = _daily_returns([])
        assert returns == []

    def test_single_value(self):
        returns = _daily_returns([100.0])
        assert returns == []

    def test_zero_price_handling(self):
        closes = [100.0, 0.0, 105.0]
        returns = _daily_returns(closes)
        # Should skip calculation when previous price is 0
        assert len(returns) == 1  # Only last one calculated


class TestSentimentIndex:
    """Test sentiment index calculation"""

    def test_all_positive(self):
        items = [
            {"label": "positive", "score": 0.8},
            {"label": "positive", "score": 0.9},
        ]
        index = _sentiment_index(items)
        assert abs(index - 0.85) < 0.001  # Average of 0.8 and 0.9

    def test_all_negative(self):
        items = [
            {"label": "negative", "score": 0.7},
            {"label": "negative", "score": 0.9},
        ]
        index = _sentiment_index(items)
        assert index == -0.8  # Average of -0.7 and -0.9

    def test_mixed_sentiments(self):
        items = [
            {"label": "positive", "score": 0.8},
            {"label": "negative", "score": 0.6},
            {"label": "neutral", "score": 0.5},
        ]
        index = _sentiment_index(items)
        # (0.8 - 0.6 + 0) / 3 = 0.2 / 3 = 0.0666667
        assert abs(index - (0.2 / 3)) < 0.001

    def test_empty_list(self):
        index = _sentiment_index([])
        assert index == 0.0


class TestEstimateReturnAndRisk:
    """Test return and risk estimation"""

    def test_basic_estimation(self):
        closes = [100.0 + i * 0.5 for i in range(65)]  # Upward trend
        sentiments = [{"label": "positive", "score": 0.8}]

        result = _estimate_return_and_risk(closes, sentiments, horizon_days=21)

        assert "expected_return_pct" in result
        assert "risk_vol_ann_pct" in result
        assert "var_95_daily_pct" in result
        assert "sentiment_index" in result
        assert result["sentiment_index"] == 0.8

    def test_negative_sentiment_impact(self):
        closes = [100.0] * 65  # Flat prices
        sentiments = [{"label": "negative", "score": 1.0}]

        result = _estimate_return_and_risk(closes, sentiments, horizon_days=21)

        assert result["sentiment_index"] == -1.0
        # Expected return should be negative due to sentiment
        assert result["expected_return_pct"] < 0

    def test_minimal_data(self):
        closes = [100.0, 101.0]
        sentiments = []

        result = _estimate_return_and_risk(closes, sentiments, horizon_days=21)

        assert isinstance(result["expected_return_pct"], float)
        assert isinstance(result["risk_vol_ann_pct"], float)


class TestRuleSignal:
    """Test rule-based signal generation"""

    def test_buy_signal(self):
        action, conf = _rule_signal(pos=14, neg=2, neu=4)
        assert action == "Buy"
        assert conf >= 0.70

    def test_sell_signal(self):
        action, conf = _rule_signal(pos=2, neg=12, neu=6)
        assert action == "Sell"
        assert conf >= 0.60

    def test_hold_signal(self):
        action, conf = _rule_signal(pos=5, neg=5, neu=10)
        assert action == "Hold"

    def test_edge_case_all_zero(self):
        action, conf = _rule_signal(pos=0, neg=0, neu=0)
        # Should handle division by zero
        assert action in ["Buy", "Sell", "Hold"]


class TestAnalyzeOne:
    """Test the main analysis function"""

    @pytest.mark.asyncio
    @patch('app.routers.analysis.get_quote')
    @patch('app.routers.analysis.get_candles_close')
    @patch('app.routers.analysis.fetch_company_news')
    @patch('app.routers.analysis.get_repository')
    async def test_analyze_without_user(
        self, mock_repo, mock_news, mock_candles, mock_quote
    ):
        # Mock market data
        mock_quote.return_value = 150.0
        mock_candles.return_value = [100.0 + i for i in range(90)]
        mock_news.return_value = [
            {"title": "Stock surges", "url": "http://example.com/1"},
            {"title": "Company beats estimates", "url": "http://example.com/2"},
        ]

        result = await _analyze_one(
            "AAPL",
            days=90,
            top_n_news=8,
            horizon_days=21,
            user_id=None
        )

        assert result["ticker"] == "AAPL"
        assert result["price"] == 150.0
        assert result["position"] is None
        assert "trend_score" in result
        assert "volatility_ann" in result
        assert "sentiment_counts" in result
        assert "sentiments" in result
        assert "estimated" in result
        assert "suggestion" in result
        assert result["suggestion"]["action"] in ["Buy", "Sell", "Hold"]

    @pytest.mark.asyncio
    @patch('app.routers.analysis.get_quote')
    @patch('app.routers.analysis.get_candles_close')
    @patch('app.routers.analysis.fetch_company_news')
    @patch('app.routers.analysis.get_repository')
    async def test_analyze_with_user_position(
        self, mock_repo, mock_news, mock_candles, mock_quote
    ):
        # Mock market data
        mock_quote.return_value = 150.0
        mock_candles.return_value = [100.0 + i for i in range(90)]
        mock_news.return_value = []

        # Mock user portfolio
        mock_holding = MagicMock()
        mock_holding.ticker = "AAPL"
        mock_holding.quantity = 10
        mock_holding.avg_cost = 140.0

        mock_portfolio = MagicMock()
        mock_portfolio.holdings = [mock_holding]

        mock_user_repo = AsyncMock()
        mock_user_repo.get_portfolio.return_value = mock_portfolio
        mock_repo.return_value = mock_user_repo

        result = await _analyze_one(
            "AAPL",
            days=90,
            top_n_news=8,
            horizon_days=21,
            user_id="user123"
        )

        assert result["ticker"] == "AAPL"
        assert result["position"] is not None
        assert result["position"]["quantity"] == 10
        assert result["position"]["avg_cost"] == 140.0
        assert result["position"]["last_price"] == 150.0
        assert result["position"]["market_value"] == 1500.0
        assert result["position"]["pnl_abs"] == 100.0  # (150-140)*10

    @pytest.mark.asyncio
    async def test_analyze_empty_ticker(self):
        with pytest.raises(HTTPException) as exc_info:
            await _analyze_one("", days=90, top_n_news=8, horizon_days=21)

        assert exc_info.value.status_code == 400
        assert "ticker is required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch('app.routers.analysis.get_quote')
    async def test_analyze_invalid_ticker(self, mock_quote):
        mock_quote.side_effect = Exception("Invalid ticker")

        with pytest.raises(Exception):
            await _analyze_one(
                "INVALID",
                days=90,
                top_n_news=8,
                horizon_days=21
            )


class TestAnalysisEndpoints:
    """Test the FastAPI endpoints (integration-style tests)"""

    @pytest.mark.asyncio
    @patch('app.routers.analysis._analyze_one')
    async def test_analyze_stock_endpoint(self, mock_analyze, client):
        mock_analyze.return_value = {
            "ticker": "AAPL",
            "price": 150.0,
            "suggestion": {"action": "Buy", "confidence": 0.8}
        }

        response = client.get("/api/v1/stocks/AAPL/analysis")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["price"] == 150.0

    @pytest.mark.asyncio
    @patch('app.routers.analysis._analyze_one')
    async def test_analyze_stocks_batch_endpoint(self, mock_analyze, client):
        mock_analyze.return_value = {
            "ticker": "AAPL",
            "price": 150.0,
        }

        response = client.get("/api/v1/stocks/analysis?tickers=AAPL,MSFT,GOOGL")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3

    @pytest.mark.asyncio
    async def test_analyze_stocks_batch_no_tickers(self, client):
        response = client.get("/api/v1/stocks/analysis?tickers=")

        assert response.status_code == 400

    @pytest.mark.asyncio
    @patch('app.routers.analysis._analyze_one')
    async def test_analyze_stocks_batch_limit(self, mock_analyze, client):
        mock_analyze.return_value = {"ticker": "TEST"}

        # Create 25 tickers (should be limited to 20)
        tickers = ",".join([f"TICK{i}" for i in range(25)])
        response = client.get(f"/api/v1/stocks/analysis?tickers={tickers}")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 20


# Pytest fixtures
@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    from fastapi.testclient import TestClient
    from contextlib import asynccontextmanager
    import app.main

    # Mock the lifespan context manager to avoid MongoDB connection
    @asynccontextmanager
    async def mock_lifespan(app):
        # Skip MongoDB and other startup tasks
        yield

    # Temporarily replace lifespan
    original_lifespan = app.main.lifespan
    app.main.lifespan = mock_lifespan

    # Import app after mocking
    from app.main import app as fastapi_app
    client = TestClient(fastapi_app)

    # Restore original lifespan after test
    yield client
    app.main.lifespan = original_lifespan


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
