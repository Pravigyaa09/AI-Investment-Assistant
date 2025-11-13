#backend/app/services/finnhub_client.py
import requests
from datetime import date, timedelta, datetime
from typing import List, Dict
from app.core.config import settings
from app.logger import get_logger

log = get_logger(__name__)

def _demo_article(t: str, reason: str):
    return {
        "ticker": t,
        "title": f"{t} — demo headline ({reason})",
        "source": "demo",
        "url": None,
        "published_at": None,
    }

def fetch_company_news(ticker: str, count: int = 25) -> List[Dict]:
    """Fetch news from Finnhub over a 90-day window. Graceful fallbacks.

    Note: Finnhub free tier has 60 requests/minute limit.
    When hitting rate limits with parallel requests, the system gracefully falls back to demo articles.
    """
    if not settings.FINNHUB_API_KEY:
        return [_demo_article(ticker, "no-api-key")]

    end = date.today()
    start = end - timedelta(days=90)
    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={ticker}&from={start.isoformat()}&to={end.isoformat()}&token={settings.FINNHUB_API_KEY}"
    )

    try:
        # 30s timeout to allow for slow responses during high load/rate limiting
        r = requests.get(url, timeout=30)
        if r.status_code == 429:
            # Rate limited (60 req/min on free tier)
            log.warning(f"Finnhub rate-limited for {ticker}. Free tier allows 60 req/min. Consider pagination or caching.")
            return [_demo_article(ticker, "rate-limited")]
        r.raise_for_status()
        data = r.json() or []
    except requests.Timeout:
        # Timeout - API is slow or overloaded
        log.warning(f"Finnhub timeout for {ticker} (30s). API may be under load. Returning demo article.")
        return [_demo_article(ticker, "timeout")]
    except requests.RequestException as e:
        log.warning(f"Finnhub request failed for {ticker}: {e.__class__.__name__}")
        return [_demo_article(ticker, f"provider-error:{e.__class__.__name__}")]
    except ValueError:
        log.warning(f"Finnhub returned invalid JSON for {ticker}")
        return [_demo_article(ticker, "bad-json")]

    out = []
    for d in data[:count]:
        title = d.get("headline") or d.get("title")
        if not title:
            continue
        ts = d.get("datetime")
        published = datetime.fromtimestamp(ts) if isinstance(ts, (int, float)) else None
        out.append({
            "ticker": ticker,
            "title": title,
            "source": d.get("source"),
            "url": d.get("url"),
            "published_at": published.isoformat() if published else None
        })

    if not out:
        out = [_demo_article(ticker, "no-results")]

    return out
