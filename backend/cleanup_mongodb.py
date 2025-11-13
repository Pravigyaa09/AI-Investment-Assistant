#!/usr/bin/env python3
"""
MongoDB cleanup and verification script.
Checks collections, removes duplicates, and verifies data integrity.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.db.mongo import get_db
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
import os
from datetime import datetime, timezone


async def main():
    """Main cleanup routine"""
    db = get_db()

    print("=" * 70)
    print("🔍 MONGODB CLEANUP & VERIFICATION")
    print("=" * 70)

    # 1. List all collections
    print("\n📋 Current Collections:")
    collections = await db.list_collection_names()
    for i, col in enumerate(collections, 1):
        count = await db[col].count_documents({})
        print(f"   {i}. {col:30} ({count} documents)")

    # 2. Check for duplicate recommendation collections
    print("\n🔎 Checking for duplicate recommendation collections...")
    has_recommendation = "recommendation" in collections
    has_recommendations = "recommendations" in collections

    if has_recommendation or has_recommendations:
        print(f"   recommendation:  {has_recommendation}")
        print(f"   recommendations: {has_recommendations}")

        if has_recommendation and has_recommendations:
            print("\n   ⚠️  FOUND DUPLICATE COLLECTIONS!")

            # Count documents in each
            rec_count = await db["recommendation"].count_documents({})
            recs_count = await db["recommendations"].count_documents({})
            print(f"      - 'recommendation':  {rec_count} documents")
            print(f"      - 'recommendations': {recs_count} documents")

            # Show sample documents
            if rec_count > 0:
                print("\n   Sample from 'recommendation':")
                sample = await db["recommendation"].find_one()
                print(f"      {sample}")

            if recs_count > 0:
                print("\n   Sample from 'recommendations':")
                sample = await db["recommendations"].find_one()
                print(f"      {sample}")

            # Ask user what to do
            print("\n   Options:")
            print("   1. Keep 'recommendations', delete 'recommendation'")
            print("   2. Keep 'recommendation', delete 'recommendations'")
            print("   3. Merge both collections")
            print("   4. Skip cleanup")

            choice = input("\n   Choose option (1-4): ").strip()

            if choice == "1":
                print("\n   ℹ️  Deleting 'recommendation' collection...")
                # First, migrate any data if needed
                if rec_count > 0 and recs_count == 0:
                    print("   📝 Migrating data from 'recommendation' to 'recommendations'...")
                    all_docs = await db["recommendation"].find().to_list(length=None)
                    if all_docs:
                        await db["recommendations"].insert_many(all_docs)
                        print(f"   ✓ Migrated {len(all_docs)} documents")

                result = await db["recommendation"].drop()
                print("   ✅ 'recommendation' collection deleted")

            elif choice == "2":
                print("\n   ℹ️  Deleting 'recommendations' collection...")
                # Migrate data if needed
                if recs_count > 0 and rec_count == 0:
                    print("   📝 Migrating data from 'recommendations' to 'recommendation'...")
                    all_docs = await db["recommendations"].find().to_list(length=None)
                    if all_docs:
                        await db["recommendation"].insert_many(all_docs)
                        print(f"   ✓ Migrated {len(all_docs)} documents")

                result = await db["recommendations"].drop()
                print("   ✅ 'recommendations' collection deleted")

            elif choice == "3":
                print("\n   ℹ️  Merging 'recommendation' into 'recommendations'...")
                all_docs = await db["recommendation"].find().to_list(length=None)
                if all_docs:
                    await db["recommendations"].insert_many(all_docs)
                    print(f"   ✓ Migrated {len(all_docs)} documents")
                result = await db["recommendation"].drop()
                print("   ✅ 'recommendation' collection deleted")

    # 3. Check portfolio/holdings structure
    print("\n📦 Checking portfolio structure...")
    users_col = db["users"]
    user_count = await users_col.count_documents({})
    print(f"   Total users: {user_count}")

    if user_count > 0:
        # Check a sample user
        sample_user = await users_col.find_one()
        if sample_user:
            print(f"\n   Sample user structure:")
            print(f"      _id: {sample_user.get('_id')}")
            print(f"      email: {sample_user.get('email')}")
            print(f"      username: {sample_user.get('username')}")

            portfolio = sample_user.get("portfolio")
            if portfolio:
                print(f"\n   ✅ Portfolio found:")
                print(f"      cash_balance: {portfolio.get('cash_balance', 0)}")
                holdings = portfolio.get("holdings", [])
                print(f"      holdings count: {len(holdings)}")
                if holdings:
                    for h in holdings[:3]:
                        print(f"         - {h.get('ticker')}: {h.get('quantity')} @ ${h.get('avg_cost')}")
                    if len(holdings) > 3:
                        print(f"         ... and {len(holdings) - 3} more")
            else:
                print(f"\n   ❌ No portfolio found for user")

        # Check for users with holdings
        users_with_holdings = await users_col.count_documents({
            "portfolio.holdings": {"$exists": True, "$ne": []}
        })
        print(f"\n   Users with holdings: {users_with_holdings}")

    # 4. Check for orphaned holdings collection
    if "holdings" in collections:
        holdings_count = await db["holdings"].count_documents({})
        print(f"\n   ⚠️  Found 'holdings' collection with {holdings_count} documents")
        print("   NOTE: Holdings should be embedded in user.portfolio.holdings")
        if holdings_count > 0:
            cleanup = input("   Delete 'holdings' collection? (y/n): ").strip().lower()
            if cleanup == "y":
                await db["holdings"].drop()
                print("   ✅ 'holdings' collection deleted")

    # 5. Check trades
    print("\n📊 Checking trades...")
    if "trades" in collections:
        trades_count = await db["trades"].count_documents({})
        print(f"   Trades collection: {trades_count} documents")

        # Check for orphaned trades
        if trades_count > 0:
            sample_trade = await db["trades"].find_one()
            if sample_trade:
                print(f"\n   Sample trade structure:")
                print(f"      _id: {sample_trade.get('_id')}")
                print(f"      user_id: {sample_trade.get('user_id')}")
                print(f"      ticker: {sample_trade.get('ticker')}")
                print(f"      side: {sample_trade.get('side')}")
                print(f"      quantity: {sample_trade.get('quantity')}")

    # 6. Summary
    print("\n" + "=" * 70)
    print("✅ CLEANUP COMPLETE")
    print("=" * 70)
    print("\n💡 Recommendations:")
    print("   1. Portfolio holdings are embedded in user documents")
    print("   2. Use only 'recommendations' collection (not 'recommendation')")
    print("   3. Ensure trades collection exists with proper user_id references")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
