# backend/routes/sentiment.py
from datetime import datetime, timedelta, timezone
import re
import requests
from fastapi import APIRouter, Query, HTTPException

from logger import get_logger
from utils.sentiment_model import analyze_sentiment, map_sentiment_to_signal
from config import settings

router = APIRouter()
logger = get_logger(__name__)

# Accept tickers like AAPL, BRK.B, RDS-A, TSLA
_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,15}$")

@router.get("/signal", summary="Get trading signal from recent news sentiment")
def get_trading_signal(
    ticker: str = Query(..., description="Stock ticker symbol (e.g., AAPL, BRK.B)"),
    limit: int = Query(20, ge=1, le=50, description="Max news items to analyze"),
):
    t = ticker.strip().upper()
    if not _TICKER_RE.match(t):
        raise HTTPException(status_code=400, detail="Invalid ticker format.")

    if not getattr(settings, "FINNHUB_API_KEY", None):
        logger.error("FINNHUB_API_KEY is not set in environment or .env file")
        raise HTTPException(status_code=500, detail="FINNHUB_API_KEY not configured")

    logger.info("Computing sentiment-based signal for ticker: %s", t)

    # Past 7 days (UTC) in YYYY-MM-DD
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
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limited by news provider")
        raise HTTPException(status_code=resp.status_code, detail=str(http_err))
    except Exception:
        logger.exception("Error fetching news for %s", t)
        raise HTTPException(status_code=500, detail="Failed to fetch news")

    raw_items = resp.json() or []
    if not isinstance(raw_items, list):
        logger.error("Unexpected news payload for %s", t)
        raise HTTPException(status_code=502, detail="Bad news payload from provider")

    news_items = raw_items[:limit]

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for item in news_items:
        title = (item.get("headline") or "").strip()
        if not title:
            continue
        label = (analyze_sentiment(title) or "neutral").lower()
        if label not in counts:
            label = "neutral"
        counts[label] += 1

    signal_info = map_sentiment_to_signal(
        counts["positive"], counts["negative"], counts["neutral"]
    )
    logger.info("Signal for %s => %s", t, signal_info)

    return {
        "ticker": t,
        "from": from_date,
        "to": to_date,
        "analyzed": sum(counts.values()),
        "counts": counts,
        "signal": signal_info,
    }
