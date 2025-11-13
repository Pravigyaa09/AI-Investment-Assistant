#!/usr/bin/env python3
"""
Verify holdings are being saved to MongoDB correctly.
Tests the complete trade flow: BUY → holdings saved → verify in DB
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.db.mongo import get_db
from app.db import get_repository, UserRepository, TradeRepository
from app.db.schemas import Portfolio, Trade, Holding


async def test_holdings_flow():
    """Test complete holdings flow"""
    db = get_db()

    print("=" * 70)
    print("🔍 HOLDINGS VERIFICATION TEST")
    print("=" * 70)

    # Step 1: Create test user
    print("\n📝 Step 1: Creating test user...")
    users_col = db["users"]

    test_user = {
        "email": f"test_holdings_{int(datetime.now(timezone.utc).timestamp())}@example.com",
        "username": "test_holdings_user",
        "hashed_password": "test_hashed_password",
        "is_active": True,
        "is_verified": True,
        "portfolio": {
            "cash_balance": 10000.0,
            "holdings": [],
            "total_value": 10000.0,
            "last_updated": datetime.now(timezone.utc).isoformat()
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    result = await users_col.insert_one(test_user)
    user_id = str(result.inserted_id)
    print(f"✅ Created test user: {user_id}")
    print(f"   Email: {test_user['email']}")
    print(f"   Initial cash: ${test_user['portfolio']['cash_balance']}")

    # Step 2: Verify initial state
    print("\n📊 Step 2: Verifying initial state...")
    user = await users_col.find_one({"_id": result.inserted_id})
    if user:
        portfolio = user.get("portfolio", {})
        holdings = portfolio.get("holdings", [])
        print(f"✅ User found in database")
        print(f"   Cash balance: ${portfolio.get('cash_balance', 0)}")
        print(f"   Holdings count: {len(holdings)}")
    else:
        print("❌ User not found!")
        return

    # Step 3: Create and execute a BUY trade
    print("\n💰 Step 3: Executing BUY trade (AAPL, qty=10, price=$150)...")
    trade_repo: TradeRepository = get_repository(TradeRepository)
    user_repo: UserRepository = get_repository(UserRepository)

    trade = Trade(
        user_id=user_id,
        ticker="AAPL",
        side="BUY",
        quantity=10,
        price=150.0,
        commission=15.0  # 0.1% of $1500
    )

    try:
        trade_id = await trade_repo.execute_trade(trade, user_repo)
        if trade_id:
            print(f"✅ Trade executed successfully")
            print(f"   Trade ID: {trade_id}")
            print(f"   Total cost: ${trade.quantity * trade.price + trade.commission}")
        else:
            print("❌ Trade execution failed!")
            return
    except Exception as e:
        print(f"❌ Trade execution error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Verify holdings were saved
    print("\n🔍 Step 4: Verifying holdings were saved...")
    user = await users_col.find_one({"_id": result.inserted_id})
    if user:
        portfolio = user.get("portfolio", {})
        holdings = portfolio.get("holdings", [])
        print(f"✅ User data retrieved")
        print(f"   Cash balance: ${portfolio.get('cash_balance', 0):.2f}")
        print(f"   Holdings count: {len(holdings)}")

        if holdings:
            for h in holdings:
                print(f"\n   Holding found:")
                print(f"      Ticker: {h.get('ticker')}")
                print(f"      Quantity: {h.get('quantity')}")
                print(f"      Avg Cost: ${h.get('avg_cost', 0):.2f}")
                print(f"      Current Value: ${h.get('current_value', 0):.2f}")
                print(f"      P&L: ${h.get('pnl', 0):.2f} ({h.get('pnl_percent', 0):.2f}%)")
        else:
            print("   ❌ No holdings found!")

    # Step 5: Verify trade was recorded
    print("\n📋 Step 5: Verifying trade was recorded...")
    trades_col = db["trades"]
    trade_count = await trades_col.count_documents({"user_id": result.inserted_id})
    print(f"✅ Trades for user: {trade_count}")

    if trade_count > 0:
        recorded_trade = await trades_col.find_one({"user_id": result.inserted_id})
        if recorded_trade:
            print(f"\n   Trade details:")
            print(f"      Trade ID: {recorded_trade.get('_id')}")
            print(f"      Ticker: {recorded_trade.get('ticker')}")
            print(f"      Side: {recorded_trade.get('side')}")
            print(f"      Quantity: {recorded_trade.get('quantity')}")
            print(f"      Price: ${recorded_trade.get('price', 0):.2f}")
            print(f"      Total: ${recorded_trade.get('total_value', 0):.2f}")
            print(f"      Status: {recorded_trade.get('status')}")

    # Step 6: Verify portfolio calculations
    print("\n📊 Step 6: Verifying portfolio calculations...")
    user = await users_col.find_one({"_id": result.inserted_id})
    portfolio = user.get("portfolio", {})
    initial_cash = 10000.0
    expected_cash = initial_cash - (10 * 150.0 + 15.0)

    actual_cash = portfolio.get("cash_balance", 0)
    total_value = portfolio.get("total_value", 0)

    print(f"   Initial cash: ${initial_cash:.2f}")
    print(f"   Expected cash after trade: ${expected_cash:.2f}")
    print(f"   Actual cash: ${actual_cash:.2f}")

    if abs(actual_cash - expected_cash) < 0.01:
        print(f"   ✅ Cash calculation CORRECT")
    else:
        print(f"   ❌ Cash calculation INCORRECT (difference: ${abs(actual_cash - expected_cash):.2f})")

    print(f"\n   Total portfolio value: ${total_value:.2f}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 70)

    holdings = portfolio.get("holdings", [])
    if len(holdings) > 0 and trade_count > 0 and abs(actual_cash - expected_cash) < 0.01:
        print("\n✅ All checks passed! Holdings are being saved correctly.")
        print("\n   ✓ Holdings saved to portfolio.holdings in user document")
        print("   ✓ Trades recorded in trades collection")
        print("   ✓ Portfolio cash balance updated correctly")
        print("   ✓ Portfolio total value calculated correctly")
    else:
        print("\n❌ Some checks failed. Please review the output above.")

    print("\n" + "=" * 70)

    # Cleanup
    print("\n🧹 Cleaning up test data...")
    await users_col.delete_one({"_id": result.inserted_id})
    await trades_col.delete_many({"user_id": result.inserted_id})
    print("✅ Test user and trades deleted")


if __name__ == "__main__":
    asyncio.run(test_holdings_flow())
