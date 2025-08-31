# backend/app/routers/auth.py
"""Authentication endpoints for MongoDB users"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from app.db import get_repository, UserRepository
from app.db.schemas import User, Portfolio
from app.api.deps import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user_mongo,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ========== REQUEST/RESPONSE MODELS ==========

class UserRegister(BaseModel):
    """User registration model"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str


class UserLogin(BaseModel):
    """User login model"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User response model"""
    id: str
    email: str
    username: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class PasswordReset(BaseModel):
    """Password reset model"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str


# ========== AUTHENTICATION ENDPOINTS ==========

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        # Validate passwords match
        if user_data.password != user_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Check if user already exists
        existing_user = await user_repo.find_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            is_verified=False,  # Require email verification
            portfolio=Portfolio()  # Initialize empty portfolio
        )
        
        # Save user to database
        user_id = await user_repo.create(new_user.model_dump(by_alias=True))
        
        log.info(f"New user registered: {user_data.email}")
        
        return UserResponse(
            id=user_id,
            email=new_user.email,
            username=new_user.username,
            is_active=new_user.is_active,
            is_verified=new_user.is_verified,
            created_at=new_user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and receive access token"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Find user by email (username field in OAuth2 form)
        user = await user_repo.find_by_email(form_data.username)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["_id"])},
            expires_delta=access_token_expires
        )
        
        log.info(f"User logged in: {form_data.username}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # in seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: dict = Depends(get_current_user_mongo)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        username=current_user["username"],
        is_active=current_user["is_active"],
        is_verified=current_user.get("is_verified", False),
        created_at=current_user["created_at"]
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user_mongo)):
    """Logout current user (client should discard token)"""
    # In a production environment, you might want to:
    # 1. Add the token to a blacklist (Redis)
    # 2. Track logout events
    # 3. Clear any server-side sessions
    
    log.info(f"User logged out: {current_user['email']}")
    
    return {
        "message": "Successfully logged out",
        "email": current_user["email"]
    }


@router.post("/change-password")
async def change_password(
    password_data: PasswordReset,
    current_user: dict = Depends(get_current_user_mongo)
):
    """Change user password"""
    try:
        # Validate new passwords match
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New passwords do not match"
            )
        
        # Verify current password
        if not verify_password(password_data.current_password, current_user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )
        
        # Update password
        user_repo: UserRepository = get_repository(UserRepository)
        new_hash = get_password_hash(password_data.new_password)
        
        success = await user_repo.update_one(
            str(current_user["_id"]),
            {"hashed_password": new_hash}
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        log.info(f"Password changed for user: {current_user['email']}")
        
        return {
            "message": "Password changed successfully",
            "email": current_user["email"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post("/verify-email/{token}")
async def verify_email(token: str):
    """Verify user email with token"""
    # TODO: Implement email verification logic
    # This would typically:
    # 1. Decode the verification token
    # 2. Find the user
    # 3. Set is_verified to True
    # 4. Save the user
    
    return {
        "message": "Email verification endpoint - to be implemented",
        "token": token
    }


@router.post("/forgot-password")
async def forgot_password(email: EmailStr):
    """Request password reset email"""
    # TODO: Implement password reset logic
    # This would typically:
    # 1. Find user by email
    # 2. Generate reset token
    # 3. Send email with reset link
    # 4. Store token with expiration
    
    return {
        "message": "Password reset email sent (to be implemented)",
        "email": email
    }


@router.post("/reset-password/{token}")
async def reset_password(token: str, new_password: str = Field(..., min_length=8)):
    """Reset password with token"""
    # TODO: Implement password reset with token
    # This would typically:
    # 1. Verify the reset token
    # 2. Find the associated user
    # 3. Update the password
    # 4. Invalidate the token
    
    return {
        "message": "Password reset endpoint - to be implemented",
        "token": token
    }