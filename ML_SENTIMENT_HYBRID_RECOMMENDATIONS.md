# Hybrid ML + Sentiment-Based Recommendations

## Overview

The ML recommender system now integrates **trained ML models** with **position-aware sentiment analysis** to provide hybrid recommendations. This combines the predictive power of ML with the clarity and interpretability of real-time sentiment analysis.

---

## What Changed

### Before
- ML recommender used only trained model predictions (Buy/Hold/Sell)
- Ignored user portfolio ownership
- No sentiment clarity filtering (could recommend Buy on weak mixed sentiment)
- No distinction between owned and non-owned stocks

### After ✅
- **Hybrid recommendations**: ML prediction + Sentiment analysis
- **Position-aware**: Different recommendations if you own the stock vs don't own it
- **Sentiment clarity checking**: Only triggers Buy/Sell on clear sentiment (40%+ of articles have clear opinion)
- **Component visibility**: Returns both ML and sentiment recommendations separately
- **Blended confidence**: Combines ML confidence with sentiment clarity

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION REQUEST                        │
│   GET /ml/recommend?ticker=AAPL&user_id=xyz                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CHECK USER PORTFOLIO                           │
│  Does user own this stock? → has_position = true/false          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌──────────────────┐    ┌──────────────────┐
        │  ML Prediction   │    │ Sentiment Analysis│
        │  (if model       │    │ • FinBERT scores │
        │   exists)        │    │ • Sentiment index│
        │ • Action: Buy    │    │ • Clarity ratio  │
        │ • Confidence     │    │ sentiment_strength
        └────────┬─────────┘    └────────┬─────────┘
                 │                       │
                 └───────────┬───────────┘
                             ▼
        ┌────────────────────────────────────────┐
        │ Position-Aware Signal Blending         │
        │                                        │
        │ If has_position=true:                 │
        │  • Strong sentiment Buy → Hold        │
        │  • Strong sentiment Sell → Sell       │
        │                                        │
        │ If has_position=false:                │
        │  • Strong sentiment Buy → Buy         │
        │  • Strong sentiment Sell → Don't Buy  │
        │                                        │
        │ Blend ML + Sentiment signals          │
        │ Use highest confidence signal         │
        └────────────────┬───────────────────────┘
                         ▼
        ┌────────────────────────────────────────┐
        │   FINAL RECOMMENDATION                 │
        │                                        │
        │ action: "Buy" | "Hold" | "Sell" |    │
        │         "Don't Buy"                   │
        │ confidence: 0.75 (blended)            │
        │ recommendation_type: "hybrid"         │
        │ has_position: true                    │
        │ ml_recommendation: {...}              │
        │ sentiment_recommendation: {...}       │
        └────────────────────────────────────────┘
```

---

## New Parameters

### GET /ml/recommend

**New Parameters:**
```
user_id (optional): User ID string
  - Enables position-aware recommendations
  - System checks portfolio to see if user owns the stock
  - Without this: uses default has_position=false logic
```

**Example:**
```bash
# Without user context (assumes you don't own stocks)
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL"

