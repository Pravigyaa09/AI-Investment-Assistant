# backend/app/schemas/__init__.py
"""
Import all schemas for easy access throughout the application.
This file re-exports schemas from db.schemas for backward compatibility.
"""

# Import from the actual location (db/schemas.py)
from app.db.schemas import (
    # Base models
    PyObjectId,
    MongoBaseModel,
    
    # User related
    User,
    Portfolio,
    Holding,
    
    # Trading related
    Trade,
    
    # AI related
    AIScore,
    Recommendation,
    
    # Market data
    MarketData
)

# For compatibility, you might want to create these additional schemas
# that are commonly used in authentication flows
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserInDB(User):
    """User schema with hashed password (internal use)"""
    hashed_password: str


class UserResponse(BaseModel):
    """User response schema (no password)"""
    id: str
    email: EmailStr
    username: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    portfolio: Optional[Portfolio] = None


# Re-export everything for easier imports
__all__ = [
    # From db.schemas
    "PyObjectId",
    "MongoBaseModel",
    "User",
    "Portfolio",
    "Holding",
    "Trade",
    "AIScore",
    "Recommendation",
    "MarketData",
    
    # Additional schemas
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "UserResponse",
]