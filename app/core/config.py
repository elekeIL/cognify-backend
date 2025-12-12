"""Application configuration settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Cognify API"
    app_env: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./cognify.db"

    # JWT Authentication
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM Configuration
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "openai"  # "openai" or "anthropic"

    # File Upload
    max_file_size_mb: int = 10
    upload_dir: str = "./uploads"
    allowed_extensions: str = "pdf,docx,txt"

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Audio
    audio_output_dir: str = "./uploads/audio"

    # Base URL (for generating audio URLs etc.) - set via BASE_URL env var in production
    base_url: str = "http://localhost:8000"

    @property
    def effective_base_url(self) -> str:
        """Get base URL, constructing from host/port if not explicitly set."""
        if self.base_url and self.base_url != "http://localhost:8000":
            return self.base_url.rstrip("/")
        # Fallback to constructed URL
        scheme = "https" if self.app_env == "production" else "http"
        host = self.host if self.host != "0.0.0.0" else "localhost"
        return f"{scheme}://{host}:{self.port}"

    # Security
    allowed_hosts: str = "*"

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Get allowed hosts as a list."""
        return [host.strip() for host in self.allowed_hosts.split(",")]

    @property
    def environment(self) -> str:
        """Alias for app_env."""
        return self.app_env

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Get allowed extensions as a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
