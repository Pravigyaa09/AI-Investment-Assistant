# backend/app/services/portfolio.py
from datetime import datetime
from sqlalchemy.orm import Session

from app.db import models
from app.services.market_data import get_quote, get_candles_close, compute_volatility
from app.services.finnhub_client import fetch_company_news
from app.nlp.finbert import FinBERT


# ---------- CRUD / trades ----------

def upsert_holding(db: Session, ticker: str, quantity: float, avg_cost: float) -> models.PortfolioHolding:
    holding = db.query(models.PortfolioHolding).filter_by(ticker=ticker).one_or_none()
    if holding is None:
        holding = models.PortfolioHolding(ticker=ticker, quantity=quantity, avg_cost=avg_cost)
        db.add(holding)
    else:
        holding.quantity = quantity
        holding.avg_cost = avg_cost
    holding.last_price = get_quote(ticker)
    holding.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(holding)
    return holding


def record_trade(db: Session, ticker: str, side: str, qty: float, price: float | None = None) -> models.Trade:
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if price is None:
        price = get_quote(ticker)

    holding = db.query(models.PortfolioHolding).filter_by(ticker=ticker).one_or_none()
    if holding is None:
        holding = models.PortfolioHolding(ticker=ticker, quantity=0.0, avg_cost=0.0, last_price=price)
        db.add(holding)

    # apply trade to holding
    if side == "BUY":
        new_qty = holding.quantity + qty
        holding.avg_cost = ((holding.avg_cost * holding.quantity) + price * qty) / max(new_qty, 1e-9)
        holding.quantity = new_qty
    else:  # SELL
        holding.quantity = max(0.0, holding.quantity - qty)
        if holding.quantity == 0:
            holding.avg_cost = 0.0

    holding.last_price = price
    holding.updated_at = datetime.utcnow()

    tr = models.Trade(ticker=ticker, side=side, qty=qty, price=price, holding=holding)
    db.add(tr)
    db.commit()
    db.refresh(holding)
    db.refresh(tr)
    return tr


# ---------- cash helpers ----------

def get_cash(db: Session) -> float:
    row = db.query(models.PortfolioCash).filter_by(id=1).one_or_none()
    return float(row.balance) if row else 0.0


def set_cash(db: Session, amount: float) -> float:
    row = db.query(models.PortfolioCash).filter_by(id=1).one_or_none()
    if row is None:
        row = models.PortfolioCash(id=1, balance=float(amount))
        db.add(row)
    else:
        row.balance = float(amount)
    db.commit()
    db.refresh(row)
    return float(row.balance)


# ---------- snapshots / metrics ----------

def get_holdings_snapshot(db: Session) -> dict:
    rows = db.query(models.PortfolioHolding).all()
    snap: dict[str, dict] = {}
    for h in rows:
        price = get_quote(h.ticker)
        mv = price * h.quantity
        cost = h.avg_cost * h.quantity
        pnl_abs = mv - cost
        pnl_pct = (pnl_abs / cost) if cost > 0 else 0.0
        snap[h.ticker] = {
            "ticker": h.ticker,
            "quantity": h.quantity,
            "avg_cost": h.avg_cost,
            "last_price": price,
            "market_value": mv,
            "pnl_abs": pnl_abs,
            "pnl_pct": pnl_pct,
        }
    return snap


def compute_weights(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values()) or 1.0
    return {k: v / total for k, v in values.items()}


def portfolio_metrics(db: Session) -> tuple[dict, dict, float, float, float]:
    snap = get_holdings_snapshot(db)
    values = {t: snap[t]["market_value"] for t in snap}
    costs = {t: snap[t]["avg_cost"] * snap[t]["quantity"] for t in snap}
    total_value = sum(values.values())
    total_cost = sum(costs.values())
    pnl_abs = total_value - total_cost
    pnl_pct = (pnl_abs / total_cost) if total_cost > 0 else 0.0

    weights = compute_weights(values)

    # risk: independent asset vol -> naive portfolio vol (sqrt(sum(w^2 * vol^2)))
    asset_vol = {}
    for t in snap:
        closes = get_candles_close(t, days=60)
        asset_vol[t] = compute_volatility(closes)
    port_vol = (sum((weights[t] ** 2) * (asset_vol[t] ** 2) for t in weights)) ** 0.5 if weights else 0.0
    return snap, weights, port_vol, pnl_abs, pnl_pct


# ---------- rebalance helpers ----------

def _current_values(db: Session) -> dict[str, float]:
    snap = get_holdings_snapshot(db)
    return {t: snap[t]["market_value"] for t in snap}


def compute_rebalance_trades(db: Session, target_weights: dict[str, float], slippage_bps: int = 10):
    """
    Returns a list of dicts: {ticker, side, qty, est_price, est_value}
    Does NOT commit trades. Uses current quotes and desired weights.
    Slippage in basis points (10 bps = 0.10%).
    """
    values_now = _current_values(db)
    cash_now = get_cash(db)
    total_portfolio = sum(values_now.values()) + cash_now
    if total_portfolio <= 0:
        return []

    trades = []
    for t, tgt_w in target_weights.items():
        price = get_quote(t)
        curr_val = values_now.get(t, 0.0)
        tgt_val = max(0.0, tgt_w) * total_portfolio
        delta_val = tgt_val - curr_val
        if abs(delta_val) < max(1.0, 0.001 * total_portfolio):  # ignore tiny dust
            continue
        # Apply slippage (worse price for us)
        price_adj = price * (1 + (slippage_bps / 10_000) * (1 if delta_val > 0 else -1))
        qty = round(abs(delta_val) / max(price_adj, 1e-9), 3)
        trades.append({
            "ticker": t,
            "side": "BUY" if delta_val > 0 else "SELL",
            "qty": qty,
            "est_price": round(price_adj, 4),
            "est_value": round(qty * price_adj, 2),
        })
    return trades


