# backend/tests/test_setup.py
"""Test script to verify MongoDB setup"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

async def test_mongodb_connection():
    """Test MongoDB connection and basic operations"""
    print("=" * 60)
    print("Testing MongoDB Setup")
    print("=" * 60)
    
    # Test 1: Import check
    print("\n1. Testing imports...")
    try:
        from app.db import get_db, connect_to_mongo, close_mongo_connection
        from app.db.schemas import User, Portfolio, Trade
        from app.db.repositories import UserRepository, TradeRepository
        print("✓ All imports successful")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print(f"  Python path: {sys.path[:2]}")
        print(f"  Current directory: {Path.cwd()}")
        return False
    
    # Test 2: MongoDB connection
    print("\n2. Testing MongoDB connection...")
    try:
        await connect_to_mongo()
        print("✓ Connected to MongoDB")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  Make sure MongoDB is running and MONGO_URI is set in .env")
        return False
    
    # Test 3: Database operations
    print("\n3. Testing database operations...")
    try:
        db = get_db()
        
        # Test ping
        await db.command("ping")
        print("✓ Database ping successful")
        
        # Count collections
        collections = await db.list_collection_names()
        print(f"✓ Found {len(collections)} collections: {collections}")
        
        # Count users
        user_count = await db.users.count_documents({})
        print(f"✓ Found {user_count} users")
        
    except Exception as e:
        print(f"✗ Database operation failed: {e}")
        return False
    
    # Test 4: Repository pattern
    print("\n4. Testing repository pattern...")
    try:
        from app.db import get_repository
        from app.db.repositories import UserRepository
        
        user_repo = get_repository(UserRepository)
        
        # Try to find a user
        users = await user_repo.find_many({}, limit=1)
        if users:
            print(f"✓ Repository working, found user: {users[0].get('email', 'N/A')}")
        else:
            print("✓ Repository working (no users found, run migration to add sample data)")
            
    except Exception as e:
        print(f"✗ Repository test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Close connection
    await close_mongo_connection()
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! MongoDB setup is working correctly")
    print("=" * 60)
    return True

async def test_auth_system():
    """Test authentication system"""
    print("\n" + "=" * 60)
    print("Testing Authentication System")
    print("=" * 60)
    
    try:
        from app.api.deps import create_access_token, get_password_hash, verify_password
        
        # Test password hashing
        password = "test123"
        hashed = get_password_hash(password)
        print(f"✓ Password hashing works")
        
        # Test password verification
        is_valid = verify_password(password, hashed)
        print(f"✓ Password verification: {is_valid}")
        
        # Test token creation
        token = create_access_token({"sub": "test_user_id"})
        print(f"✓ Token created: {token[:20]}...")
        
        print("✅ Authentication system working")
        
    except Exception as e:
        print(f"✗ Auth test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Main test runner"""
    print(f"Running from: {Path.cwd()}")
    print(f"Backend directory: {backend_dir}")
    print(f"Python path includes: {sys.path[0]}\n")
    
    # Run tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Test MongoDB
    mongo_ok = loop.run_until_complete(test_mongodb_connection())
    
    # Test Auth
    auth_ok = loop.run_until_complete(test_auth_system())
    
    if mongo_ok and auth_ok:
        print("\n🎉 All systems operational! You can now run:")
        print("   python -m app.db.migrate_to_mongo  # To add sample data")
        print("   uvicorn app.main:app --reload      # To start the server")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the backend directory")
        print("2. Ensure MongoDB is running")
        print("3. Check that .env file exists with MONGO_URI set")
        print("4. Verify all required files have been created")

if __name__ == "__main__":
    main()