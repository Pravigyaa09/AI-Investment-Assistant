# backend/app/api/deps.py
"""API Dependencies for MongoDB authentication and authorization"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from bson import ObjectId

from app.core.config import settings
from app.db import get_db, get_repository, UserRepository
from app.logger import get_logger

log = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/token")

# JWT settings
SECRET_KEY = settings.SECRET_KEY or "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES or 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user_mongo(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from MongoDB using JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Validate ObjectId format
        if not ObjectId.is_valid(user_id):
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Get user from MongoDB
    user_repo: UserRepository = get_repository(UserRepository)
    user = await user_repo.find_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


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


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[Dict[str, Any]]:
    """Get current user if token is provided, otherwise return None"""
    if not token:
        return None
    
    try:
        return await get_current_user_mongo(token)
    except HTTPException:
        return None


# Admin check dependency
async def get_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user_mongo)
) -> Dict[str, Any]:
    """Ensure the current user is an admin"""
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# Rate limiting helper (can be used with Redis in production)
class RateLimiter:
    """Simple in-memory rate limiter (use Redis in production)"""
    
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


# Create rate limiters for different endpoints
rate_limit_trades = RateLimiter(times=10, seconds=60)  # 10 trades per minute
rate_limit_api = RateLimiter(times=100, seconds=60)  # 100 API calls per minute