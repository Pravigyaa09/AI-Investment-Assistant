# backend/app/routers/analysis.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import pstdev
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.services.market_data import (
    get_quote,
    get_candles_close,
    compute_volatility,
    simple_trend_score,
)
from app.services.finnhub_client import fetch_company_news

# Optional FinBERT (safe if not present)
try:
    from app.nlp.finbert import FinBERT
except Exception:
    FinBERT = None  # type: ignore

router = APIRouter(tags=["analysis"])

# ---------- helpers ----------
def _sentiment_fallback(title: str) -> dict:
    t = (title or "").lower()
    pos = ["surge", "jumps", "beats", "rises", "gain", "bull", "profit", "record", "soar"]
    neg = ["falls", "misses", "slump", "drop", "bear", "loss", "down", "plunge", "cut"]
    if any(w in t for w in pos): return {"label": "positive", "score": 0.66}
    if any(w in t for w in neg): return {"label": "negative", "score": 0.66}
    return {"label": "neutral", "score": 0.5}

def _sentiment(title: str) -> dict:
    try:
        if FinBERT and FinBERT.is_available():
            return FinBERT.predict(title or "")
    except Exception:
        pass
    return _sentiment_fallback(title)

def _daily_returns(closes: List[float]) -> List[float]:
    rets: List[float] = []
    for i in range(1, len(closes)):
        p0, p1 = closes[i-1], closes[i]
        if p0 and p0 > 0:
            rets.append(p1/p0 - 1.0)
    return rets

def _sentiment_index(items: List[dict]) -> float:
    vals: List[float] = []
    for s in items:
        lab = (s.get("label") or "neutral").lower()
        sc = float(s.get("score") or 0.0)
        if lab == "positive": vals.append(+sc)
        elif lab == "negative": vals.append(-sc)
    return sum(vals) / len(vals) if vals else 0.0

def _estimate_return_and_risk(closes: List[float], sentiments: List[dict], horizon_days: int = 21) -> Dict[str, float]:
    """
    Simple forward-return & risk estimate:
      mu = mean of ~60 daily returns
      sigma = stdev of daily returns
      mu_adj = mu + 0.002 * sentiment_index  ([-1..+1] -> ±0.2%/day bump)
      expected(h) = (1+mu_adj)^h - 1
      VaR95 (1d) ≈ max(0, 1.65*sigma - mu_adj)
    """
    window = min(60, max(2, len(closes)-1))
    rets = _daily_returns(closes[-(window+1):])
    mu = sum(rets)/len(rets) if rets else 0.0
    sigma = pstdev(rets) if len(rets) > 1 else 0.0

    s_idx = _sentiment_index(sentiments)  # [-1..+1]
    mu_adj = mu + 0.002 * s_idx

    exp_ret = (1.0 + mu_adj) ** horizon_days - 1.0
    vol_ann = sigma * (252 ** 0.5)
    var_95 = max(0.0, 1.65 * sigma - mu_adj)

    return {
        "expected_return_pct": round(exp_ret * 100.0, 3),
        "risk_vol_ann_pct": round(vol_ann * 100.0, 3),
        "var_95_daily_pct": round(var_95 * 100.0, 3),
        "sentiment_index": round(s_idx, 4),
    }

def _rule_signal(pos: int, neg: int, neu: int) -> tuple[str, float]:
    total = max(1, pos + neg + neu)
    p = pos / total
    n = neg / total
    if p >= 0.70: return "Buy", round(p, 3)
    if n >= 0.60: return "Sell", round(n, 3)
    return "Hold", round(1 - abs(p - n), 3)

def _analyze_one(
    db: Session,
    ticker: str,
    *,
    days: int,
    top_n_news: int,
    horizon_days: int,
) -> Dict:
    t = (ticker or "").upper().strip()
    if not t:
        raise HTTPException(status_code=400, detail="ticker is required")

    price = float(get_quote(t))
    holding = db.query(models.PortfolioHolding).filter_by(ticker=t).one_or_none()
    position = None
    if holding:
        mv = price * holding.quantity
        cost = holding.avg_cost * holding.quantity
        pnl_abs = mv - cost
        pnl_pct = (pnl_abs / cost) if cost > 0 else 0.0
        position = {
            "quantity": holding.quantity,
            "avg_cost": holding.avg_cost,
            "last_price": price,
            "market_value": round(mv, 2),
            "pnl_abs": round(pnl_abs, 2),
            "pnl_pct": round(pnl_pct, 4),
        }

    closes = get_candles_close(t, days=days)
    trend = simple_trend_score(closes)
    vol_ann = compute_volatility(closes)

    # News + FinBERT
    news = fetch_company_news(t, count=top_n_news)
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    sentiments: List[dict] = []
    for n in news:
        pred = _sentiment(n.get("title") or "")
        lab = (pred.get("label") or "neutral").lower()
        if lab in counts:
            counts[lab] += 1
        sentiments.append({
            "title": n.get("title"),
            "label": lab,
            "score": float(pred.get("score") or 0.0),
            "url": n.get("url"),
        })

    est = _estimate_return_and_risk(closes, sentiments, horizon_days=horizon_days)
    action, conf = _rule_signal(counts["positive"], counts["negative"], counts["neutral"])
    combo_hint = "uptrend" if trend > 0 else ("downtrend" if trend < 0 else "flat")

    return {
        "ticker": t,
        "as_of": datetime.now(tz=timezone.utc).isoformat(),
        "position": position,
        "price": price,
        "trend_score": round(trend, 3),
        "volatility_ann": round(vol_ann, 4),
        "news_count": len(news),
        "sentiment_counts": counts,
        "sentiments": sentiments,
        "estimated": est,
        "suggestion": {"action": action, "confidence": conf, "trend_hint": combo_hint},
        "note": "Estimates use recent drift + FinBERT sentiment; not financial advice.",
    }

# ---------- single-ticker ----------
@router.get("/stocks/{ticker}/analysis")
def analyze_stock(
    ticker: str,
    days: int = Query(90, ge=10, le=365),
    top_n_news: int = Query(8, ge=1, le=25),
    horizon_days: int = Query(21, ge=5, le=90),
    db: Session = Depends(get_db),
):
    return _analyze_one(db, ticker, days=days, top_n_news=top_n_news, horizon_days=horizon_days)

# ---------- multi-ticker (batch) ----------
@router.get("/stocks/analysis")
def analyze_stocks_batch(
    tickers: str = Query(..., description="Comma-separated list, e.g. AAPL,MSFT,TSLA"),
    days: int = Query(90, ge=10, le=365),
    top_n_news: int = Query(4, ge=1, le=15),
    horizon_days: int = Query(21, ge=5, le=90),
    db: Session = Depends(get_db),
):
    # parse, de-dup, cap size to protect server
    raw = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    uniq: List[str] = []
    for t in raw:
        if t not in uniq:
            uniq.append(t)
    if not uniq:
        raise HTTPException(status_code=400, detail="no valid tickers provided")
    if len(uniq) > 20:
        uniq = uniq[:20]

    results: List[Dict] = []
    for t in uniq:
        try:
            results.append(_analyze_one(db, t, days=days, top_n_news=top_n_news, horizon_days=horizon_days))
        except HTTPException as he:
            results.append({"ticker": t, "error": he.detail})
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})

    return {"count": len(results), "results": results}

# Keep your debug endpoint
@router.post("/_debug/send-digest")
def _debug_send_digest():
    try:
        from app.tasks.daily_digest import send_morning_digest
        return send_morning_digest()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
