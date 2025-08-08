# backend/routes/news.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, HTTPException
import requests
import re

from logger import get_logger
from utils.sentiment_model import analyze_sentiment
from config import settings

router = APIRouter()
logger = get_logger(__name__)

# Accept tickers like AAPL, BRK.B, RDS-A, TSLA
_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,15}$")

@router.get("/", summary="Get recent company news with sentiment")
def get_news(
    ticker: str = Query(..., description="Stock ticker symbol (e.g. AAPL, BRK.B)"),
    limit: int = Query(5, ge=1, le=20, description="Max articles to return"),
):
    t = ticker.strip().upper()
    if not _TICKER_RE.match(t):
        raise HTTPException(status_code=400, detail="Invalid ticker format.")

    logger.info("Fetching news and analyzing sentiment for ticker: %s", t)

    if not getattr(settings, "FINNHUB_API_KEY", None):
        logger.error("FINNHUB_API_KEY is not set in environment or .env file")
        raise HTTPException(status_code=500, detail="FINNHUB_API_KEY not configured")

    # Past 7 days (UTC) in YYYY-MM-DD as Finnhub expects
    today = datetime.now(timezone.utc).date()
    from_date = (today - timedelta(days=7)).isoformat()
    to_date = today.isoformat()

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": t,
        "from": from_date,
        "to": to_date,
        "token": settings.FINNHUB_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.exception("Timeout fetching news for %s", t)
        raise HTTPException(status_code=504, detail="News request timed out")
    except requests.HTTPError as http_err:
        logger.exception("Finnhub HTTP error for %s", t)
        # If rate-limited, surface a clearer message
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limited by news provider")
        raise HTTPException(status_code=resp.status_code, detail=str(http_err))
    except Exception:
        logger.exception("Error fetching news for %s", t)
        raise HTTPException(status_code=500, detail="Failed to fetch news")

    raw_items = resp.json() or []
    news_items = (raw_items if isinstance(raw_items, list) else [])[:limit]

    articles = []
    for article in news_items:
        title = (article.get("headline") or "").strip()
        unix_ts = article.get("datetime")
        published_iso = (
            datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()
            if isinstance(unix_ts, (int, float))
            else None
        )
        sentiment = analyze_sentiment(title) if title else "unknown"

        articles.append(
            {
                "title": title,
                "sentiment": sentiment,
                "link": article.get("url"),
                "published": published_iso,  # ISO 8601 string
                "source": article.get("source"),
            }
        )

    return {"ticker": t, "from": from_date, "to": to_date, "articles": articles}
