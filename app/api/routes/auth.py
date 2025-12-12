"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.dependencies import DbSession, CurrentUser
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    PasswordChange,
    PasswordReset,
)
from app.services.auth_service import AuthService


router = APIRouter()


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
# Forgot Password
# ─────────────────────────────────────────────

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(password_reset: PasswordReset, db: DbSession):
    """
    Request a password reset email.
    Always returns success to prevent enumeration.
    """
    user = await AuthService.get_user_by_email(db, password_reset.email)

    if user:
        # TODO: Implement real email sending
        print(f"Password reset requested for: {password_reset.email}")

    return MessageResponse(
        message="If an account with this email exists, a password reset link has been sent."
    )


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
