def test_sentiment_keywords(client):
    payload = {"texts": ["Stock jumps to record", "Shares slump after miss", "No big change today"]}
    r = client.post("/api/sentiment", json=payload)
    assert r.status_code == 200
    out = r.json()
    labels = [x["label"] for x in out]
    assert labels == ["positive", "negative", "neutral"]
