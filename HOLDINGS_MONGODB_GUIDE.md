# Holdings & MongoDB Issues - Complete Guide

## Quick Summary

### Issue #1: Holdings Not Saved
**Status**: ✅ **Actually being saved correctly** - they're in user.portfolio.holdings
**Solution**: Verify with verification script

### Issue #2: Duplicate Collections
**Status**: ❌ **Needs cleanup** - both "recommendation" and "recommendations" exist
**Solution**: Run cleanup script to remove "recommendation" (singular)

---

## What's Actually Happening

### Holdings Storage Model

Holdings are **embedded** in the User document, NOT in a separate collection:

```
MongoDB Structure:
│
├── users (collection)
│   └── User Document
│       ├── _id
│       ├── email
│       ├── username
│       ├── hashed_password
│       └── portfolio (embedded)
│           ├── cash_balance: 10000
│           ├── holdings: [      ← Holdings array
│           │   {
│           │     "ticker": "AAPL",
│           │     "quantity": 10,
│           │     "avg_cost": 150
│           │   }
│           ├── total_value: 10000
│           └── last_updated: timestamp
│
├── trades (collection)
│   └── Trade Document
│       ├── user_id (references User._id)
│       ├── ticker
│       ├── side: "BUY"/"SELL"
│       └── ...
│
└── recommendations (collection)
    └── Recommendation Document
        ├── user_id
        ├── ticker
        ├── action
        └── ...
```

**Key Point**: Holdings are NOT in a separate "holdings" collection. They're nested inside each User document.

---

## Files to Run

### 1. Verify Holdings Are Saved

```bash
cd backend
python verify_holdings.py
```

**What it does:**
- Creates a test user
- Executes a BUY trade
- Checks if holdings were saved to MongoDB
- Verifies portfolio calculations
- Cleans up test data

**Expected output:**
```
✅ VERIFICATION COMPLETE
✅ All checks passed! Holdings are being saved correctly.
   ✓ Holdings saved to portfolio.holdings in user document
   ✓ Trades recorded in trades collection
   ✓ Portfolio cash balance updated correctly
   ✓ Portfolio total value calculated correctly
```

### 2. Cleanup MongoDB Collections

```bash
cd backend
python cleanup_mongodb.py
```

**What it does:**
- Lists all collections
- Identifies duplicate "recommendation" vs "recommendations"
- Checks portfolio structure
- Optionally merges/deletes duplicates
- Verifies data integrity

**Expected prompts:**
```
🔎 Checking for duplicate recommendation collections...
   recommendation:  True
   recommendations: True

   ⚠️  FOUND DUPLICATE COLLECTIONS!

   Options:
   1. Keep 'recommendations', delete 'recommendation'  ← CHOOSE THIS
   2. Keep 'recommendation', delete 'recommendations'
   3. Merge both collections
   4. Skip cleanup

   Choose option (1-4): 1
```

---

## Step-by-Step Fix Process

### Step 1: Verify Current Holdings Status

```bash
cd backend
python verify_holdings.py
```

Check if holdings are being saved. If test passes, skip to Step 2.
If it fails, see "Troubleshooting" section below.

### Step 2: Clean Up Duplicate Collections

```bash
cd backend
python cleanup_mongodb.py
```

When prompted, choose **Option 1** to:
- Keep the correct `recommendations` collection
- Delete the old `recommendation` collection

### Step 3: Verify API Works Correctly

Make a test trade and verify it returns holdings:

```bash
# 1. Login and get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_email@example.com&password=your_password"

# Get the access_token from response

# 2. Execute a BUY trade
curl -X POST http://localhost:8000/api/portfolio/trade \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "ticker": "AAPL",
    "side": "BUY",
    "quantity": 10,
    "price": 150.00
  }'

# 3. Get portfolio (should show holdings)
curl http://localhost:8000/api/portfolio \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected portfolio response:**
```json
{
  "cash_balance": 8485.00,
  "holdings": [
    {
      "ticker": "AAPL",
      "quantity": 10,
      "avg_cost": 150.00,
      "last_price": 150.00,
      "current_value": 1500.00,
      "pnl": 0.00,
      "pnl_percent": 0.00,
      "weight": 15.00
    }
  ],
  "total_value": 9985.00,
  "total_invested": 1500.00,
  "total_pnl": 0.00,
  "total_pnl_percent": 0.00,
  "holdings_count": 1,
  "last_updated": "2024-11-04T10:30:45.123Z"
}
```

### Step 4: Verify in MongoDB

Query MongoDB directly to confirm holdings:

```javascript
// In MongoDB shell
db.users.findOne(
  { email: "your_email@example.com" },
  { portfolio: 1 }
)

// Should return:
{
  "_id": ObjectId("..."),
  "portfolio": {
    "cash_balance": 8485.00,
    "holdings": [
      {
        "ticker": "AAPL",
        "quantity": 10,
        "avg_cost": 150,
        "last_price": 150,
        "current_value": 1500,
        "pnl": 0,
        "pnl_percent": 0,
        "updated_at": ISODate("2024-11-04T10:30:45.123Z")
      }
    ],
    "total_value": 9985,
    "last_updated": ISODate("2024-11-04T10:30:45.123Z")
  }
}
```

---

## Troubleshooting

### Issue: Holdings Not Showing in API Response

**Check 1: User exists**
```bash
curl http://localhost:8000/api/portfolio \
  -H "Authorization: Bearer YOUR_TOKEN"
