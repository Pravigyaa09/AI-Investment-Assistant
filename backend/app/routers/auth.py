# backend/app/routers/auth.py
"""Authentication endpoints for MongoDB users"""

import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
import jwt
import redis

from app.db import get_repository, UserRepository
from app.db.schemas import User, Portfolio
from app.core.security import verify_password, get_password_hash, create_access_token
from app.api.deps import get_current_user_mongo
from app.core.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Redis for token blacklist (optional)
try:
    redis_client = redis.Redis(
        host=getattr(settings, 'REDIS_HOST', 'localhost'), 
        port=getattr(settings, 'REDIS_PORT', 6379), 
        db=0, 
        decode_responses=True
    )
    # Test connection
    redis_client.ping()
except:
    redis_client = None
    log.warning("Redis not available - token blacklisting disabled")


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


class PasswordResetRequest(BaseModel):
    """Password reset request model"""
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model"""
    email: EmailStr


# ========== UTILITY CLASSES ==========

class TokenManager:
    @staticmethod
    def generate_verification_token(user_id: str, email: str) -> str:
        """Generate email verification token"""
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "email_verification",
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    
    @staticmethod
    def generate_reset_token(user_id: str, email: str) -> str:
        """Generate password reset token"""
        payload = {
            "user_id": user_id,
            "email": email,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1),  # Short expiry for security
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    
    @staticmethod
    def verify_token(token: str, expected_type: str) -> Optional[dict]:
        """Verify and decode token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") != expected_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            log.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            log.warning("Invalid token")
            return None
    
    @staticmethod
    def blacklist_token(token: str):
        """Add token to blacklist"""
        if redis_client:
            try:
                # Decode to get expiry time
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
                exp = payload.get("exp")
                if exp:
                    # Set expiry time for Redis key
                    ttl = exp - datetime.utcnow().timestamp()
                    if ttl > 0:
                        redis_client.setex(f"blacklist:{token}", int(ttl), "1")
            except Exception as e:
                log.error(f"Failed to blacklist token: {e}")


class EmailService:
    @staticmethod
    def send_verification_email(email: str, token: str):
        """Send email verification email"""
        try:
            # Check if SMTP is configured
            if not all([
                getattr(settings, 'SMTP_HOST', None),
                getattr(settings, 'SMTP_USER', None),
                getattr(settings, 'SMTP_PASSWORD', None)
            ]):
                log.warning(f"SMTP not configured - verification email for {email} not sent")
                return
            
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_USER
            msg["To"] = email
            msg["Subject"] = "Verify Your Email - AI Investment Assistant"
            
            # Create verification link
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            verification_link = f"{frontend_url}/verify-email?token={token}"
            
            body = f"""
            <html>
                <body>
                    <h2>Welcome to AI Investment Assistant!</h2>
                    <p>Please click the link below to verify your email address:</p>
                    <p><a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">Verify Email</a></p>
                    <p>This link will expire in 24 hours.</p>
                    <p>If you didn't create an account, please ignore this email.</p>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(body, "html"))
            
            with smtplib.SMTP(settings.SMTP_HOST, getattr(settings, 'SMTP_PORT', 587)) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            log.info(f"Verification email sent to {email}")
            
        except Exception as e:
            log.error(f"Failed to send verification email to {email}: {e}")
    
    @staticmethod
    def send_password_reset_email(email: str, token: str):
        """Send password reset email"""
        try:
            # Check if SMTP is configured
            if not all([
                getattr(settings, 'SMTP_HOST', None),
                getattr(settings, 'SMTP_USER', None),
                getattr(settings, 'SMTP_PASSWORD', None)
            ]):
                log.warning(f"SMTP not configured - reset email for {email} not sent")
                return
            
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_USER
            msg["To"] = email
            msg["Subject"] = "Password Reset - AI Investment Assistant"
            
            # Create reset link
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            reset_link = f"{frontend_url}/reset-password?token={token}"
            
            body = f"""
            <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>You requested a password reset for your AI Investment Assistant account.</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href="{reset_link}" style="background-color: #f44336; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">Reset Password</a></p>
                    <p>This link will expire in 1 hour for security reasons.</p>
                    <p>If you didn't request this reset, please ignore this email.</p>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(body, "html"))
            
            with smtplib.SMTP(settings.SMTP_HOST, getattr(settings, 'SMTP_PORT', 587)) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            log.info(f"Password reset email sent to {email}")
            
        except Exception as e:
            log.error(f"Failed to send password reset email to {email}: {e}")


