"""
Application configuration — loads all environment variables from .env
and exposes them as a typed Settings object via Pydantic.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    # ── PostgreSQL ──────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ─────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Gmail SMTP ──────────────────────────────────────────────
    GMAIL_ADDRESS: str
    GMAIL_APP_PASSWORD: str

    # ── OTP / Lockout ───────────────────────────────────────────
    OTP_EXPIRY_SECONDS: int = 300
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    model_config = {
        "env_file": str(ENV_PATH),
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
