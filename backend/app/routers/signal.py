# backend/app/routers/signal.py (only the relevant additions)
from fastapi import APIRouter, HTTPException, Query
from typing import Dict
from app.services.finnhub_client import fetch_company_news
from app.nlp.finbert import FinBERT

# NEW: import trend helpers
from app.services.market_data import get_candles_close, simple_trend_score

router = APIRouter(tags=["signal"])

def simple_sentiment(text: str):
    t = (text or "").lower()
    pos_kw = ["surge","surges","jump","jumps","beats","rises","rise","gain","gains","bull","profit","record","soar","soars"]
    neg_kw = ["falls","fall","misses","slump","slumps","drop","drops","bear","loss","losses","down","plunge","plunges","cut","cuts","weak"]
    if any(k in t for k in pos_kw): return {"label":"positive","score":0.66}
    if any(k in t for k in neg_kw): return {"label":"negative","score":0.66}
    return {"label":"neutral","score":0.5}

@router.get("/signal")
def signal_from_news(ticker: str = Query("AAPL", min_length=1, max_length=15)):
    # 1) News + sentiment
    try:
        news = fetch_company_news(ticker, count=25)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"news fetch failed: {e}")
    counts = {"positive":0,"neutral":0,"negative":0}
    for n in news:
        title = n.get("title") or ""
        try:
            pred = FinBERT.predict(title) if FinBERT.is_available() else simple_sentiment(title)
        except Exception:
            pred = simple_sentiment(title)
        counts[pred["label"]] += 1
    total = max(1, sum(counts.values()))
    pos = counts["positive"]/total
    neg = counts["negative"]/total

    # 2) Price trend (last 60 days)
    try:
        closes = get_candles_close(ticker, days=60)
        trend = simple_trend_score(closes)   # [-1..+1]
    except Exception:
        trend = 0.0

    # 3) Combine into action
    # Sentiment component: (pos - neg) in [-1..+1]
    sent_component = pos - neg
    # Weighted combo (feel free to tweak weights)
    combo = 0.6 * sent_component + 0.4 * trend

    if combo >= 0.25:
        action, confidence = "Buy", round(min(1.0, combo), 3)
    elif combo <= -0.20:
        action, confidence = "Sell", round(min(1.0, -combo), 3)
    else:
        action, confidence = "Hold", round(1.0 - abs(combo), 3)

    return {
        "ticker": ticker.upper().strip(),
        "counts": counts,
        "trend_score": round(trend, 3),
        "sent_score": round(sent_component, 3),
        "combo_score": round(combo, 3),
        "action": action,
        "confidence": confidence,
        "articles_used": min(total, 25),
    }
