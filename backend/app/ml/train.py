# backend/app/ml/train.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit

from app.ml.features import build_features
from app.ml.model_store import save_model
from app.services.market_data import get_candles_close

def _forward_return(closes: List[float], idx: int, h: int) -> Optional[float]:
    if idx + h >= len(closes): return None
    p0, p1 = closes[idx], closes[idx + h]
    return (p1 / p0) - 1.0 if p0 > 0 else None

def _label_from_return(r: float, buy_th=0.01, sell_th=-0.01) -> str:
    if r >= buy_th:  return "Buy"
    if r <= sell_th: return "Sell"
    return "Hold"

def _collect_series(ticker: str, days: int = 400) -> List[float]:
    closes = get_candles_close(ticker, days=days)
    return closes

def _collect_dataset(
    tickers: List[str],
    *,
    lookback_days: int = 200,
    horizon_days: int = 21,
) -> Tuple[List[Dict[str,float]], List[str], List[float], List[str]]:
    X, y_class, y_reg, feats_seen = [], [], [], set()
    for t in tickers:
        closes = _collect_series(t, days=lookback_days + horizon_days + 40)
        if len(closes) < 60:
            continue
        # walk through time; each step rebuild_features at that point
        # to keep runtime sane, sample every ~3 days
        for i in range(40, len(closes) - horizon_days, 3):
            # temporarily monkey-patch: we want features "as of" i
            # simple hack: slice closes in memory (feature builder uses last N closes)
            def build_snapshot():
                from app.ml.features import build_features as bf
                # use smaller top_n_news to be gentle on API
                return bf(t, lookback_days=120, news_window_days=2, top_n_news=6)
            fp = build_snapshot()
            xr = fp.X
            for k in xr.keys(): feats_seen.add(k)
            fr = _forward_return(closes, i, horizon_days)
            if fr is None: continue
            X.append(xr)
            y_reg.append(float(fr))
            y_class.append(_label_from_return(fr))
    feat_list = sorted(list(feats_seen))
    return X, y_class, y_reg, feat_list

def train_and_save(
    tickers: List[str],
    *,
    lookback_days: int = 240,
    horizon_days: int = 21
) -> str:
    X_dicts, y_cls, y_ret, feat_list = _collect_dataset(
        tickers, lookback_days=lookback_days, horizon_days=horizon_days
    )
    if not X_dicts:
        raise RuntimeError("No training data collected")

    # vectorize
    X = np.array([[float(d.get(f, 0.0)) for f in feat_list] for d in X_dicts], dtype=float)

    # classifier (probabilities)
    clf = Pipeline([
        ("scaler", StandardScaler(with_mean=False)),
        ("lr", LogisticRegression(max_iter=200, multi_class="auto"))
    ])
    clf.fit(X, y_cls)

    # regressor (expected forward return)
    reg = RandomForestRegressor(n_estimators=200, random_state=42)
    reg.fit(X, np.array(y_ret, dtype=float))

    bundle = {
        "clf": clf,
        "reg": reg,
        "features": feat_list,
        "horizon_days": horizon_days,
    }
    path = save_model(bundle)
    return path
