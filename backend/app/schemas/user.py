# backend/app/schemas/user.py
"""User related schemas"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

from app.db.schemas import Portfolio


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    is_active: bool = True
    is_verified: bool = False


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema (public)"""
    id: str
    created_at: datetime
    updated_at: datetime
    portfolio: Optional[Portfolio] = None
    
    class Config:
        from_attributes = True


class UserInDB(UserBase):
    """User in database schema (internal)"""
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    portfolio: Portfolio
    
    class Config:
        from_attributes = True