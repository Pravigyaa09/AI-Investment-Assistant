# backend/routes/signal.py
from fastapi import APIRouter, HTTPException, Query
from logger import get_logger
from utils.news_fetcher import fetch_news
from utils.sentiment_model import analyze_sentiment, map_sentiment_to_signal

logger = get_logger(__name__)
router = APIRouter()  # must exist at module top-level

@router.get("")
async def get_trading_signal(
    ticker: str = Query(..., min_length=1, max_length=16, description="Stock ticker symbol"),
):
    """
    Returns Buy/Sell/Hold + confidence based on FinBERT sentiment over recent news.
    Mounted under /api/signal, so this endpoint is /api/signal
    """
    # Normalize/validate ticker
    symbol = ticker.strip().upper()
    if not symbol:
        logger.error("Ticker is empty after normalization")
        raise HTTPException(status_code=400, detail="Ticker is required")

    logger.info("Signal request for ticker=%s", symbol)

    # 1) Fetch recent news articles for the symbol
    try:
        articles = fetch_news(symbol)
    except Exception:
        logger.exception("Failed to fetch news from provider")
        raise HTTPException(status_code=502, detail="Failed to fetch news")

    if not isinstance(articles, list):
        logger.error("News provider returned non-list payload")
        raise HTTPException(status_code=502, detail="Invalid news response")

    # 2) Run sentiment over headlines/summaries
    pos = neg = neu = 0
    processed = 0

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

        processed += 1

    logger.info("%s sentiment counts -> pos=%d neg=%d neu=%d (processed=%d)",
                symbol, pos, neg, neu, processed)

    # 3) Map counts to trading signal
    try:
        signal = map_sentiment_to_signal(pos, neg, neu)
    except Exception:
        logger.exception("Error mapping sentiment to signal")
        raise HTTPException(status_code=500, detail="Signal mapping error")

    # Optional: enrich response with ticker for client convenience
    if isinstance(signal, dict) and "ticker" not in signal:
        signal["ticker"] = symbol

    logger.info("%s signal -> %s", symbol, signal)
    return signal
