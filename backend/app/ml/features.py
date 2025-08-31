# backend/app/ml/features.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

from app.services.market_data import get_candles_close, compute_volatility, simple_trend_score
from app.services.finnhub_client import fetch_company_news

try:
    from app.nlp.finbert import FinBERT
    _FINBERT_OK = FinBERT.is_available()
except Exception:
    FinBERT = None  # type: ignore
    _FINBERT_OK = False


@dataclass
class FeaturePack:
    X: Dict[str, float]
    info: Dict  # auxiliary info (closes, sentiment lines, etc.)


def _safe_finbert_scores(title: str) -> Tuple[float, float, float]:
    """Return (pos, neu, neg) probs."""
    if not title:
        return (0.0, 1.0, 0.0)
    if _FINBERT_OK and FinBERT:
        try:
            probs = FinBERT.predict_proba(title)  # expects dict: {positive,neutral,negative}
            return (float(probs.get("positive", 0.0)),
                    float(probs.get("neutral", 1.0)),
                    float(probs.get("negative", 0.0)))
        except Exception:
            pass
    # tiny keyword fallback
    low = title.lower()
    if any(w in low for w in ["surge","jumps","beats","rises","gain","profit","upgrade","record"]):
        return (0.9, 0.1, 0.0)
    if any(w in low for w in ["falls","misses","slump","drop","loss","cuts","downgrade","probe","lawsuit"]):
        return (0.0, 0.2, 0.8)
    return (0.1, 0.8, 0.1)


def _rsi14(closes: List[float]) -> float:
    if len(closes) < 15:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(-14, 0):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else:        losses -= diff
    avg_g = gains / 14.0
    avg_l = losses / 14.0
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


def build_features(
    ticker: str,
    *,
    lookback_days: int = 120,
    news_window_days: int = 3,
    top_n_news: int = 12,
) -> FeaturePack:
    """
    Build ML features for one ticker as of now.
    Returns FeaturePack with X (features) and info for UX.
    """
    t = ticker.upper().strip()

    closes = get_candles_close(t, days=max(lookback_days, 30))
    last = closes[-1] if closes else 0.0
    sma20 = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else last
    sma50 = sum(closes[-50:]) / 50.0 if len(closes) >= 50 else last
    trend = simple_trend_score(closes)
    vol_ann = compute_volatility(closes)
    rsi = _rsi14(closes)

    # simple returns
    def ret(n: int) -> float:
        if len(closes) <= n:
            return 0.0
        c0, c1 = closes[-n-1], closes[-1]
        return (c1 / c0) - 1.0 if c0 > 0 else 0.0

    r1 = ret(1)
    r5 = ret(5)
    r10 = ret(10)
    r20 = ret(20)

    # FinBERT news in recent window
    end_dt = datetime.now(tz=timezone.utc)
    start_dt = end_dt - timedelta(days=news_window_days)
    news = fetch_company_news(t, count=top_n_news, start=start_dt, end=end_dt) or []

    pos_vals, neu_vals, neg_vals = [], [], []
    sentiments = []  # for UI
    for n in news:
        title = n.get("title") or n.get("headline") or ""
        p, u, g = _safe_finbert_scores(title)
        pos_vals.append(p); neu_vals.append(u); neg_vals.append(g)
        label = "positive" if p > max(u, g) else ("negative" if g > max(p, u) else "neutral")
        sentiments.append({"title": title, "label": label, "scores": {"pos": p, "neu": u, "neg": g}, "url": n.get("url")})

    def _agg(xs: List[float]) -> Tuple[float, float, float]:
        if not xs:
            return (0.0, 0.0, 0.0)
        return (float(sum(xs)/len(xs)), float(max(xs)), float(min(xs)))

    pos_mean, pos_max, pos_min = _agg(pos_vals)
    neu_mean, neu_max, neu_min = _agg(neu_vals)
    neg_mean, neg_max, neg_min = _agg(neg_vals)

    X = {
        "trend": trend,
        "vol_ann": vol_ann,
        "rsi14": rsi,
        "sma20_ratio": (last / sma20 - 1.0) if sma20 else 0.0,
        "sma50_ratio": (last / sma50 - 1.0) if sma50 else 0.0,
        "ret_1": r1, "ret_5": r5, "ret_10": r10, "ret_20": r20,
        "news_pos_mean": pos_mean, "news_pos_max": pos_max, "news_pos_min": pos_min,
        "news_neu_mean": neu_mean, "news_neu_max": neu_max, "news_neu_min": neu_min,
        "news_neg_mean": neg_mean, "news_neg_max": neg_max, "news_neg_min": neg_min,
        "news_count": float(len(news)),
    }

    return FeaturePack(
        X=X,
        info={
            "last_close": last,
            "closes": closes[-60:],
            "sentiments": sentiments,
        }
    )
