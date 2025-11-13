# Stock Recommendation Logic Improvements

## Overview

The recommendation system now intelligently adapts recommendations based on whether you own the stock, providing **contextual advice** instead of generic signals.

---

## What Changed

### Before ❌
- **Always recommended the same action** regardless of ownership
- Only showed: Buy, Sell, or Hold
- Didn't consider user's current portfolio

### After ✅
- **Contextual recommendations** based on ownership
- Shows: Buy, Hold (own), Sell, or Don't Buy (don't own)
- Considers user's portfolio position
- More actionable insights

---

## New Recommendation Logic

### If You **OWN** the Stock

| Sentiment | Action | Reasoning |
|-----------|--------|-----------|
| **Positive** (≥60% positive news) | **HOLD** | Stock is doing well, keep it |
| **Negative** (≥60% negative news) | **SELL** | Stock is struggling, get rid of it |
| **Neutral** | **HOLD** | No strong signal, maintain position |

**Example:**
- You own AAPL
- News is positive (70% positive articles)
- **Recommendation: HOLD** (keep your position)

### If You **DON'T OWN** the Stock

| Sentiment | Action | Reasoning |
|-----------|--------|-----------|
| **Positive** (≥60% positive news) | **BUY** | Stock is doing well, acquire it |
| **Negative** (≥60% negative news) | **DON'T BUY** | Stock is struggling, avoid it |
| **Neutral** | **HOLD** | No strong signal, wait and see |

**Example:**
- You don't own TSLA
- News is negative (65% negative articles)
- **Recommendation: DON'T BUY** (avoid the stock)

---

## How It Works

### Step 1: Check Ownership
```python
# Backend checks if user owns the stock
position = None
if user_id:
    portfolio = await user_repo.get_portfolio(user_id)
    for holding in portfolio.holdings:
        if holding.ticker == ticker:
            position = holding  # User owns it!
```

### Step 2: Analyze News Sentiment
```python
# Count sentiment in recent news articles
counts = {
    "positive": 5,  # 5 positive articles
    "negative": 2,  # 2 negative articles
    "neutral": 1    # 1 neutral article
}
```

### Step 3: Generate Position-Aware Recommendation
```python
action, confidence = _rule_signal(
    pos=5,
    neg=2,
    neu=1,
    has_position=True  # ← This is the key difference!
)
# Returns: ("Hold", 0.714) for owned stock
# Would return: ("Buy", 0.714) if didn't own it
```

### Step 4: Send to Frontend

```json
{
  "ticker": "AAPL",
  "has_position": true,
  "suggestion": {
    "action": "Hold",
    "confidence": 0.714,
    "trend_hint": "uptrend"
  }
}
```

---

## Confidence Scores

The confidence score represents how strong the sentiment is:

- **0.8 - 1.0**: Very Strong Signal (80%+ of news is positive/negative)
- **0.6 - 0.8**: Strong Signal (60%+ of news leans one direction)
- **0.5 - 0.6**: Moderate Signal (barely above threshold)
- **< 0.5**: Weak Signal (mixed/neutral sentiment)

**Example:**
- 8 positive articles, 2 neutral → 80% positive → confidence = 0.80 (Very Strong)
- 6 positive articles, 4 negative → 60% positive → confidence = 0.60 (Strong)

---

## Visual Indicators

### Frontend Display

The frontend now shows different visual styles based on the recommendation:

```
✅ BUY         → Green background, up arrow icon
       (Own stock: not applicable)
       (Don't own: strong positive signal)

⏸️  HOLD        → Yellow background, neutral icon
       (Own stock: neutral sentiment)
       (Don't own: neutral sentiment)

🛑 SELL        → Red background, down arrow icon
       (Own stock: strong negative signal)
       (Don't own: not applicable)

🚫 DON'T BUY    → Red background, alert icon
       (Own stock: not applicable)
       (Don't own: strong negative signal)
```

---

## Examples

### Scenario 1: Own AAPL, Positive News

**Your Portfolio:** 10 shares of AAPL

**News Sentiment:** 7 positive, 1 negative, 2 neutral articles

**Backend Calculation:**
```
positive_ratio = 7/10 = 70%
negative_ratio = 1/10 = 10%
has_position = True (you own AAPL)

Result:
- Positive signal ≥ 60% ✓
- owns stock ✓
→ Action: "Hold"
→ Confidence: 0.714 (70% confidence)
```

**Frontend Display:**
```
┌─────────────────────────────────────┐
│        AAPL - Current Position      │
│                                     │
│              HOLD                   │
│      Confidence: 71.4%              │
│      Current Price: $180.50         │
│      Expected Return: +3.24%        │
└─────────────────────────────────────┘
```

**Meaning:** Your AAPL position is performing well. Keep it.

---

### Scenario 2: Don't Own TSLA, Negative News

**Your Portfolio:** You don't own TSLA

**News Sentiment:** 1 positive, 7 negative, 2 neutral articles

**Backend Calculation:**
```
positive_ratio = 1/10 = 10%
negative_ratio = 7/10 = 70%
has_position = False (you don't own TSLA)

Result:
- Negative signal ≥ 60% ✓
- don't own stock ✓
→ Action: "Don't Buy"
→ Confidence: 0.714 (70% confidence)
```

**Frontend Display:**
```
┌─────────────────────────────────────┐
│      TSLA - Not in Portfolio        │
│                                     │
│           DON'T BUY                 │
│      Confidence: 71.4%              │
│      Current Price: $245.30         │
│      Expected Return: -5.12%        │
└─────────────────────────────────────┘
```

