# backend/tests/test_portfolio.py
import pytest

@pytest.fixture
def mock_prices(monkeypatch):
    # Patch functions where they are USED (inside portfolio.py)
    import app.services.portfolio as portfolio_svc

    monkeypatch.setattr(
        portfolio_svc, "get_quote",
        lambda t: {"AAPL": 200.0, "MSFT": 300.0}.get(t, 100.0),
        raising=False,
    )
    monkeypatch.setattr(
        portfolio_svc, "get_candles_close",
        lambda t, days=60: [100 + i for i in range(min(days, 30))],
        raising=False,
    )
    return True

def test_portfolio_flow(client, mock_prices):
    # seed cash
    r = client.post("/api/portfolio/cash", params={"amount": 10000})
    assert r.status_code == 200 and r.json()["cash"] == 10000.0

    # create holdings
    r = client.post("/api/portfolio/holdings", json={"ticker": "AAPL", "quantity": 10, "avg_cost": 180})
    assert r.status_code == 200
    r = client.post("/api/portfolio/holdings", json={"ticker": "MSFT", "quantity": 5, "avg_cost": 300})
    assert r.status_code == 200

    # list holdings
    r = client.get("/api/portfolio/holdings")
    assert r.status_code == 200
    holdings = {h["ticker"]: h for h in r.json()}
    assert holdings["AAPL"]["market_value"] == 200.0 * 10
    assert holdings["MSFT"]["market_value"] == 300.0 * 5

    # metrics
    r = client.get("/api/portfolio/metrics")
    assert r.status_code == 200
    m = r.json()
    assert pytest.approx(m["total_value"], rel=1e-3) == 2000 + 1500  # 3500

    # preview rebalance (dry-run)
    body = {"max_weight": 0.6, "target_vol": 0.2, "cash_buffer_pct": 0.1, "top_n_news": 3}
    r = client.post("/api/portfolio/rebalance/preview", json=body, params={"slippage_bps": 10})
    assert r.status_code == 200
    preview = r.json()
    assert "suggested_weights" in preview and "trades" in preview

    # execute rebalance (commit=false)
    r = client.post("/api/portfolio/rebalance/execute", json=body, params={"commit": False, "slippage_bps": 10})
    assert r.status_code == 200
    assert r.json()["mode"] == "dry_run"

    # execute rebalance (commit=true)
    r = client.post("/api/portfolio/rebalance/execute", json=body, params={"commit": True, "slippage_bps": 10})
    assert r.status_code == 200
    exe = r.json()
    assert exe["mode"] == "committed"
    assert "execution" in exe
    assert "cash_after" in exe["execution"]
