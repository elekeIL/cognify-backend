"""Production-Ready Authentication Service — Secure JWT + Refresh Token Rotation"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import UserCreate, TokenResponse

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Precomputed fake hash to mitigate timing attacks
FAKE_HASHED_PASSWORD = pwd_context.hash(
    "this_is_a_fake_user_that_never_exists_2025"
)


class AuthService:
    """Production-grade authentication service."""

    # ─── Password ────────────────────────────────
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # ─── JWT Creation ───────────────────────────
    @staticmethod
    def _create_jwt(user_id: str, expires_delta: timedelta, token_type: str, jti: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "iat": now,
            "exp": expire,
            "type": token_type,
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # ─── Token Creation (access + refresh, store refresh in DB) ─────────
    @staticmethod
    async def create_tokens(db: AsyncSession, user_id: str) -> TokenResponse:
        access_jti = str(uuid.uuid4())
        access_token = AuthService._create_jwt(
            user_id=user_id,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            token_type="access",
            jti=access_jti,
        )

        refresh_jti = str(uuid.uuid4())
        refresh_token = AuthService._create_jwt(
            user_id=user_id,
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
            token_type="refresh",
            jti=refresh_jti,
        )

        db.add(
            RefreshToken(
                jti=refresh_jti,
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            )
        )
        await db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )

    # ─── Decode JWT ──────────────────────────────
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            return None

    # ─── User Lookup ─────────────────────────────
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    # ─── Registration ───────────────────────────
    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        if await AuthService.get_user_by_email(db, user_data.email.lower()):
            raise ValueError("Email already registered")

        user = User(
            email=user_data.email.lower(),
            hashed_password=AuthService.hash_password(user_data.password),
            full_name=user_data.full_name,
            company=user_data.company,
            role=user_data.role or "user",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    # ─── Secure Login (constant-time) ───────────
    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        user = await AuthService.get_user_by_email(db, email.lower())
        hashed_password = user.hashed_password if user else FAKE_HASHED_PASSWORD
        password_correct = pwd_context.verify(password, hashed_password)

        if not user or not password_correct or not user.is_active:
            return None

        user.last_login = datetime.now(timezone.utc)
        return user

    # ─── Refresh Access Token (Rotation) ────────
    @staticmethod
    async def refresh_access_token(db: AsyncSession, refresh_token: str) -> Optional[TokenResponse]:
        payload = AuthService.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        jti = payload["jti"]
        user_id = payload["sub"]

        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.jti == jti,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None

        user = await AuthService.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            return None

        # Revoke old token (one-time use)
        token_record.revoked = True

        # Issue new tokens
        return await AuthService.create_tokens(db, user_id)

    # ─── Logout Current Token ───────────────────
    @staticmethod
    async def logout(db: AsyncSession, refresh_token: str) -> bool:
        payload = AuthService.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return False

        jti = payload["jti"]
        result = await db.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        return result.rowcount > 0

    # ─── Logout All Devices ─────────────────────
    @staticmethod
    async def logout_all(db: AsyncSession, user_id: str) -> int:
        result = await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        return result.rowcount
