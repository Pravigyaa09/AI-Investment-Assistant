# 🚀 ML Trade Recommender - Quick Start Guide

## Overview

This guide walks you through setting up and testing the ML-based trade recommender system from scratch.

---

## Prerequisites

1. **Backend running** on `http://localhost:8000`
2. **Python packages installed**:
   ```bash
   pip install scikit-learn joblib numpy
   ```
3. **API keys configured** (Finnhub, etc.)

---

## Step 1: Check Initial Status

Before training, verify the system is ready:

```bash
curl http://localhost:8000/api/ml/status
```

**Expected response** (no model yet):
```json
{
  "trained": false,
  "model_path": "/.../backend/app/ml/_artifacts/recommender.pkl",
  "message": "No trained model found. Use POST /ml/train to train a model.",
  "features": null,
  "horizon_days": null
}
```

---

## Step 2: Train the Model

### Option A: Using Standalone Script (Recommended for first time)

```bash
cd backend
python train_model.py
```

**Interactive prompts:**
```
🧠 ML TRADE RECOMMENDER - MODEL TRAINING
======================================================================

📊 Configuration:
   Tickers: AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, JPM, BAC, WMT (10 total)
   Lookback days: 240
   Horizon days: 21
   Model output: /.../recommender.pkl

======================================================================

🚀 Start training? (y/n): y

⏳ Training started... This may take several minutes.
```

**Custom training:**
```bash
# Train with specific tickers
python train_model.py --tickers AAPL MSFT TSLA NVDA GOOGL

# Train with more historical data
python train_model.py --lookback-days 365 --horizon-days 30
```

**Expected output:**
```
======================================================================
✅ SUCCESS - Model trained and saved!
======================================================================

📁 Model saved to: /.../recommender.pkl

📊 Model components:
   - Classifier: Logistic Regression (Buy/Sell/Hold predictions)
   - Regressor: Random Forest (Expected return forecasts)

💡 Next steps:
   1. Start your FastAPI server
   2. Test the model: GET /api/ml/recommend?ticker=AAPL
   3. Check status: GET /api/ml/status
```

---

### Option B: Using API Endpoint (Background training)

```bash
curl -X POST http://localhost:8000/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    "lookback_days": 240,
    "horizon_days": 21
  }'
```

**Response:**
```json
{
  "status": "training_started",
  "message": "Model training started for 5 tickers",
  "config": {
    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    "lookback_days": 240,
    "horizon_days": 21
  },
  "note": "Training is running in the background. Use GET /ml/status to check completion."
}
```

**Monitor progress:**
```bash
# Check every 30 seconds
watch -n 30 'curl -s http://localhost:8000/api/ml/status | jq'
```

---

## Step 3: Verify Model is Trained

```bash
curl http://localhost:8000/api/ml/status
```

**Expected response** (model trained):
```json
{
  "trained": true,
  "model_path": "/.../recommender.pkl",
  "message": "Trained ML model available",
  "features": [
    "trend", "vol_ann", "rsi14", "sma20_ratio", "sma50_ratio",
    "ret_1", "ret_5", "ret_10", "ret_20",
    "news_pos_mean", "news_pos_max", "news_pos_min",
    "news_neu_mean", "news_neu_max", "news_neu_min",
    "news_neg_mean", "news_neg_max", "news_neg_min",
    "news_count"
  ],
  "horizon_days": 21,
  "models": {
    "classifier": "Pipeline",
    "regressor": "RandomForestRegressor"
  }
}
```

---

## Step 4: Test ML Recommendations

### Single Ticker

```bash
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL&horizon_days=21" | jq
```

