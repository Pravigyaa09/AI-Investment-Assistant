# backend/tests/test_news.py
import pytest

@pytest.fixture
def mock_news(monkeypatch):
    # Patch the function as imported by the router module
    import app.routers.news as news_router

    def _fake(ticker: str, count: int = 25):
        return [
            {"ticker": ticker, "title": "Apple surges on earnings", "source": "demo", "url": None, "published_at": None},
            {"ticker": ticker, "title": "Guidance beats expectations", "source": "demo", "url": None, "published_at": None},
        ]

    monkeypatch.setattr(news_router, "fetch_company_news", _fake)
    return _fake

def test_news_returns_articles(client, mock_news):
    r = client.get("/api/news", params={"ticker": " aAp l "})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert len(data["articles"]) == 2
    assert "surges" in data["articles"][0]["title"].lower()
