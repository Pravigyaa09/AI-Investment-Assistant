import yfinance as yf
from datetime import datetime
import logging

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("finance_data.log")
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def get_recent_news(ticker: str, limit: int = 5):
    logger.info(f"Fetching news for ticker: {ticker}")

    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news[:limit] if stock.news else []
    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        return []

    results = []
    for item in news_items:
        title = item.get("title", "")
        url = item.get("link", "")
        time = item.get("providerPublishTime")

        if time:
            dt = datetime.fromtimestamp(time)
        else:
            dt = None
            logger.warning(f"Missing publish time for article: {title}")

        if not title or not url:
            logger.warning(f"Incomplete article data: {item}")

        results.append((title, url, dt))

    logger.info(f"Fetched {len(results)} news items for {ticker}")
    return results
