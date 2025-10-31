# backend/app/api/deps.py
"""API Dependencies for MongoDB authentication and authorization"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from bson import ObjectId

# Import from core.security - DO NOT REDEFINE
from app.core.security import decode_access_token
from app.core.config import settings
from app.db import get_repository
from app.db.repositories import UserRepository
from app.logger import get_logger

log = get_logger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")

async def get_current_user_mongo(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from MongoDB using JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token using the function from security.py
    payload = decode_access_token(token)
    if not payload:
        log.error("Token decode failed - invalid token")
        raise credentials_exception
    
    user_id = payload.get("sub")
    if not user_id:
        log.error("Token missing 'sub' field")
        raise credentials_exception
    
    # Validate ObjectId
    if not ObjectId.is_valid(user_id):
        log.error(f"Invalid ObjectId: {user_id}")
        raise credentials_exception
    
    # Get user from MongoDB
    try:
        user_repo = get_repository(UserRepository)
        user = await user_repo.find_by_id(user_id)
        
        if not user:
            log.error(f"User not found: {user_id}")
            raise credentials_exception
        
        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        return user
    except Exception as e:
        log.error(f"Error fetching user: {e}")
        raise credentials_exception

# Rest of your functions remain the same
async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user_mongo)
) -> Dict[str, Any]:
    """Ensure the current user is active"""
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_verified_user(
    current_user: Dict[str, Any] = Depends(get_current_user_mongo)
) -> Dict[str, Any]:
    """Ensure the current user is verified"""
    if not current_user.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User email not verified. Please verify your email to access this resource."
        )
    return current_user

# Rate limiter class stays the same
class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self, times: int = 10, seconds: int = 60):
        self.times = times
        self.seconds = seconds
        self.calls = {}
    
    async def __call__(self, user: Dict[str, Any] = Depends(get_current_user_mongo)) -> Dict[str, Any]:
        user_id = str(user["_id"])
        now = datetime.now(timezone.utc)
        
        # Clean old entries
        self.calls = {
            uid: times 
            for uid, times in self.calls.items() 
            if any(t > now - timedelta(seconds=self.seconds) for t in times)
        }
        
        # Check rate limit
        if user_id in self.calls:
            recent_calls = [t for t in self.calls[user_id] if t > now - timedelta(seconds=self.seconds)]
            if len(recent_calls) >= self.times:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.times} requests per {self.seconds} seconds."
                )
            self.calls[user_id] = recent_calls + [now]
        else:
            self.calls[user_id] = [now]
        
        return user

rate_limit_trades = RateLimiter(times=10, seconds=60)
rate_limit_api = RateLimiter(times=100, seconds=60)