# With user context (checks portfolio ownership)
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL&user_id=507f1f77bcf86cd799439011"
```

### POST /ml/recommend

**Updated Request Body:**
```json
{
  "tickers": ["AAPL", "MSFT", "TSLA"],
  "horizon_days": 21,
  "user_id": "507f1f77bcf86cd799439011"  // Optional but enables position-awareness
}
```

---

## Response Structure

### Example Response: AAPL (you own it, positive sentiment)

```json
{
  "ticker": "AAPL",
  "action": "Hold",
  "confidence": 0.68,
  "expected_return_h": 0.0342,
  "risk": {
    "vol_annual": 0.2145,
    "vol_daily": 0.0135,
    "sigma_h": 0.0658,
    "var95_h": 0.1086
  },
  "sentiment_analysis": {
    "sentiment_index": 0.45,           // -1.0 to +1.0
    "sentiment_strength": 0.625,       // 5 clear articles out of 8 (clear!)
    "positive": 5,
    "negative": 0,
    "neutral": 3
  },
  "ml_recommendation": {
    "action": "Buy",
    "confidence": 0.72
  },
  "sentiment_recommendation": {
    "action": "Hold",                  // Position-aware! (you own it → Hold)
    "confidence": 0.28
  },
  "features_used": {
    "trend": 0.045,
    "rsi14": 65.2,
    "ret_5": 0.012,
    "ret_10": 0.025,
    ...
  },
  "sentiments": [
    {
      "label": "positive",
      "score": 0.85
    },
    ...
  ],
  "provider": "ml",
  "recommendation_type": "hybrid",
  "has_position": true,
  "position_aware": true
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| **action** | string | Final recommendation: Buy \| Hold \| Sell \| Don't Buy |
| **confidence** | float | 0.0-1.0, blended ML + sentiment clarity |
| **expected_return_h** | float | Expected return over horizon period |
| **risk** | object | Volatility metrics (annual, daily, VaR) |
| **sentiment_analysis** | object | Sentiment index (-1 to +1) and strength (0-1) |
| **ml_recommendation** | object | What ML model predicts (before position adjustment) |
| **sentiment_recommendation** | object | Position-aware sentiment signal |
| **has_position** | boolean | Whether user owns the stock |
| **position_aware** | boolean | Whether position-aware logic was applied |
| **recommendation_type** | string | "hybrid" (ML + Sentiment) |

---

## Decision Logic

### Sentiment Index Thresholds

```
Sentiment Index: -1.0 (very negative) ← → +1.0 (very positive)

POSITIVE_THRESHOLD = 0.30
NEGATIVE_THRESHOLD = -0.30
MIN_CLARITY = 0.40  (40% of articles must have clear sentiment)
```

### Final Action Decision

**If you OWN the stock (has_position=true):**

| ML Says | Sentiment Index | Clarity | Final Action | Reason |
|---------|-----------------|---------|--------------|--------|
| Buy | > 0.30 | ≥ 0.40 | **Hold** | Stock doing well, keep position |
| Buy | 0.0 to 0.30 | < 0.40 | **Hold** | Mixed sentiment, maintain |
| Sell | < -0.30 | ≥ 0.40 | **Sell** | Strong negative, exit |
| Sell | -0.3 to 0.0 | < 0.40 | **Hold** | Weak signal, monitor |
| Hold | Any | Any | **Hold** | Stay with position |

**If you DON'T own the stock (has_position=false):**

| ML Says | Sentiment Index | Clarity | Final Action | Reason |
|---------|-----------------|---------|--------------|--------|
| Buy | > 0.30 | ≥ 0.40 | **Buy** | Strong positive signal |
| Buy | 0.0 to 0.30 | < 0.40 | **Hold** | Weak sentiment, wait |
| Sell | < -0.30 | ≥ 0.40 | **Don't Buy** | Strong negative, avoid |
| Sell | -0.3 to 0.0 | < 0.40 | **Hold** | Weak signal, wait |
| Hold | Any | Any | **Hold** | Neutral stance |

### Confidence Calculation

```python
# Blended confidence = (ML confidence + Sentiment confidence) / 2
# Where sentiment confidence = abs(sentiment_index) × sentiment_strength

Example:
  ML predicts "Buy" with confidence 0.75
  Sentiment predicts "Buy" with confidence 0.28 (index=0.35 × strength=0.80)
  Final confidence = (0.75 + 0.28) / 2 = 0.515
```

---

## How Position-Aware Logic Works

### Scenario 1: You Own AAPL, Positive News (Sentiment Index: 0.45, Clarity: 62.5%)

**Portfolio Status:** 10 shares of AAPL @ $150 avg cost

**News:** 5 positive, 0 negative, 3 neutral articles
- Positive ratio: 62.5% ✓ (above 40% clarity threshold)
- Sentiment index: 0.45 ✓ (above 0.30 positive threshold)

**ML Prediction:** "Buy" (confidence 0.72)

**Sentiment Prediction (without position awareness):** "Buy" (confidence 0.28)

**Position-Aware Adjustment:**
- User owns the stock (has_position=true)
- Strong positive sentiment detected
- Recommendation: **"Hold"** instead of "Buy"
- Reasoning: "You already own this stock and it's performing well. Keep your position and monitor."

**Final Response:**
```json
{
  "action": "Hold",
  "confidence": 0.50,
  "ml_recommendation": { "action": "Buy", "confidence": 0.72 },
  "sentiment_recommendation": { "action": "Hold", "confidence": 0.28 },
  "has_position": true,
  "position_aware": true
}
```

---

### Scenario 2: You Don't Own TSLA, Negative News (Sentiment Index: -0.42, Clarity: 62.5%)

**Portfolio Status:** No holdings in TSLA

**News:** 1 positive, 0 neutral, 5 negative articles (aggregated from multiple sources)
- Negative ratio: 83% → Sentiment index: -0.42 ✓ (below -0.30 negative threshold)
- Clarity: 100% (all articles have clear sentiment) ✓✓

**ML Prediction:** "Hold" (confidence 0.60)

**Sentiment Prediction (without position awareness):** "Sell" (confidence 0.42)

**Position-Aware Adjustment:**
- User does NOT own the stock (has_position=false)
- Strong negative sentiment detected (index < -0.30)
- Recommendation: **"Don't Buy"** instead of "Sell"
- Reasoning: "TSLA is facing headwinds. Don't buy at this time. Wait for improvement."

**Final Response:**
```json
{
  "action": "Don't Buy",
  "confidence": 0.42,
  "ml_recommendation": { "action": "Hold", "confidence": 0.60 },
  "sentiment_recommendation": { "action": "Don't Buy", "confidence": 0.42 },
  "has_position": false,
  "position_aware": true
}
```

---

### Scenario 3: You Own MSFT, Mixed News (Sentiment Index: -0.05, Clarity: 37.5%)

**Portfolio Status:** 5 shares of MSFT @ $300 avg cost

**News:** 3 positive, 0 neutral, 2 negative articles
- Mixed sentiment (3 positive vs 2 negative)
- Sentiment index: -0.05 (barely negative, not strong)
- Clarity: 100% (all articles clear, but signal is weak)

**ML Prediction:** "Hold" (confidence 0.58)

**Sentiment Prediction (without position awareness):** "Hold" (confidence 0.05)

**Position-Aware Adjustment:**
- User owns the stock (has_position=true)
- Weak/mixed signal (index between -0.30 and +0.30)
- Recommendation: **"Hold"** (no change)
- Reasoning: "Mixed signals on MSFT. Keep your position but monitor closely for clarity."

**Final Response:**
```json
{
  "action": "Hold",
  "confidence": 0.315,
  "ml_recommendation": { "action": "Hold", "confidence": 0.58 },
  "sentiment_recommendation": { "action": "Hold", "confidence": 0.05 },
  "has_position": true,
  "position_aware": true
}
```

---

## Testing the System

### Test 1: Own Stock with Positive Sentiment

```bash
# 1. Buy AAPL to create a position
curl -X POST http://localhost:8000/api/portfolio/trade \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "price": 180
  }'

# 2. Get hybrid recommendation with user context
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL&user_id=YOUR_USER_ID"

# Expected: "Hold" (not "Buy") because you own it and sentiment is positive
```

### Test 2: Don't Own Stock with Negative Sentiment

```bash
# Get recommendation for stock you don't own
curl "http://localhost:8000/api/ml/recommend?ticker=TSLA&user_id=YOUR_USER_ID"

# Expected: "Don't Buy" (if sentiment is negative and clear)
```

### Test 3: Without User Context (Baseline)

```bash
# Compare with non-position-aware recommendation
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL"

# Compare with position-aware version:
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL&user_id=YOUR_USER_ID"
```

---

## Key Features

✅ **Hybrid Intelligence**
- Combines trained ML models with real-time sentiment analysis
- Blends predictive power with interpretability

✅ **Position-Aware**
- Different recommendations if you own the stock vs don't own it
- Avoids suggesting "Buy" when you already own it
- Suggests "Don't Buy" instead of "Sell" for non-owned stocks

✅ **Sentiment Clarity Checking**
- Only triggers strong Buy/Sell on clear sentiment (40%+ of articles have opinion)
- Prevents false signals from weak/mixed sentiment
- Confidence reflects both signal strength AND clarity

✅ **Component Visibility**
- Returns both ML and sentiment recommendations separately
- You can see how each component influenced the final decision
- Transparency into the blending process

✅ **Risk Metrics**
- Includes volatility (annual/daily) and VaR estimates
- Helps users understand the risk profile

---

## Production Considerations

### Before Deploying

1. **Test with multiple users**
   ```bash
   # Test User A (owns AAPL)
   # Test User B (doesn't own AAPL)
   # Verify different recommendations
   ```

2. **Verify sentiment analysis**
   - Check that FinBERT is available (or fallback works)
   - Validate sentiment scores look reasonable

3. **Monitor blending logic**
   - Track which signal (ML or sentiment) wins in close cases
   - Monitor confidence scores are realistic

### Performance Notes

- Each recommendation requires:
  - Feature building from market data (~200ms)
  - News fetching and sentiment analysis (~300ms)
  - ML inference (if model loaded) (~50ms)
  - Portfolio lookup (if user_id provided) (~50ms)
  - **Total: ~600ms per ticker**

---

## Backward Compatibility

✅ All existing endpoints still work:
- GET /ml/recommend?ticker=AAPL (no user context)
- POST /ml/recommend (without user_id)

Returns the same response but with:
- `has_position: false` (assumes you don't own stocks)
- `position_aware: false` (no position-aware logic applied)

---

## Files Modified

### Backend

**backend/app/ml/infer.py** (rewrote entirely)
- Added `_sentiment_fallback()` - keyword-based sentiment fallback
- Added `_sentiment_predict()` - FinBERT or fallback
- Added `_sentiment_index()` - weighted sentiment calculation
- Added `_get_sentiment_analysis()` - fetch and analyze news
- Added `_apply_position_aware_signal()` - position-aware logic
- Modified `recommend()` - now supports user_id and has_position
- Returns hybrid recommendations with component breakdowns

**backend/app/routers/recommender.py** (updated endpoints)
- Added `_check_user_position()` helper
- Modified GET /ml/recommend - added user_id parameter
- Modified POST /ml/recommend - added user_id to request model
- Both now check portfolio ownership and apply position awareness

---

## Next Steps

1. **Test the system** with multiple users and stocks
2. **Monitor recommendation accuracy** in production
3. **Gather user feedback** on decision quality
4. **Fine-tune thresholds** (clarity, sentiment bounds) if needed
5. **Consider retrain**: Eventually retrain ML models with sentiment features

---

## Summary

The system now provides intelligent, position-aware recommendations by combining:

1. **ML Predictions** - learned patterns from historical data
2. **Sentiment Analysis** - current market opinion
3. **Position Awareness** - user's portfolio context
4. **Clarity Filtering** - confidence in the sentiment signal

Result: More actionable, contextualized recommendations that adapt to whether you own the stock or not.

**Status**: ✅ Ready for testing

---

**Created**: November 4, 2024
**Version**: 1.0 - Hybrid ML + Sentiment Integration