def execute_trades(db: Session, trades: list[dict]) -> dict:
    """
    Commits BUY/SELL trades at provided est_price and qty.
    Adjusts holdings and cash balance.
    """
    cash = get_cash(db)
    spent = 0.0
    received = 0.0
    results = []

    for tr in trades:
        t = tr["ticker"]
        side = tr["side"].upper()
        qty = float(tr["qty"])
        price = float(tr["est_price"])
        value = qty * price

        if side == "BUY" and cash < value:
            # skip buys we can't fund
            results.append({**tr, "status": "skipped_insufficient_cash"})
            continue

        # record trade updates holding & avg cost
        record_trade(db, t, side, qty, price)

        if side == "BUY":
            cash -= value
            spent += value
        else:
            cash += value
            received += value

        results.append({**tr, "status": "filled"})

    set_cash(db, cash)
    return {
        "filled": [r for r in results if r["status"] == "filled"],
        "skipped": [r for r in results if r["status"].startswith("skipped")],
        "cash_after": round(cash, 2),
        "spent": round(spent, 2),
        "received": round(received, 2),
    }


# ---------- sentiment & momentum for suggestions ----------

def _keyword_fallback(text: str) -> dict:
    t = (text or "").lower()
    pos = ["surge", "jumps", "beats", "rises", "gain", "bull", "profit", "record", "soar"]
    neg = ["falls", "misses", "slump", "drop", "bear", "loss", "down", "plunge", "cut"]
    if any(w in t for w in pos):
        return {"label": "positive", "score": 0.66}
    if any(w in t for w in neg):
        return {"label": "negative", "score": 0.66}
    return {"label": "neutral", "score": 0.5}


def _sentiment_score(ticker: str, top_n: int = 5) -> tuple[str, float]:
    # +1 for positive, -1 for negative, 0 neutral; average over top_n
    news = fetch_company_news(ticker, count=top_n)
    scores = []
    for n in news:
        title = n.get("title") or ""
        try:
            if FinBERT.is_available():
                pred = FinBERT.predict(title)
            else:
                pred = _keyword_fallback(title)
        except Exception:
            pred = _keyword_fallback(title)
        label = pred["label"]
        scores.append(1 if label == "positive" else (-1 if label == "negative" else 0))
    if not scores:
        return "neutral", 0.0
    avg = sum(scores) / len(scores)
    label = "positive" if avg > 0.25 else ("negative" if avg < -0.25 else "neutral")
    return label, avg


def _momentum_30d(ticker: str) -> float:
    closes = get_candles_close(ticker, days=30)
    if len(closes) < 2 or closes[0] <= 0:
        return 0.0
    return (closes[-1] - closes[0]) / closes[0]


def suggest_weights(db: Session, max_weight: float, target_vol: float, cash_buffer_pct: float, top_n_news: int) -> tuple[dict, list[dict]]:
    snap, weights, port_vol, _, _ = portfolio_metrics(db)
    tickers = list(snap.keys())
    if not tickers:
        return {}, []

    # base target: current weights; tilt by sentiment (+/- 5-10%) and momentum (+/- 5-10%)
    suggested: dict[str, float] = {}
    actions: list[dict] = []

    for t in tickers:
        curr_w = weights.get(t, 0.0)
        sent_label, sent_avg = _sentiment_score(t, top_n=top_n_news)
        mom = _momentum_30d(t)  # 30d momentum

        # Sentiment tilt: +/- 7.5% * avg; Momentum tilt: +/- 7.5% * sign
        tilt = 0.075 * sent_avg + 0.075 * (1 if mom > 0 else (-1 if mom < 0 else 0))
        tgt = max(0.0, min(max_weight, curr_w + tilt))

        suggested[t] = tgt
        actions.append({
            "ticker": t,
            "current_weight": round(curr_w, 4),
            "suggested_weight": round(tgt, 4),
            "delta_weight": round(tgt - curr_w, 4),
            "sentiment": sent_label,
            "momentum_30d": round(mom, 4),
        })

    # renormalize to (1 - cash_buffer_pct)
    total = sum(suggested.values()) or 1.0
    scale = max(0.0, 1.0 - max(0.0, min(0.9, cash_buffer_pct))) / total
    suggested = {k: round(v * scale, 4) for k, v in suggested.items()}
    return suggested, actions


# ---------- plan & execute ----------

def plan_and_optionally_execute(
    db: Session,
    max_weight: float,
    target_vol: float,
    cash_buffer_pct: float,
    top_n_news: int,
    slippage_bps: int,
    commit: bool,
):
    suggested, actions = suggest_weights(
        db,
        max_weight=max_weight,
        target_vol=target_vol,
        cash_buffer_pct=cash_buffer_pct,
        top_n_news=top_n_news,
    )
    trades = compute_rebalance_trades(db, suggested, slippage_bps=slippage_bps)
    summary = {"suggested_weights": suggested, "actions": actions, "trades": trades}

    if not commit:
        return {"mode": "dry_run", **summary}

    exec_result = execute_trades(db, trades)
    return {"mode": "committed", **summary, "execution": exec_result}
