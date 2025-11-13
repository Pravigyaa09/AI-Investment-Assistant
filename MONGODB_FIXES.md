# MongoDB Fixes - Holdings & Duplicate Collections

## Issues Identified

### 1. **Holdings Not Being Saved to MongoDB**

**Problem**: User holdings are not persisting in MongoDB

**Root Cause**: Portfolio holdings are stored as **embedded documents** in the User collection (not separate "holdings" collection):
```javascript
User
  ├── _id
  ├── email
  ├── username
  ├── hashed_password
  └── portfolio
      ├── cash_balance
      ├── holdings  ← Array of holding objects
      │   ├── ticker
      │   ├── quantity
      │   ├── avg_cost
      │   └── ...
      └── total_value
```

**Solution**: The holdings ARE being saved correctly - they're nested inside the portfolio field of the user document. To verify:

```bash
# Check if holdings are saved
python cleanup_mongodb.py

# Or query directly:
db.users.findOne({ "portfolio.holdings": { $exists: true, $ne: [] } })
```

---

### 2. **Duplicate Collection Issue**

**Problem**: MongoDB has both `recommendation` and `recommendations` collections

**Root Cause**: Code inconsistency - `RecommendationRepository` correctly uses `"recommendations"` (plural), but somewhere old code created `"recommendation"` (singular)

**Solution**: Run the cleanup script to remove duplicates:

```bash
cd backend
python cleanup_mongodb.py
```

---

## Step-by-Step Fix

### Step 1: Run MongoDB Cleanup Script

```bash
cd backend
python cleanup_mongodb.py
```

**What it does:**
- Lists all collections and document counts
- Identifies duplicate `recommendation` vs `recommendations`
- Checks portfolio structure in users
- Optionally merges/deletes duplicate collections
- Verifies holdings are embedded in user documents

### Step 2: Verify Holdings Are Saved

After making a trade, verify it was saved:

```bash
# Query a specific user's portfolio
db.users.findOne(
  { email: "user@example.com" },
  { "portfolio.holdings": 1 }
)
```

**Expected output:**
```json
{
  "_id": ObjectId("..."),
  "portfolio": {
    "cash_balance": 5000.50,
    "holdings": [
      {
        "ticker": "AAPL",
        "quantity": 10,
        "avg_cost": 150.00,
        "current_value": 1500.00,
        "pnl": 100.00,
        "pnl_percent": 7.14
      }
    ],
    "total_value": 6500.50
  }
}
```

### Step 3: Remove Duplicate Collections

```bash
# Option 1: Keep 'recommendations', delete 'recommendation'
db.recommendation.drop()  # Delete singular

# Option 2: Or use the cleanup script (interactive)
python cleanup_mongodb.py
# Choose option 1 when prompted
```

---

## Code Fix - Ensure Holdings Are Saved

The `execute_trade()` function in `TradeRepository` already saves holdings correctly (lines 321-331):

```python
# Save trade
trade_id = await self.create(trade.model_dump(by_alias=True))

# Update user portfolio ← This saves holdings
await user_repo.update_portfolio(str(trade.user_id), portfolio)

return trade_id
```

**Key points:**
1. ✅ Holdings are updated in portfolio object
2. ✅ Portfolio is saved to user document via `update_portfolio()`
3. ✅ No separate "holdings" collection needed

---

## Verification Checklist

After running the fixes:

- [ ] Run `python cleanup_mongodb.py`
- [ ] Choose option to remove duplicate "recommendation" collection
- [ ] Execute a test trade (BUY/SELL)
- [ ] Verify holdings appear in MongoDB:
  ```bash
  python cleanup_mongodb.py  # Check "Users with holdings" count
  ```
- [ ] Verify portfolio API returns holdings:
  ```bash
  curl http://localhost:8000/api/portfolio \
    -H "Authorization: Bearer YOUR_TOKEN"
  ```
- [ ] Check no errors in server logs

---

## API Verification

**Get Portfolio** (with holdings):
```bash
curl http://localhost:8000/api/portfolio \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected response:**
```json
{
  "cash_balance": 5000.50,
  "holdings": [
    {
      "ticker": "AAPL",
      "quantity": 10,
      "avg_cost": 150.00,
      "last_price": 155.00,
      "current_value": 1550.00,
      "pnl": 100.00,
      "pnl_percent": 7.14,
      "weight": 23.8
    }
  ],
  "total_value": 6500.50,
  "total_invested": 1500.00,
  "total_pnl": 100.00,
  "total_pnl_percent": 7.14,
  "holdings_count": 1,
  "last_updated": "2024-11-04T10:30:45.123Z"
}
```

---

## Collections Schema Reference

### Correct Collections

**users** (primary):
- User documents with embedded portfolio and holdings

**trades**:
- Transaction records (BUY/SELL)

**recommendations** (not "recommendation"):
- ML model recommendations for users

**ai_scores**:
- AI/ML score history

**news**:
- Cached news articles

**market_data**:
- Cached market data

---

## Troubleshooting

### Holdings not appearing after trade

**Check 1**: Verify trade was created
```bash
db.trades.findOne({ user_id: ObjectId("...") })
```

**Check 2**: Verify portfolio was updated
```bash
db.users.findOne(
  { _id: ObjectId("...") },
  { portfolio: 1 }
)
```

**Check 3**: Check server logs for errors
```bash
# Look for "Error executing trade" or similar
```

### Duplicate collections still exist

Run the cleanup script again:
```bash
python cleanup_mongodb.py
# Choose option 1 or 3
```

### Portfolio API returns empty holdings

1. Ensure you're authenticated (Bearer token)
2. Execute a trade first
3. Check the portfolio endpoint is querying correct user_id

---

## Production Checklist

- [ ] Backup MongoDB before running cleanup
- [ ] Test on development database first
- [ ] Verify holdings persist after trade execution
- [ ] Verify API returns correct portfolio data
- [ ] Check no errors in logs
- [ ] Test with multiple users to ensure isolation
- [ ] Verify ML recommendations use "recommendations" collection

---

## Summary

✅ **Holdings ARE being saved** - they're embedded in user documents
❌ **Duplicate collections need cleanup** - use `cleanup_mongodb.py`
✅ **Code is correct** - `TradeRepository.execute_trade()` saves properly

**Next steps:**
1. Run `python cleanup_mongodb.py` to remove duplicates
2. Verify holdings appear in MongoDB
3. Test API endpoints work correctly
