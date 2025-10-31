#backend/app/ml/recommender.py
from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev
from typing import Dict, List

from app.services import market_data
from app.services.finnhub_client import fetch_company_news

# FinBERT is optional; we fall back to keywords if unavailable
try:
    from app.nlp.finbert import FinBERT
    _FINBERT_READY = getattr(FinBERT, "is_available", lambda: False)()
except Exception:  # pragma: no cover
    FinBERT = None  # type: ignore
    _FINBERT_READY = False


def _safe_daily_stats(closes: List[float]) -> Dict[str, float]:
    """Return {'mu': daily_mean_return, 'sigma': daily_vol} or zeros."""
    clean = [float(c) for c in closes if c and c > 0]
    if len(clean) < 2:
        return {"mu": 0.0, "sigma": 0.0}
    rets = []
    for i in range(1, len(clean)):
        p0, p1 = clean[i - 1], clean[i]
        if p0 > 0:
            rets.append((p1 / p0) - 1.0)
    if len(rets) < 2:
        return {"mu": 0.0, "sigma": 0.0}
    return {"mu": float(mean(rets)), "sigma": float(pstdev(rets))}


def _sentiment_label(title: str) -> str:
    """Run FinBERT if available, otherwise a tiny keyword fallback."""
    title = (title or "").strip()
    if not title:
        return "neutral"
    try:
        if _FINBERT_READY and FinBERT:
            pred = FinBERT.predict(title)
            return (pred or {}).get("label", "neutral")
    except Exception:
        pass
    low = title.lower()
    pos = any(w in low for w in ["surge", "jumps", "beats", "rises", "gain", "profit", "record", "soar"])
    neg = any(w in low for w in ["falls", "misses", "slump", "drop", "loss", "cuts", "plunge"])
    if pos and not neg: return "positive"
    if neg and not pos: return "negative"
    return "neutral"


def recommend_ticker(ticker: str, horizon_days: int = 21, top_n_news: int = 6) -> Dict:
    """
    Heuristic recommender (Phase 6 pre-ML):
      • uses price drift + volatility from recent closes
      • blends with FinBERT headline sentiment
      • returns Buy/Hold/Sell + expected return and risk

    Never raises; returns 'insufficient_data' if we can’t fetch enough.
    """
    t = (ticker or "").upper().strip()
    if not t:
        return {"error": "ticker is required"}

    # --- Prices & returns
    # Ask for a bit more history than the horizon to stabilize stats
    days_back = max(60, horizon_days + 40)
    closes = market_data.get_candles_close(t, days=days_back)
    stats = _safe_daily_stats(closes)
    mu, sigma = stats["mu"], stats["sigma"]

    last_price = market_data.get_quote(t)
    if last_price <= 0 and closes:
        last_price = closes[-1]  # fallback to last close

    # If still no data, bail gracefully
    if last_price <= 0:
        return {
            "ticker": t,
            "status": "insufficient_data",
            "message": "Could not fetch reliable price data for this ticker right now.",
        }

    # Expected return over horizon (geometric mean approximation)
    exp_ret_pct = (1.0 + mu) ** horizon_days - 1.0 if mu else 0.0
    # Risk over horizon (propagate daily stdev)
    risk_horizon_pct = sigma * sqrt(horizon_days) if sigma else 0.0
    risk_annual_pct = sigma * sqrt(252) if sigma else 0.0

    # --- News & sentiment
    news = []
    try:
        news = fetch_company_news(t, count=top_n_news) or []
    except Exception:
        news = []

    sent_counts = {"positive": 0, "neutral": 0, "negative": 0}
    samples = []
    for n in news[:top_n_news]:
        title = n.get("title") or n.get("headline") or ""
        if not title:
            continue
        lab = _sentiment_label(title)
        if lab in sent_counts:
            sent_counts[lab] += 1
        samples.append({"title": title, "label": lab, "url": n.get("url")})

    # Convert labels to a tiny numeric tilt [-1..+1]
    total = max(1, sum(sent_counts.values()))
    tilt = (sent_counts["positive"] - sent_counts["negative"]) / total

    # Blend: add a small sentiment tilt to expected return (scaled by risk)
    exp_ret_blended = exp_ret_pct + 0.25 * tilt * risk_horizon_pct

    # Map to action
    if exp_ret_blended > max(0.02, 0.6 * risk_horizon_pct):
        action = "Buy"
    elif exp_ret_blended < -max(0.01, 0.4 * risk_horizon_pct):
        action = "Sell"
    else:
        action = "Hold"

    expected_price = last_price * (1 + exp_ret_blended)

    return {
        "ticker": t,
        "horizon_days": horizon_days,
        "last_price": round(float(last_price), 4),
        "expected_return_pct": round(float(exp_ret_blended), 4),
        "expected_price": round(float(expected_price), 4),
        "risk_horizon_pct": round(float(risk_horizon_pct), 4),
        "risk_annual_pct": round(float(risk_annual_pct), 4),
        "sentiment_counts": sent_counts,
        "sample_headlines": samples,
        "suggestion": {"action": action},
        "note": "Heuristic pre-ML model. Not financial advice.",
    }
