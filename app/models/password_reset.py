"""Password Reset OTP model for secure password recovery."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PasswordResetOTP(Base):
    """
    Stores hashed OTPs for password reset requests.

    Security features:
    - OTP is stored as a hash (never plain text)
    - Time-limited expiration
    - Single-use enforcement
    - Rate limiting via attempt tracking
    """

    __tablename__ = "password_reset_otps"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # OTP is stored hashed - NEVER store plain text
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Expiration timestamp
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    # Single-use enforcement
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Track failed verification attempts for rate limiting
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)

    # Maximum allowed failed attempts before invalidation
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<PasswordResetOTP(id={self.id}, user_id={self.user_id}, used={self.is_used})>"

    def is_valid(self) -> bool:
        """Check if the OTP is still valid (not expired, not used, not locked out)."""
        now = datetime.now(timezone.utc)
        return (
            not self.is_used
            and self.expires_at > now
            and self.failed_attempts < self.max_attempts
        )

    def is_locked_out(self) -> bool:
        """Check if OTP is locked out due to too many failed attempts."""
        return self.failed_attempts >= self.max_attempts
