from fastapi import APIRouter, Query
import requests
from logger import get_logger
from utils.sentiment_model import analyze_sentiment

router = APIRouter()
logger = get_logger(__name__)

FINNHUB_API_KEY = "d29mffpr01qvhsfu2magd29mffpr01qvhsfu2mb0"

@router.get("/news")
def get_news(ticker: str = Query(..., description="Stock ticker symbol")):
    ticker = ticker.strip().upper()
    logger.info(f"Fetching news and analyzing sentiment for ticker: {ticker}")
    
    try:
        # Fetch past week's news
        url = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={ticker}&from=2025-07-30&to=2025-08-06&token={FINNHUB_API_KEY}"
        )
        response = requests.get(url)
        response.raise_for_status()

        news_items = response.json()[:5]  # Top 5 articles
        articles = []

        for article in news_items:
            title = article.get("headline", "")
            sentiment = analyze_sentiment(title) if title else "unknown"

            articles.append({
                "title": title,
                "sentiment": sentiment,
                "link": article.get("url"),
                "published": article.get("datetime"),
                "source": article.get("source")
            })

        return {"ticker": ticker, "articles": articles}
    
    except Exception as e:
        logger.exception("Error fetching or processing news")
        return {"error": str(e)}