# ========== AUTHENTICATION ENDPOINTS ==========

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister, background_tasks: BackgroundTasks):
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
        
        # Generate verification token and send email
        verification_token = TokenManager.generate_verification_token(user_id, new_user.email)
        background_tasks.add_task(
            EmailService.send_verification_email,
            new_user.email,
            verification_token
        )
        
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


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user_mongo),
    authorization: str = Header(None)
):
    """Logout current user and blacklist token"""
    try:
        # Extract token from Authorization header and blacklist it
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            TokenManager.blacklist_token(token)
        
        log.info(f"User logged out: {current_user['email']}")
        
        return {
            "message": "Successfully logged out",
            "email": current_user["email"]
        }
        
    except Exception as e:
        log.error(f"Logout error: {e}")
        # Still return success - logout should be idempotent
        return {
            "message": "Successfully logged out",
            "email": current_user.get("email", "unknown")
        }


@router.post("/verify-email/{token}")
async def verify_email(token: str):
    """Verify user email with token"""
    try:
        print(f"DEBUG: Starting verification for token: {token[:50]}...")
        
        # Verify the token
        payload = TokenManager.verify_token(token, "email_verification")
        print(f"DEBUG: Token payload: {payload}")
        
        if not payload:
            print("DEBUG: Token validation failed - invalid or expired")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Find the user
        user = await user_repo.find_by_email(payload["email"])
        print(f"DEBUG: Found user: {user['email'] if user else 'None'}")
        
        if not user:
            print("DEBUG: User not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if already verified
        if user.get("is_verified", False):
            print("DEBUG: User already verified")
            return {
                "message": "Email already verified",
                "email": user["email"]
            }
        
        # Update user verification status
        print(f"DEBUG: Updating verification status for user ID: {user['_id']}")
        success = await user_repo.update_one(
            str(user["_id"]),
            {"is_verified": True, "updated_at": datetime.now(timezone.utc)}
        )
        
        print(f"DEBUG: Update result: {success}")
        
        if not success:
            print("DEBUG: Failed to update verification status")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update verification status"
            )
        
        # Verify the update worked
        updated_user = await user_repo.find_by_email(payload["email"])
        print(f"DEBUG: User after update - is_verified: {updated_user.get('is_verified', 'Not found')}")
        
        log.info(f"Email verified for user: {user['email']}")
        
        return {
            "message": "Email successfully verified",
            "email": user["email"],
            "verified_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Exception occurred: {e}")
        log.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks
):
    """Request password reset email"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Find user by email
        user = await user_repo.find_by_email(request.email)
        if not user:
            # Don't reveal if email exists - security best practice
            return {
                "message": "If the email exists, a password reset link has been sent",
                "email": request.email
            }
        
        # Generate reset token
        reset_token = TokenManager.generate_reset_token(str(user["_id"]), user["email"])
        
        # Store reset token in database for additional security (optional)
        await user_repo.update_one(
            str(user["_id"]),
            {
                "reset_token": reset_token,
                "reset_token_created": datetime.now(timezone.utc)
            }
        )
        
        # Send email in background
        background_tasks.add_task(
            EmailService.send_password_reset_email,
            user["email"],
            reset_token
        )
        
        log.info(f"Password reset requested for: {user['email']}")
        
        return {
            "message": "If the email exists, a password reset link has been sent",
            "email": request.email
        }
        
    except Exception as e:
        log.error(f"Password reset request error: {e}")
        # Don't reveal internal errors
        return {
            "message": "If the email exists, a password reset link has been sent",
            "email": request.email
        }


@router.post("/reset-password/{token}")
async def reset_password(token: str, request: PasswordResetRequest):
    """Reset password with token"""
    try:
        # Validate password confirmation
        if request.new_password != request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        
        # Verify the reset token
        payload = TokenManager.verify_token(token, "password_reset")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Find the user
        user = await user_repo.find_by_email(payload["email"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify stored token (additional security)
        stored_token = user.get("reset_token")
        if stored_token != token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        # Hash the new password
        hashed_password = get_password_hash(request.new_password)
        
        # Update password and clear reset token
        success = await user_repo.update_one(
            str(user["_id"]),
            {
                "hashed_password": hashed_password,
                "updated_at": datetime.now(timezone.utc),
                "$unset": {"reset_token": "", "reset_token_created": ""}
            }
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        log.info(f"Password reset completed for user: {user['email']}")
        
        return {
            "message": "Password successfully reset",
            "email": user["email"],
            "reset_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.post("/resend-verification")
async def resend_verification_email(
    request: ForgotPasswordRequest,  # Reuse since it only needs email
    background_tasks: BackgroundTasks
):
    """Resend email verification"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Find user by email
        user = await user_repo.find_by_email(request.email)
        if not user:
            # Don't reveal if email exists
            return {
                "message": "If the email exists and is unverified, a verification link has been sent",
                "email": request.email
            }
        
        # Check if already verified
        if user.get("is_verified", False):
            return {
                "message": "Email is already verified",
                "email": request.email
            }
        
        # Generate new verification token
        verification_token = TokenManager.generate_verification_token(str(user["_id"]), user["email"])
        
        # Send email in background
        background_tasks.add_task(
            EmailService.send_verification_email,
            user["email"],
            verification_token
        )
        
        log.info(f"Verification email resent to: {user['email']}")
        
        return {
            "message": "If the email exists and is unverified, a verification link has been sent",
            "email": request.email
        }
        
    except Exception as e:
        log.error(f"Resend verification error: {e}")
        return {
            "message": "If the email exists and is unverified, a verification link has been sent",
            "email": request.email
        }
