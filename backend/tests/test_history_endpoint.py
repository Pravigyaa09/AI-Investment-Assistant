# backend/tests/test_history_endpoint.py
def test_history_works_with_fallbacks(client, monkeypatch):
    # Force synthetic path by disabling candles (fast, deterministic)
    import os
    os.environ["DISABLE_CANDLES"] = "1"
    r = client.get("/api/history", params={"ticker": "AAPL", "days": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert len(data["closes"]) == 10