**Expected response:**
```json
{
  "ticker": "AAPL",
  "action": "Buy",
  "confidence": 0.7845,
  "expected_return_h": 0.0324,
  "risk": {
    "vol_annual": 0.256734,
    "vol_daily": 0.016187,
    "sigma_h": 0.074197,
    "var95_h": 0.122425
  },
  "features_used": {
    "trend": 0.0234,
    "vol_ann": 0.2567,
    "rsi14": 62.45,
    "sma20_ratio": 0.0112,
    "sma50_ratio": 0.0345,
    "ret_1": 0.0023,
    "ret_5": 0.0156,
    "ret_10": 0.0298,
    "ret_20": 0.0512,
    "news_pos_mean": 0.6234,
    "news_pos_max": 0.8901,
    "news_pos_min": 0.3456,
    "news_neu_mean": 0.2345,
    "news_neu_max": 0.4567,
    "news_neu_min": 0.1234,
    "news_neg_mean": 0.1421,
    "news_neg_max": 0.3210,
    "news_neg_min": 0.0456,
    "news_count": 12.0
  },
  "sentiments": [
    {
      "title": "Apple reports strong earnings...",
      "label": "positive",
      "scores": {"pos": 0.89, "neu": 0.08, "neg": 0.03},
      "url": "https://..."
    },
    ...
  ],
  "provider": "ml"
}
```

**Key fields:**
- `action`: Buy/Hold/Sell
- `confidence`: 0-1 (higher = more confident)
- `expected_return_h`: Expected return over horizon (21 days)
- `provider`: "ml" (using trained model) or "rules" (fallback)

---

### Multiple Tickers

```bash
curl "http://localhost:8000/api/ml/recommend?tickers=AAPL,MSFT,TSLA&horizon_days=21" | jq
```

**Expected response:**
```json
{
  "count": 3,
  "results": [
    {
      "ticker": "AAPL",
      "action": "Buy",
      "confidence": 0.7845,
      ...
    },
    {
      "ticker": "MSFT",
      "action": "Hold",
      "confidence": 0.6234,
      ...
    },
    {
      "ticker": "TSLA",
      "action": "Sell",
      "confidence": 0.7123,
      ...
    }
  ]
}
```

---

### POST Method (Better for many tickers)

```bash
curl -X POST http://localhost:8000/api/ml/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"],
    "horizon_days": 21
  }' | jq
```

---

## Step 5: Interpret Results

### Understanding Confidence Scores

- **High confidence (0.8-1.0)**: Strong signal, model is very confident
  - ✅ **Action**: Consider acting on recommendation

- **Medium confidence (0.6-0.8)**: Moderate signal
  - ⚠️ **Action**: Use with caution, cross-check with other indicators

- **Low confidence (<0.6)**: Weak signal
  - ❌ **Action**: Probably ignore, or default to "Hold"

### Understanding Risk Metrics

```json
"risk": {
  "vol_annual": 0.2567,     // 25.67% annualized volatility
  "vol_daily": 0.0162,      // 1.62% daily volatility
  "sigma_h": 0.0742,        // 7.42% volatility over horizon
  "var95_h": 0.1224         // 12.24% Value at Risk (95%)
}
```

- **vol_annual**: Higher = more volatile stock
- **var95_h**: 95% chance you won't lose more than this % over horizon
  - If `var95_h = 0.12`, there's a 5% chance of losing >12% in 21 days

### Decision Logic

**Good buy signal:**
```
action = "Buy"
confidence > 0.75
expected_return_h > var95_h * 0.5
```

**Risky buy:**
```
action = "Buy"
confidence > 0.7
expected_return_h < var95_h
```
→ High expected return but also high risk

**Safe hold:**
```
action = "Hold"
confidence > 0.7
expected_return_h ~ 0
```
→ Model suggests no strong movement

---

## Step 6: Test Fallback Behavior

Temporarily rename the model file to test rule-based fallback:

```bash
cd backend/app/ml/_artifacts
mv recommender.pkl recommender.pkl.backup

# Test again
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL" | jq
```

**Expected response** (rule-based):
```json
{
  "ticker": "AAPL",
  "action": "Hold",
  "confidence": 0.65,
  "expected_return_h": 0.0123,
  "provider": "rules",    // ← Note: fallback to rules
  ...
}
```

**Restore model:**
```bash
mv recommender.pkl.backup recommender.pkl
```

---

## Step 7: Frontend Integration

### Using the Frontend API Service

