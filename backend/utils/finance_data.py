# backend/utils/finance_data.py
from datetime import datetime, timezone
from logger import get_logger
import yfinance as yf

logger = get_logger(__name__)

def get_recent_news(ticker: str, limit: int = 5) -> list[dict]:
    """
    Fetch recent news for a ticker via yfinance.

    Returns a list of dicts:
    {
        "headline": str,
        "url": str,
        "publisher": str | None,
        "published_at": str | None,  # ISO-8601 UTC
        "summary": str               # may be empty
    }
    """
    t = (ticker or "").strip().upper()
    if not t:
        logger.warning("get_recent_news called with empty ticker")
        return []

    logger.info("Fetching news for %s", t)

    try:
        stock = yf.Ticker(t)
        items = stock.news or []
    except Exception:
        logger.exception("Error fetching news for %s", t)
        return []

    results: list[dict] = []
    seen_urls = set()

    for item in items:
        title = (item.get("title") or "").strip()
        url = (item.get("link") or "").strip()
        if not title or not url:
            logger.debug("Skipping incomplete article payload: %r", item)
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        ts = item.get("providerPublishTime")
        published_at = None
        if ts:
            # yfinance usually returns seconds; guard for ms just in case
            try:
                if ts > 10**12:  # looks like ms
                    ts = ts / 1000.0
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                published_at = dt.isoformat()
            except Exception:
                logger.debug("Bad providerPublishTime %r for %s", ts, url)

        results.append({
            "headline": title,
            "url": url,
            "publisher": item.get("publisher"),
            "published_at": published_at,
            "summary": (item.get("summary") or "").strip(),  # often empty in yfinance
        })

        if len(results) >= limit:
            break

    logger.info("Fetched %d news items for %s", len(results), t)
    return results
