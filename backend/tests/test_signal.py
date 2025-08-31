# backend/tests/test_signal.py
import pytest

@pytest.fixture
def mock_mixed_news(monkeypatch):
    import app.routers.signal as signal_router

    def _fake(ticker: str, count: int = 25):
        return [
            {"ticker": ticker, "title": "Company beats expectations and surges", "source": "demo", "url": None, "published_at": None},
            {"ticker": ticker, "title": "Shares fall after weak outlook", "source": "demo", "url": None, "published_at": None},
            {"ticker": ticker, "title": "Neutral commentary", "source": "demo", "url": None, "published_at": None},
        ]

    monkeypatch.setattr(signal_router, "fetch_company_news", _fake)
    return _fake

def test_signal_aggregates_sentiment(client, mock_mixed_news):
    r = client.get("/api/signal", params={"ticker": "MSFT"})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "MSFT"
    assert data["counts"]["positive"] == 1
    assert data["counts"]["negative"] == 1
    assert data["counts"]["neutral"] == 1
    assert sum(data["counts"].values()) == 3
    assert data["action"] in {"Buy", "Hold", "Sell"}

def test_signal_has_trend_and_combo(client, mock_mixed_news):
    r = client.get("/api/signal", params={"ticker": "MSFT"})
    assert r.status_code == 200
    data = r.json()
    assert "trend_score" in data
    assert "combo_score" in data
    assert data["action"] in {"Buy", "Hold", "Sell"}
