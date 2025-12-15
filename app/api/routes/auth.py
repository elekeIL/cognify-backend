"""Authentication endpoints."""

import logging
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel

from app.core.dependencies import DbSession, CurrentUser
from app.core.rate_limiter import rate_limiter, get_client_ip
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    PasswordChange,
    PasswordReset,
    PasswordResetVerifyOTP,
    PasswordResetConfirm,
    OTPVerifyResponse,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)
router = APIRouter()


def check_rate_limit(request: Request, limit_type: str, identifier: str) -> None:
    """Check rate limit and raise HTTPException if exceeded."""
    allowed, retry_after = rate_limiter.is_allowed(limit_type, identifier)
    if not allowed:
        logger.warning(f"Rate limit exceeded for {limit_type}: {identifier[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


# ─────────────────────────────────────────────
# Refresh Request Schema
# ─────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# ─────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: DbSession):
    """
    Register a new user.
    Returns access and refresh tokens.
    """
    try:
        user = await AuthService.create_user(db, user_data)
        return await AuthService.create_tokens(db, user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: DbSession):
    """
    Authenticate a user.
    Returns access and refresh tokens.
    """
    user = await AuthService.authenticate_user(
        db, credentials.email, credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return await AuthService.create_tokens(db, user.id)


# ─────────────────────────────────────────────
# Refresh Token (Rotation)
# ─────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: DbSession):
    """
    Rotate refresh token and get a new access token + refresh token.
    """
    tokens = await AuthService.refresh_access_token(db, body.refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return tokens


# ─────────────────────────────────────────────
# Current User
# ─────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: CurrentUser):
    """Return authenticated user's info."""
    return current_user


# ─────────────────────────────────────────────
# Update Profile
# ─────────────────────────────────────────────

@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Update the current user's profile.
    """
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name
    if user_data.company is not None:
        current_user.company = user_data.company
    if user_data.role is not None:
        current_user.role = user_data.role

    await db.flush()
    await db.refresh(current_user)
    return current_user


# ─────────────────────────────────────────────
# Change Password
# ─────────────────────────────────────────────

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: CurrentUser,
    db: DbSession,
):
    """
    Change the user's password.
    Requires current password.
    """
    if not AuthService.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = AuthService.hash_password(password_data.new_password)
    await db.flush()

    return MessageResponse(message="Password changed successfully")


# ─────────────────────────────────────────────
# Forgot Password - Step 1: Request OTP
# ─────────────────────────────────────────────

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(password_reset: PasswordReset, request: Request, db: DbSession):
    """
    Request a password reset OTP.

    Always returns the same message to prevent user enumeration.
    If the email exists, an OTP will be sent.

    Rate limited: 5 requests per 15 minutes per IP, 3 per hour per email.
    """
    client_ip = get_client_ip(request)
    email = password_reset.email.lower()

    # Check rate limits
    check_rate_limit(request, "password_reset_ip", client_ip)
    check_rate_limit(request, "password_reset_email", email)

    email_service = get_email_service()

    # Get user by email
    user = await AuthService.get_user_by_email(db, password_reset.email)

    # For simulation/demo mode, we'll return a special response
    # In production with SMTP configured, this would send a real email
    otp_for_demo = None

    if user and user.is_active:
        try:
            # Generate OTP
            otp = await PasswordResetService.create_reset_otp(db, user)

            # Check if email service is configured
            if email_service.is_configured:
                # Send OTP via email (production mode)
                await email_service.send_password_reset_otp(
                    to_email=user.email,
                    otp=otp,
                    user_name=user.full_name or "User",
                )
                logger.info(f"Password reset OTP sent to {user.email[:3]}***")
            else:
                # Simulation mode - store OTP for demo response
                otp_for_demo = otp
                logger.info(f"[SIMULATION MODE] Password reset OTP for {user.email[:3]}***: {otp}")

        except Exception as e:
            # Log error but don't expose to user
            logger.error(f"Failed to process password reset: {e}")

    # Build response message
    if otp_for_demo:
        # Simulation mode - include OTP in response for demo
        return MessageResponse(
            message=f"[SIMULATION MODE] Email not configured. Your verification code is: {otp_for_demo}. In production, this would be sent via email."
        )
    else:
        # Production mode - generic message
        return MessageResponse(
            message="If an account with this email exists, a verification code has been sent."
        )


# ─────────────────────────────────────────────
# Forgot Password - Step 2: Verify OTP
# ─────────────────────────────────────────────

@router.post("/forgot-password/verify", response_model=OTPVerifyResponse)
async def verify_reset_otp(data: PasswordResetVerifyOTP, request: Request, db: DbSession):
    """
    Verify the password reset OTP.

    Returns a one-time reset token if OTP is valid.
    This token is required for the final password reset step.

    Rate limited: 10 attempts per 15 minutes per IP, 5 per email.
    """
    client_ip = get_client_ip(request)
    email = data.email.lower()

    # Check rate limits
    check_rate_limit(request, "otp_verify_ip", client_ip)
    check_rate_limit(request, "otp_verify_email", email)

    success, reset_token, message = await PasswordResetService.verify_otp(
        db=db,
        email=data.email,
        otp=data.otp,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Reset rate limits for this email after successful verification
    rate_limiter.reset("otp_verify_email", email)

    return OTPVerifyResponse(
        message=message,
        reset_token=reset_token,
    )


# ─────────────────────────────────────────────
# Forgot Password - Step 3: Reset Password
# ─────────────────────────────────────────────

@router.post("/forgot-password/reset", response_model=MessageResponse)
async def reset_password(data: PasswordResetConfirm, request: Request, db: DbSession):
    """
    Reset the password using the reset token from OTP verification.

    This endpoint:
    - Validates the reset token
    - Updates the password
    - Invalidates ALL existing sessions
    - Sends confirmation email
    """
    email_service = get_email_service()

    success, message = await PasswordResetService.reset_password(
        db=db,
        email=data.email,
        reset_token=data.reset_token,
        new_password=data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Send confirmation email
    user = await AuthService.get_user_by_email(db, data.email)
    if user:
        try:
            await email_service.send_password_reset_confirmation(
                to_email=user.email,
                user_name=user.full_name or "User",
            )
        except Exception as e:
            logger.error(f"Failed to send password reset confirmation email: {e}")

    return MessageResponse(message=message)


# ─────────────────────────────────────────────
# Delete Account
# ─────────────────────────────────────────────

@router.delete("/account", response_model=MessageResponse)
async def delete_account(current_user: CurrentUser, db: DbSession):
    """
    Permanently delete the current user's account.
    """
    await db.delete(current_user)
    await db.flush()

    return MessageResponse(message="Account deleted successfully")