```javascript
import api from '@/services/api';

// Get single recommendation
const result = await api.getMLRecommendation('AAPL', 21);
console.log(result.action);        // "Buy"
console.log(result.confidence);    // 0.7845
console.log(result.provider);      // "ml"

// Get multiple recommendations
const results = await api.getMLRecommendations(['AAPL', 'MSFT', 'TSLA'], 21);
console.log(results.count);        // 3
console.log(results.results);      // Array of recommendations

// Check model status
const status = await api.getMLModelStatus();
console.log(status.trained);       // true
console.log(status.features);      // Array of 18 feature names

// Train new model (requires auth)
const trainResult = await api.trainMLModel(
  ['AAPL', 'MSFT', 'GOOGL'],  // tickers
  240,                         // lookback_days
  21                           // horizon_days
);
console.log(trainResult.status);  // "training_started"
```

---

## Troubleshooting

### Issue: "No training data collected"

**Cause**: Tickers are invalid or insufficient historical data

**Solution:**
```bash
# Use well-known, liquid tickers
python train_model.py --tickers AAPL MSFT GOOGL AMZN

# Or increase lookback
python train_model.py --lookback-days 365
```

---

### Issue: Training is very slow

**Cause**: Too many tickers or long lookback period

**Solution:**
```bash
# Start with fewer tickers
python train_model.py --tickers AAPL MSFT GOOGL --lookback-days 180

# Gradually increase once working
```

---

### Issue: Low confidence scores

**Cause**: Model hasn't learned strong patterns

**Solution:**
1. **Retrain with more diverse tickers:**
   ```bash
   python train_model.py --tickers AAPL MSFT GOOGL AMZN TSLA NVDA META \
                                    JPM BAC WMT TGT DIS NFLX
   ```

2. **Increase lookback period:**
   ```bash
   python train_model.py --lookback-days 365
   ```

3. **Use ensemble of models** (future enhancement)

---

### Issue: API rate limits

**Cause**: Too many API calls during training

**Solution:**
```bash
# Reduce tickers
python train_model.py --tickers AAPL MSFT GOOGL

# OR reduce lookback
python train_model.py --lookback-days 120

# OR wait 1-2 minutes and retry
```

---

## Next Steps

### 1. Integrate into StockAnalysis Page

Update [StockAnalysis.jsx](trading-platform-frontend/src/pages/StockAnalysis.jsx):

```javascript
const fetchMLRecommendation = async (ticker) => {
  try {
    const result = await api.getMLRecommendation(ticker, 21);
    setMLData(result);
  } catch (err) {
    console.error('ML fetch failed:', err);
  }
};
```

### 2. Add ML Badge

Show ML vs. rule-based indicator:

```jsx
{analysis.provider === 'ml' && (
  <span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded text-xs">
    ML Model
  </span>
)}
{analysis.provider === 'rules' && (
  <span className="bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded text-xs">
    Heuristic Fallback
  </span>
)}
```

### 3. Display Confidence

```jsx
<div className="flex items-center gap-2">
  <span>Confidence:</span>
  <div className="flex-1 bg-gray-700 rounded-full h-2">
    <div
      className="bg-blue-500 h-2 rounded-full"
      style={{ width: `${analysis.confidence * 100}%` }}
    />
  </div>
  <span>{(analysis.confidence * 100).toFixed(1)}%</span>
</div>
```

### 4. Retrain Regularly

Set up a cron job or scheduled task:

```bash
# Weekly retraining
0 0 * * 0 cd /path/to/backend && python train_model.py
```

---

## Summary

✅ **Completed:**
1. ML infrastructure (features, training, inference, model storage)
2. API endpoints (`/ml/recommend`, `/ml/train`, `/ml/status`)
3. Standalone training script
4. Frontend API integration
5. Documentation

🚀 **Ready to use:**
- Train model: `python train_model.py`
- Get recommendations: `GET /api/ml/recommend?ticker=AAPL`
- Check status: `GET /api/ml/status`

📊 **Production checklist:**
- [ ] Train with 20+ diverse tickers
- [ ] Set up weekly retraining schedule
- [ ] Monitor confidence scores
- [ ] Add evaluation metrics (accuracy, F1, etc.)
- [ ] Implement A/B testing vs. rule-based

---

**Disclaimer**: This is NOT financial advice. All predictions are for educational purposes only.
