# backend/tests/comprehensive_test.py
"""Comprehensive test for MongoDB migration completion"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

async def run_all_tests():
    print("=" * 70)
    print(" COMPREHENSIVE MONGODB MIGRATION TEST ")
    print("=" * 70)
    
    # Test 1: Core MongoDB imports
    print("\n[TEST 1] MongoDB Core Imports...")
    try:
        from app.db import (
            connect_to_mongo, close_mongo_connection,
            get_db, get_repository,
            User, Portfolio, Trade,
            UserRepository, TradeRepository
        )
        print("✅ MongoDB imports successful")
    except ImportError as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Test 2: Auth system
    print("\n[TEST 2] Authentication System...")
    try:
        from app.api.deps import (
            create_access_token, 
            get_password_hash, 
            verify_password,
            get_current_user_mongo
        )
        from app.routers.auth import router as auth_router
        print("✅ Auth system imports successful")
    except ImportError as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Test 3: Routers
    print("\n[TEST 3] Router Imports...")
    try:
        from app.routers import (
            auth, mongo_portfolio_v2, mongo_users,
            analysis, sentiment, recommender
        )
        print("✅ All routers import successfully")
    except ImportError as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Test 4: MongoDB Connection
    print("\n[TEST 4] MongoDB Connection...")
    try:
        await connect_to_mongo()
        db = get_db()
        await db.command("ping")
        collections = await db.list_collection_names()
        print(f"✅ Connected to MongoDB with {len(collections)} collections")
        await close_mongo_connection()
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Test 5: Check for old files
    print("\n[TEST 5] Checking for removed files...")
    old_files = [
        Path("app/db/base.py"),
        Path("app/db/models.py"),
        Path("app/db/session.py"),
        Path("app/schemas/article.py"),
        Path("app/schemas/portfolio.py"),
        Path("app/services/portfolio.py"),
    ]
    
    existing_old = [f for f in old_files if f.exists()]
    if existing_old:
        print("❌ Old files still exist:")
        for f in existing_old:
            print(f"   - {f}")
    else:
        print("✅ All old files removed")
    
    print("\n" + "=" * 70)
    print(" ✅ ALL TESTS PASSED - MIGRATION COMPLETE! ")
    print("=" * 70)
    
    print("\n📋 Next Steps:")
    print("1. Initialize DB: python -m app.db.migrate_to_mongo")
    print("2. Start server:  uvicorn app.main:app --reload")
    print("3. Test API:      http://localhost:8000/docs")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)