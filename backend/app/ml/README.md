# 🧠 ML-Based Trade Recommender System

## Overview

The ML Trade Recommender is a **Buy/Sell/Hold classifier** that combines **FinBERT sentiment analysis** and **technical indicators** to predict optimal trading actions. The system uses ensemble learning with both classification (action prediction) and regression (return forecasting).

---

## Architecture

```
📦 app/ml/
 ┣ 📂 _artifacts/           ← Trained models storage
 ┃  ┗ 📜 recommender.pkl    ← Saved model bundle
 ┣ 📜 features.py           ← Feature extraction & preprocessing
 ┣ 📜 train.py              ← Model training pipeline
 ┣ 📜 infer.py              ← Real-time inference engine
 ┣ 📜 model_store.py        ← Model persistence utilities
 ┗ 📜 recommender.py        ← [DEPRECATED] Legacy heuristic recommender
```

---

## Features (18 Total)

### Technical Indicators (11)
- `trend`: Trend score (price vs SMA20 ratio)
- `vol_ann`: Annualized volatility
- `rsi14`: RSI (14-period)
- `sma20_ratio`: Current price / SMA20 - 1
- `sma50_ratio`: Current price / SMA50 - 1
- `ret_1`: 1-day return
- `ret_5`: 5-day return
- `ret_10`: 10-day return
- `ret_20`: 20-day return

### FinBERT Sentiment Features (6)
- `news_pos_mean`: Average positive sentiment score
- `news_pos_max`: Maximum positive sentiment score
- `news_pos_min`: Minimum positive sentiment score
- `news_neu_mean`: Average neutral sentiment score
- `news_neu_max`: Maximum neutral sentiment score
- `news_neu_min`: Minimum neutral sentiment score
- `news_neg_mean`: Average negative sentiment score
- `news_neg_max`: Maximum negative sentiment score
- `news_neg_min`: Minimum negative sentiment score

### Metadata (1)
- `news_count`: Number of news articles analyzed

---

## Training Pipeline

### 1. Data Collection (`train.py`)

```python
from app.ml.train import train_and_save

# Train on multiple tickers
train_and_save(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    lookback_days=240,  # Historical window
    horizon_days=21     # Forward-looking period
)
```

**Process:**
1. For each ticker, fetch historical prices (lookback_days + horizon_days)
2. Walk through time with 3-day steps
3. At each step, extract features "as of" that date
4. Calculate forward return over horizon_days
5. Label: `Buy` (return > 1%), `Sell` (return < -1%), `Hold` (otherwise)

### 2. Feature Extraction (`features.py`)

```python
from app.ml.features import build_features

# Extract features for a ticker
fp = build_features(
    ticker="AAPL",
    lookback_days=120,
    news_window_days=3,
    top_n_news=12
)

# fp.X = dict of 18 features
# fp.info = auxiliary data (closes, sentiments, etc.)
```

### 3. Model Training

**Two models are trained:**

1. **Classifier** (Logistic Regression)
   - Predicts: `Buy`, `Hold`, or `Sell`
   - Returns: Class probabilities for confidence scoring

2. **Regressor** (Random Forest)
   - Predicts: Expected forward return (percentage)
   - Used for: Portfolio optimization and risk assessment

**Pipeline:**
```python
clf = Pipeline([
    ("scaler", StandardScaler(with_mean=False)),
    ("lr", LogisticRegression(max_iter=200, multi_class="auto"))
])

reg = RandomForestRegressor(n_estimators=200, random_state=42)
```

### 4. Model Persistence

```python
from app.ml.model_store import save_model, load_model

# Save
bundle = {
    "clf": trained_classifier,
    "reg": trained_regressor,
    "features": feature_list,
    "horizon_days": 21
}
save_model(bundle)

# Load
bundle = load_model()
```

Saved to: `app/ml/_artifacts/recommender.pkl`

---

## Inference (`infer.py`)

### ML-Based Inference

```python
from app.ml.infer import recommend

result = recommend("AAPL", horizon_days=21)
```

**Response:**
```json
{
  "ticker": "AAPL",
  "action": "Buy",
  "confidence": 0.7845,
  "expected_return_h": 0.0324,
  "risk": {
    "vol_annual": 0.2567,
    "vol_daily": 0.0162,
    "sigma_h": 0.0742,
    "var95_h": 0.1224
  },
  "features_used": { ... },
  "sentiments": [ ... ],
  "provider": "ml"
}
```

### Rule-Based Fallback

If no trained model exists:
```json
{
  "provider": "rules",
  "action": "Hold",
  "confidence": 0.65,
  ...
}
```

---

## API Endpoints

### 1. Get Recommendations

**GET** `/api/ml/recommend`

Query params:
- `ticker`: Single ticker (e.g., `AAPL`)
- `tickers`: Comma-separated (e.g., `AAPL,MSFT,TSLA`)
- `horizon_days`: Forecast horizon (default: 21)

**Example:**
```bash
curl "http://localhost:8000/api/ml/recommend?ticker=AAPL&horizon_days=21"
```

**POST** `/api/ml/recommend`

Body:
```json
{
  "tickers": ["AAPL", "MSFT", "TSLA"],
  "horizon_days": 21
}
```

---

### 2. Check Model Status

**GET** `/api/ml/status`

