import yfinance as yf
from datetime import datetime
from utils.sentiment_model import analyze_sentiment  # ⬅️ Import FinBERT wrapper

def get_news(ticker: str, analyze: bool = True):
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news
        news_data = []

        for article in raw_news:
            title = article.get("title")
            sentiment = analyze_sentiment(title) if analyze else "N/A"

            news_data.append({
                "title": title,
                "sentiment": sentiment,
                "link": article.get("link"),
                "published": datetime.fromtimestamp(article.get("providerPublishTime")),
                "source": article.get("publisher")
            })

        return news_data

    except Exception as e:
        return [{"error": str(e)}]