@router.post("/test/generate-verification-token")
async def generate_test_verification_token(email: str):
    """TEMPORARY: Generate verification token for testing"""
    user_repo: UserRepository = get_repository(UserRepository)
    user = await user_repo.find_by_email(email)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token = TokenManager.generate_verification_token(str(user["_id"]), user["email"])
    
    return {"verification_token": token}

@router.get("/debug/db-info")
async def debug_db_info():
    """Debug database connection"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Get database and collection info
        db_name = user_repo.db.name
        collection_name = user_repo.collection.name
        
        # Count documents
        user_count = await user_repo.collection.count_documents({})
        
        # Get one sample document
        sample = await user_repo.collection.find_one({})
        
        return {
            "database_name": db_name,
            "collection_name": collection_name,
            "document_count": user_count,
            "sample_document_keys": list(sample.keys()) if sample else None,
            "sample_email": sample.get("email") if sample else None
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/debug/find-user/{email}")
async def debug_find_user(email: str):
    """Debug user lookup"""
    try:
        user_repo: UserRepository = get_repository(UserRepository)
        
        # Try different query methods
        user1 = await user_repo.find_by_email(email)
        user2 = await user_repo.find_one({"email": email})
        user3 = await user_repo.collection.find_one({"email": email})
        
        # Get all users to see what's actually in the database
        all_users = await user_repo.find_many({})
        
        return {
            "search_email": email,
            "find_by_email": bool(user1),
            "find_one": bool(user2), 
            "direct_collection": bool(user3),
            "all_users_count": len(all_users),
            "all_emails": [u.get("email") for u in all_users if u.get("email")]
        }
    except Exception as e:
        return {"error": str(e)}