**Meaning:** TSLA is facing headwinds. Don't buy it right now.

---

### Scenario 3: Own MSFT, Neutral News

**Your Portfolio:** 5 shares of MSFT

**News Sentiment:** 3 positive, 3 negative, 2 neutral articles

**Backend Calculation:**
```
positive_ratio = 3/8 = 37.5%
negative_ratio = 3/8 = 37.5%
has_position = True (you own MSFT)

Result:
- Positive signal < 60% ✗
- Negative signal < 60% ✗
→ Action: "Hold"
→ Confidence: 0.25 (weak signal)
```

**Frontend Display:**
```
┌─────────────────────────────────────┐
│       MSFT - Current Position       │
│                                     │
│              HOLD                   │
│      Confidence: 25.0%              │
│      Current Price: $415.60         │
│      Expected Return: +1.05%        │
└─────────────────────────────────────┘
```

**Meaning:** Mixed signals on MSFT. Keep it but monitor closely.

---

## Code Changes

### Backend File: `backend/app/routers/analysis.py`

**Function:** `_rule_signal()` (lines 134-178)

**What Changed:**
- Added `has_position` parameter to track ownership
- Modified logic to return position-aware recommendations
- Added "Don't Buy" action for non-owned stocks with negative sentiment

```python
def _rule_signal(pos: int, neg: int, neu: int, has_position: bool = False):
    # ... (documentation and calculation)

    if has_position:
        # User owns the stock
        if positive_signal:
            return "Hold", conf  # Keep it
        elif negative_signal:
            return "Sell", conf  # Get rid of it
    else:
        # User doesn't own the stock
        if positive_signal:
            return "Buy", conf   # Acquire it
        elif negative_signal:
            return "Don't Buy", conf  # Avoid it
```

**Function Call Update:** (line 248)
```python
# Before
action, conf = _rule_signal(counts["positive"], counts["negative"], counts["neutral"])

# After
action, conf = _rule_signal(
    counts["positive"],
    counts["negative"],
    counts["neutral"],
    has_position=position is not None  # ← Key change!
)
```

### Frontend File: `trading-platform-frontend/src/pages/StockAnalysis.jsx`

**Functions:** `getSuggestionColor()` and `getSuggestionIcon()` (lines 43-61)

**What Changed:**
- Added handling for "Don't Buy" action
- Improved color/icon mapping for better UX
- Now specifically checks for exact action strings

```javascript
const getSuggestionColor = (suggestion) => {
  const lower = suggestion.toLowerCase();
  if (lower === 'buy') return 'green';           // BUY → Green
  if (lower === 'sell') return 'red';            // SELL → Red
  if (lower === "don't buy") return 'red';       // DON'T BUY → Red (warning)
  if (lower === 'hold') return 'yellow';         // HOLD → Yellow
  return 'gray';
};
```

---

## Testing the New Logic

### Test Case 1: Own Stock + Positive News

```bash
# 1. Buy AAPL
curl -X POST http://localhost:8000/api/portfolio/trade \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "ticker": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "price": 150
  }'

# 2. Analyze AAPL (should show HOLD)
curl "http://localhost:8000/api/stocks/AAPL/analysis" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Check response
# {
#   "ticker": "AAPL",
#   "has_position": true,
#   "suggestion": {
#     "action": "Hold",  ← If news is positive
#     "confidence": 0.7,
#     "trend_hint": "uptrend"
#   }
# }
```

### Test Case 2: Don't Own Stock + Negative News

```bash
# 1. Analyze a stock you don't own (e.g., TSLA)
curl "http://localhost:8000/api/stocks/TSLA/analysis" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2. Check response
# {
#   "ticker": "TSLA",
#   "has_position": false,
#   "suggestion": {
#     "action": "Don't Buy",  ← If news is negative
#     "confidence": 0.7,
#     "trend_hint": "downtrend"
#   }
# }
```

---

## Benefits

✅ **More Actionable**: Recommendations now make sense for your situation
✅ **Contextual**: Logic adapts to whether you own the stock
✅ **Intuitive**: "Don't Buy" is clearer than "Sell" for stocks you don't own
✅ **Risk-Aware**: Helps avoid bad purchases and bad holdings
✅ **Confidence-Based**: Shows how strong the signal is

---

## FAQ

**Q: Why "Don't Buy" instead of "Sell"?**
A: Because you can't sell a stock you don't own. "Don't Buy" is more accurate.

**Q: What if I don't authenticate?**
A: The system assumes you don't own any stocks (all recommendations are Buy/Don't Buy/Hold).

**Q: Can I override these recommendations?**
A: Yes! These are suggestions, not rules. Trade at your own discretion.

**Q: How often are recommendations updated?**
A: Every time you analyze a stock. News is fetched fresh from Finnhub.

**Q: Is this financial advice?**
A: No. These are algorithmic suggestions for educational purposes only.

---

## Production Deployment

### Before Deploying

1. **Test with multiple users**
   ```bash
   # Test with User A (owns AAPL)
   # Test with User B (doesn't own AAPL)
   # Verify different recommendations
   ```

2. **Verify news sentiment**
   - Ensure FinBERT is available (or fallback works)
   - Check sentiment scores are reasonable

3. **Monitor recommendations**
   - Track which recommendations users follow
   - Measure success rate over time

### Rollout Plan

1. Deploy backend changes first
2. Verify API returns correct actions
3. Deploy frontend changes
4. Test in staging environment
5. Monitor logs and user feedback

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2024-11-04 | 1.0 | Initial implementation - Position-aware recommendations |

---

**Status**: ✅ Ready for testing
**Last Updated**: November 4, 2024
