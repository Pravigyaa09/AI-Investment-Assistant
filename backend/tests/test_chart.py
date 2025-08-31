def test_chart_series_basic(client, monkeypatch):
    # Make candles deterministic by forcing synthetic path
    import os
    os.environ["DISABLE_CANDLES"] = "1"

    r = client.get("/api/chart/series", params={"ticker": "AAPL", "days": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["days"] == 10
    assert data["provider"] == "synthetic"
    assert len(data["points"]) == 10
    # validate shape
    assert "date" in data["points"][0] and "close" in data["points"][0]