```

If you get 401 → Re-authenticate
If you get 500 → Check server logs

**Check 2: Holdings in MongoDB**
```javascript
db.users.findOne(
  { email: "your_email@example.com" },
  { "portfolio.holdings": 1 }
)
```

If empty array → No trades executed
If contains holdings → API might not be returning them correctly

**Check 3: Trade executed successfully**
```javascript
db.trades.find({ user_id: ObjectId("YOUR_USER_ID") })
```

If empty → Trade execution failed
If contains trades → Holdings should exist

### Issue: Trade Execution Failed

**Error: "Insufficient funds"**
- Deposit more cash: `POST /api/portfolio/deposit`
- Check current cash: `GET /api/portfolio`

**Error: "Insufficient shares"**
- Can't sell shares you don't own
- Check holdings: `GET /api/portfolio`

**Error: 500 Server Error**
- Check server logs
- Run: `python verify_holdings.py` to diagnose

### Issue: Duplicate Collections Still Exist

Run cleanup again:
```bash
python cleanup_mongodb.py
```

Choose option 1, 2, or 3 based on which collection has your data.

### Issue: Portfolio Value Calculation Wrong

The API calculates portfolio value as:
```python
total_value = cash_balance + sum(holding.current_value for each holding)
```

If wrong, check:
1. Are holdings updating prices? (`last_price` should change)
2. Is cash_balance correct?
3. Are holdings quantities right?

---

## Code Reference

### Where Holdings Are Saved

**File**: `backend/app/db/repositories.py`
**Function**: `TradeRepository.execute_trade()` (lines 250-333)

Key lines:
```python
# Line 331: This saves holdings to MongoDB
await user_repo.update_portfolio(str(trade.user_id), portfolio)
```

**File**: `backend/app/db/repositories.py`
**Function**: `UserRepository.update_portfolio()` (lines 125-127)

```python
async def update_portfolio(self, user_id: str, portfolio: Portfolio) -> bool:
    """Update user's portfolio"""
    return await self.update_one(user_id, {"portfolio": portfolio.model_dump()})
```

This saves the entire portfolio object (including holdings array) to the user document.

---

## Collections Reference

### Current Collections (After Cleanup)

| Collection | Purpose | Key Fields |
|------------|---------|-----------|
| `users` | User accounts & portfolios | email, username, portfolio |
| `trades` | Transaction history | user_id, ticker, side, quantity |
| `recommendations` | ML recommendations | user_id, ticker, action |
| `ai_scores` | AI score history | user_id, ticker |
| `news` | Cached news articles | ticker, source |
| `market_data` | Cached market data | ticker, price |

### Deprecated Collections (To Delete)

| Collection | Reason | Action |
|------------|--------|--------|
| `recommendation` | Duplicate (singular) | DELETE - use `recommendations` instead |
| `holdings` | Redundant - use embedded | DELETE - holdings are in user.portfolio |

---

## Verification Checklist

Use this to ensure everything is working:

- [ ] Run `python verify_holdings.py` - all checks pass
- [ ] Run `python cleanup_mongodb.py` - remove duplicate collections
- [ ] Execute test BUY trade - no errors
- [ ] Check `GET /api/portfolio` - holdings appear
- [ ] Query MongoDB - holdings in user.portfolio.holdings
- [ ] Execute test SELL trade - holdings updated
- [ ] Check portfolio total value - calculated correctly
- [ ] Query `db.trades` - trades recorded
- [ ] Check `db.recommendations` only - singular removed

---

## FAQ

**Q: Why are holdings in the user document instead of separate collection?**
A: Embedded documents (denormalization) are better for this use case because:
- Holdings are always queried with user data
- Faster reads (no joins)
- Atomic writes (no multi-document transactions)
- Follows MongoDB best practices for relational data

**Q: What's the difference between "recommendation" and "recommendations"?**
A: They're the same thing. The code should use "recommendations" (plural).
The singular "recommendation" is old/unused and should be deleted.

**Q: How often should I run the cleanup script?**
A: Only once initially. After that, the code correctly uses "recommendations".

**Q: Can I use the old "holdings" collection?**
A: No. Holdings are embedded in user documents. The separate collection is not used.

**Q: What if I have data in the old collections?**
A: The cleanup script can migrate data before deleting. Choose option 1, 2, or 3 when prompted.

---

## Production Deployment

Before deploying to production:

1. **Backup database**
   ```bash
   mongodump --uri "mongodb://..." --out /backup/
   ```

2. **Test on staging**
   ```bash
   python verify_holdings.py  # On staging environment
   ```

3. **Run cleanup**
   ```bash
   python cleanup_mongodb.py  # Choose option 1
   ```

4. **Verify API endpoints**
   ```bash
   # Test all portfolio endpoints
   GET    /api/portfolio
   POST   /api/portfolio/trade
   POST   /api/portfolio/deposit
   GET    /api/portfolio/trades
   GET    /api/portfolio/performance
   DELETE /api/portfolio/holdings/{ticker}
   ```

5. **Monitor logs**
   - Check for any errors related to portfolio operations
   - Monitor API response times
   - Check MongoDB connection health

---

## Support

If issues persist:

1. Run verification scripts and save output
2. Check server logs
3. Review MongoDB data structure
4. Ensure code is up to date
5. Check API token is valid

---

**Created**: November 4, 2024
**Version**: 1.0
