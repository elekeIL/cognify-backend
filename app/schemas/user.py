"""User schemas for API validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=100)


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    email: str
    full_name: str
    company: Optional[str] = None
    role: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)


class PasswordReset(BaseModel):
    """Schema for password reset request (Step 1: Request OTP)."""
    email: EmailStr


class PasswordResetVerifyOTP(BaseModel):
    """Schema for OTP verification (Step 2: Verify OTP)."""
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation (Step 3: Set new password)."""
    email: EmailStr
    reset_token: str = Field(min_length=32)
    new_password: str = Field(min_length=8, max_length=100)


class OTPVerifyResponse(BaseModel):
    """Response after successful OTP verification."""
    message: str
    reset_token: str  # One-time token for password reset
