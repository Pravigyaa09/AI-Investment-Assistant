# reset_user.py
import asyncio
from app.db import connect_to_mongo, get_db
from app.core.security import get_password_hash  # Use the fixed version

async def reset_demo_user():
    await connect_to_mongo()
    db = get_db()
    
    # Create fresh password hash
    new_hash = get_password_hash("demo123")
    print(f"New hash created: {new_hash[:50]}...")
    
    # Update user
    result = await db.users.update_one(
        {"email": "demo@aiinvest.com"},
        {"$set": {
            "hashed_password": new_hash,
            "is_active": True,
            "is_verified": True
        }}
    )
    
    if result.modified_count > 0:
        print("✓ Password reset successfully!")
        print("\nLogin with:")
        print("  Email: demo@aiinvest.com")
        print("  Password: demo123")
    else:
        print("User not found or update failed")

asyncio.run(reset_demo_user())