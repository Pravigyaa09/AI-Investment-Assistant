from fastapi import APIRouter, HTTPException, Query
from logger import get_logger
from utils.news_fetcher import fetch_news
from utils.sentiment_model import analyze_sentiment, map_sentiment_to_signal

logger = get_logger(__name__)
router = APIRouter()  # <-- this must exist at top level

@router.get("/signal")
async def get_trading_signal(ticker: str = Query(..., min_length=1, max_length=16)):
    """
    Returns Buy/Sell/Hold + confidence based on FinBERT sentiment over recent news.
    """
    logger.info(f"Signal request for ticker={ticker}")

    try:
        articles = fetch_news(ticker)
    except Exception:
        logger.exception("Failed to fetch news from provider")
        raise HTTPException(status_code=502, detail="Failed to fetch news")

    if not isinstance(articles, list):
        logger.error("News provider returned non-list payload")
        raise HTTPException(status_code=502, detail="Invalid news response")

    pos = neg = neu = 0
    for a in articles:
        headline = (a.get("headline") or a.get("title") or "").strip()
        summary = (a.get("summary") or "").strip()
        text = f"{headline} {summary}".strip()
        if not text:
            continue
        try:
            label = analyze_sentiment(text)
        except Exception:
            logger.exception("Error running FinBERT analyze_sentiment")
            continue

        if label == "positive":
            pos += 1
        elif label == "negative":
            neg += 1
        else:
            neu += 1

    logger.info(f"{ticker} sentiment counts -> pos={pos} neg={neg} neu={neu}")

    try:
        signal = map_sentiment_to_signal(pos, neg, neu)
    except Exception:
        logger.exception("Error mapping sentiment to signal")
        raise HTTPException(status_code=500, detail="Signal mapping error")

    logger.info(f"{ticker} signal -> {signal}")
    return signal
