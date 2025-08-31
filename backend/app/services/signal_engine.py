def rule_based_signal(counts: dict) -> tuple[str, float]:
    total = max(1, sum(counts.values()))
    pos = counts.get("positive", 0) / total
    neg = counts.get("negative", 0) / total
    if pos >= 0.70:
        return "Buy", round(pos, 3)
    if neg >= 0.60:
        return "Sell", round(neg, 3)
    return "Hold", round(1 - abs(pos - neg), 3)