**Response (trained):**
```json
{
  "trained": true,
  "model_path": "/path/to/_artifacts/recommender.pkl",
  "message": "Trained ML model available",
  "features": ["trend", "vol_ann", "rsi14", ...],
  "horizon_days": 21,
  "models": {
    "classifier": "Pipeline",
    "regressor": "RandomForestRegressor"
  }
}
```

**Response (not trained):**
```json
{
  "trained": false,
  "message": "No trained model found. Use POST /ml/train to train a model."
}
```

---

### 3. Train Model

**POST** `/api/ml/train`

Body:
```json
{
  "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
  "lookback_days": 240,
  "horizon_days": 21
}
```

**Response:**
```json
{
  "status": "training_started",
  "message": "Model training started for 5 tickers",
  "config": { ... },
  "note": "Training is running in the background. Use GET /ml/status to check completion."
}
```

**Notes:**
- Training runs in the background
- Can take several minutes depending on tickers and lookback
- Use `GET /ml/status` to check when complete

---

### 4. User-Specific Recommendations

**POST** `/api/ml/evaluate`

Body:
```json
{
  "user_id": "60d5ec49f1a2c8b1f8e4e1a1",
  "tickers": ["AAPL", "MSFT"]
}
```

Evaluates recommendations and saves to MongoDB.

**GET** `/api/ml/recommendations?user_id=...&tickers=AAPL,MSFT`

Retrieves saved recommendations for a user.

---

## Standalone Training Script

### Usage

```bash
# Train with default tickers (10 major stocks)
python train_model.py

# Train with custom tickers
python train_model.py --tickers AAPL MSFT GOOGL AMZN TSLA NVDA META

# Train with more historical data
python train_model.py --lookback-days 365 --horizon-days 30

# Train with many tickers (diversified dataset)
python train_model.py --tickers AAPL MSFT GOOGL AMZN TSLA NVDA META \
                               JPM BAC WMT TGT COST HD LOW \
                               DIS NFLX CRM ADBE
```

### Arguments

- `--tickers`: List of ticker symbols (default: 10 major stocks)
- `--lookback-days`: Historical days to collect (default: 240)
- `--horizon-days`: Forward horizon for labels (default: 21)

---

## Best Practices

### Training

1. **Ticker Selection**
   - Use 10-20 diverse tickers for balanced dataset
   - Include different sectors (tech, finance, retail, etc.)
   - Avoid penny stocks or illiquid tickers

2. **Lookback Period**
   - Minimum: 100 days
   - Recommended: 240-365 days
   - Longer = more data but slower training

3. **Horizon Period**
   - Short-term: 5-10 days
   - Medium-term: 21 days (default)
   - Long-term: 30-60 days

4. **Retraining Frequency**
   - Weekly: For active trading
   - Monthly: For long-term strategies
   - On-demand: After major market events

### Inference

1. **Always check model status first**
   ```bash
   curl http://localhost:8000/api/ml/status
   ```

2. **Use confidence scores**
   - High confidence (>0.8): Strong signal
   - Medium confidence (0.6-0.8): Moderate signal
   - Low confidence (<0.6): Weak signal, consider "Hold"

3. **Combine with risk metrics**
   - Check `var95_h` (Value at Risk)
   - Compare `expected_return_h` vs `sigma_h`
   - Avoid high-risk trades with low expected returns

---

## Troubleshooting

### Training Issues

**Error: "No training data collected"**
- Check ticker symbols are valid
- Increase lookback_days
- Verify API credentials

**Error: API rate limits**
- Reduce number of tickers
- Decrease lookback_days
- Add delays between API calls

### Inference Issues

**Error: "No trained model found"**
- Run `POST /ml/train` first
- Or use `python train_model.py`

**Low accuracy/confidence**
- Retrain with more tickers
- Increase lookback_days for more data
- Check FinBERT is available (better sentiment)

---

## Performance Metrics

### Training Metrics

- **Accuracy**: Classification accuracy on test set
- **F1-Score**: Weighted F1 across Buy/Hold/Sell
- **ROC-AUC**: Multi-class ROC-AUC

*Note: Current implementation focuses on quick iteration. Add evaluation metrics to `train.py` for production.*

### Inference Speed

- **Feature extraction**: ~2-5 seconds (includes API calls)
- **Model prediction**: <10ms
- **Total latency**: ~2-5 seconds per ticker

---

## Future Enhancements

### High Priority
- [ ] Add evaluation metrics to training pipeline
- [ ] Implement cross-validation
- [ ] Add model versioning (timestamp-based)
- [ ] Cache features to reduce API calls

### Medium Priority
- [ ] Support for ensemble models (XGBoost, LightGBM)
- [ ] Hyperparameter tuning
- [ ] Add MACD, Bollinger Bands features
- [ ] Sector/industry features

### Low Priority
- [ ] Real-time streaming inference
- [ ] A/B testing framework
- [ ] Explainability (SHAP values)
- [ ] Multi-timeframe predictions

---

## References

- **FinBERT**: Financial sentiment analysis model
- **Logistic Regression**: Scikit-learn implementation
- **Random Forest**: Scikit-learn ensemble method
- **Technical Indicators**: RSI, SMA, volatility calculations

---

## License

Part of the AI Investment Assistant platform.

**Disclaimer**: This is NOT financial advice. All predictions are for educational and informational purposes only. Always consult a licensed financial advisor before making investment decisions.
