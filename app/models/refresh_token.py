# app/models/refresh_token.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from datetime import datetime, timezone
from app.db import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti = Column(String, primary_key=True, index=True)        # JWT ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))