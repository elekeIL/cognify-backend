"""
Production-Grade Password Reset Service.

Security features:
- Cryptographically secure OTP generation
- OTPs stored as hashes (never plain text)
- Time-limited expiration (configurable, default 10 minutes)
- Single-use enforcement
- Rate limiting via attempt tracking
- Constant-time comparison to prevent timing attacks
- Session invalidation after password reset
"""

import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.models.password_reset import PasswordResetOTP
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)
settings = get_settings()

# Use same password context as auth for hashing OTPs
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OTP Configuration
OTP_LENGTH = 6  # 6-digit OTP
OTP_EXPIRY_MINUTES = 10  # OTP valid for 10 minutes
MAX_FAILED_ATTEMPTS = 5  # Lock out after 5 failed attempts
MAX_ACTIVE_OTPS_PER_USER = 3  # Limit active OTPs per user


class PasswordResetService:
    """Production-grade password reset service with OTP verification."""

    # ─────────────────────────────────────────────────────────────
    # OTP Generation
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        """
        Generate a cryptographically secure 6-digit OTP.
        Uses secrets module for CSPRNG.
        """
        # Generate random number between 100000 and 999999
        otp = secrets.randbelow(900000) + 100000
        return str(otp)

    @staticmethod
    def hash_otp(otp: str) -> str:
        """Hash the OTP for secure storage."""
        return pwd_context.hash(otp)

    @staticmethod
    def verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
        """Verify OTP against hash using constant-time comparison."""
        return pwd_context.verify(plain_otp, hashed_otp)

    # ─────────────────────────────────────────────────────────────
    # Request Password Reset (Step 1)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def create_reset_otp(
        db: AsyncSession,
        user: User,
        expiry_minutes: int = OTP_EXPIRY_MINUTES,
    ) -> str:
        """
        Create a password reset OTP for a user.

        Args:
            db: Database session
            user: User requesting reset
            expiry_minutes: OTP validity period

        Returns:
            Plain text OTP (to be sent via email - NEVER logged)
        """
        # Clean up old/expired OTPs for this user
        await PasswordResetService._cleanup_user_otps(db, user.id)

        # Check rate limit (max active OTPs)
        active_count = await PasswordResetService._count_active_otps(db, user.id)
        if active_count >= MAX_ACTIVE_OTPS_PER_USER:
            # Invalidate oldest OTP to make room
            await PasswordResetService._invalidate_oldest_otp(db, user.id)

        # Generate new OTP
        plain_otp = PasswordResetService.generate_otp()
        otp_hash = PasswordResetService.hash_otp(plain_otp)

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        # Create OTP record
        otp_record = PasswordResetOTP(
            user_id=user.id,
            otp_hash=otp_hash,
            expires_at=expires_at,
            max_attempts=MAX_FAILED_ATTEMPTS,
        )
        db.add(otp_record)
        await db.flush()

        logger.info(f"Password reset OTP created for user {user.id[:8]}...")

        # Return plain OTP for email sending
        # WARNING: Do NOT log the plain OTP
        return plain_otp

    # ─────────────────────────────────────────────────────────────
    # Verify OTP (Step 2)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def verify_otp(
        db: AsyncSession,
        email: str,
        otp: str,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Verify the OTP for a password reset request.

        Args:
            db: Database session
            email: User's email address
            otp: The OTP to verify

        Returns:
            Tuple of (success: bool, reset_token: Optional[str], message: str)
            - success: True if OTP is valid
            - reset_token: One-time token for password reset (if success)
            - message: Human-readable status message
        """
        # Get user by email
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal that user doesn't exist
            # Simulate verification time to prevent timing attacks
            PasswordResetService.hash_otp("000000")
            return False, None, "Invalid or expired OTP"

        # Get active OTPs for user (not used, not expired, not locked out)
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PasswordResetOTP).where(
                and_(
                    PasswordResetOTP.user_id == user.id,
                    PasswordResetOTP.is_used == False,
                    PasswordResetOTP.expires_at > now,
                    PasswordResetOTP.failed_attempts < PasswordResetOTP.max_attempts,
                )
            ).order_by(PasswordResetOTP.created_at.desc())
        )
        otp_records = result.scalars().all()

        if not otp_records:
            return False, None, "Invalid or expired OTP"

        # Try to verify against any valid OTP
        verified_otp = None
        for otp_record in otp_records:
            if PasswordResetService.verify_otp_hash(otp, otp_record.otp_hash):
                verified_otp = otp_record
                break
            else:
                # Increment failed attempts for this OTP
                otp_record.failed_attempts += 1
                if otp_record.is_locked_out():
                    logger.warning(
                        f"OTP locked out for user {user.id[:8]}... after {otp_record.failed_attempts} failed attempts"
                    )

        if not verified_otp:
            await db.flush()
            return False, None, "Invalid or expired OTP"

        # OTP verified successfully - generate one-time reset token
        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = PasswordResetService.hash_otp(reset_token)

        # Mark OTP as used and store reset token hash
        verified_otp.is_used = True
        verified_otp.used_at = datetime.now(timezone.utc)
        # Store the reset token hash temporarily (reuse otp_hash field)
        # The OTP record becomes a "reset session"
        verified_otp.otp_hash = reset_token_hash

        await db.flush()

        logger.info(f"OTP verified successfully for user {user.id[:8]}...")

        return True, reset_token, "OTP verified successfully"

    # ─────────────────────────────────────────────────────────────
    # Reset Password (Step 3)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def reset_password(
        db: AsyncSession,
        email: str,
        reset_token: str,
        new_password: str,
    ) -> Tuple[bool, str]:
        """
        Reset the user's password after OTP verification.

        Args:
            db: Database session
            email: User's email address
            reset_token: The reset token from verify_otp
            new_password: New password to set

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Get user
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "Invalid reset token"

        # Find verified OTP with matching reset token
        # Look for used OTPs (verified) within a short time window (5 minutes)
        time_limit = datetime.now(timezone.utc) - timedelta(minutes=5)

        result = await db.execute(
            select(PasswordResetOTP).where(
                and_(
                    PasswordResetOTP.user_id == user.id,
                    PasswordResetOTP.is_used == True,
                    PasswordResetOTP.used_at > time_limit,
                )
            ).order_by(PasswordResetOTP.used_at.desc())
        )
        otp_records = result.scalars().all()

        # Verify reset token against stored hash
        valid_record = None
        for otp_record in otp_records:
            if PasswordResetService.verify_otp_hash(reset_token, otp_record.otp_hash):
                valid_record = otp_record
                break

        if not valid_record:
            return False, "Invalid or expired reset token"

        # Validate password strength
        if len(new_password) < 8:
            return False, "Password must be at least 8 characters"

        # Update password
        user.hashed_password = pwd_context.hash(new_password)

        # Delete the used OTP record
        await db.delete(valid_record)

        # Invalidate ALL existing sessions/tokens for this user
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .values(revoked=True)
        )

        # Clean up any other OTPs for this user
        await db.execute(
            delete(PasswordResetOTP).where(PasswordResetOTP.user_id == user.id)
        )

        await db.flush()

        logger.info(f"Password reset completed for user {user.id[:8]}..., all sessions invalidated")

        return True, "Password reset successfully"

    # ─────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _cleanup_user_otps(db: AsyncSession, user_id: str) -> int:
        """Remove expired and used OTPs for a user."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(PasswordResetOTP).where(
                and_(
                    PasswordResetOTP.user_id == user_id,
                    (PasswordResetOTP.expires_at < now) | (PasswordResetOTP.is_used == True),
                )
            )
        )
        return result.rowcount

    @staticmethod
    async def _count_active_otps(db: AsyncSession, user_id: str) -> int:
        """Count active (valid) OTPs for a user."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PasswordResetOTP).where(
                and_(
                    PasswordResetOTP.user_id == user_id,
                    PasswordResetOTP.is_used == False,
                    PasswordResetOTP.expires_at > now,
                )
            )
        )
        return len(result.scalars().all())

    @staticmethod
    async def _invalidate_oldest_otp(db: AsyncSession, user_id: str) -> None:
        """Invalidate the oldest active OTP for a user."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PasswordResetOTP).where(
                and_(
                    PasswordResetOTP.user_id == user_id,
                    PasswordResetOTP.is_used == False,
                    PasswordResetOTP.expires_at > now,
                )
            ).order_by(PasswordResetOTP.created_at.asc()).limit(1)
        )
        oldest = result.scalar_one_or_none()
        if oldest:
            await db.delete(oldest)

    @staticmethod
    async def cleanup_expired_otps(db: AsyncSession) -> int:
        """Global cleanup of all expired OTPs. Call periodically."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(PasswordResetOTP).where(PasswordResetOTP.expires_at < now)
        )
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired password reset OTPs")
        return count
