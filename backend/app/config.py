"""All settings come from environment variables / the root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # LMS_ prefix: a machine-wide DATABASE_URL from another project can never leak in.
    model_config = SettingsConfigDict(env_file=ROOT_ENV, env_prefix="LMS_", extra="ignore")

    database_url: str
    test_database_url: str = ""
    jwt_secret: str
    jwt_expire_minutes: int = 480
    loan_days: int = 14
    fine_per_day: int = 5
    max_active_loans: int = 3
    cors_origins: str = "http://localhost:5173"
    # Auth cookie: httpOnly so page JavaScript (and any XSS) can never read the JWT.
    # Must be true behind HTTPS; false only for plain-http local dev.
    cookie_secure: bool = False
    # Login throttling: failed attempts allowed inside the window before 429.
    login_max_failures: int = 5          # per IP + email (guessing one account's password)
    login_max_failures_per_ip: int = 20  # per IP across all emails (credential stuffing)
    login_window_seconds: int = 900
    # AI: "none" = keyword search + templated answer; "openrouter" = embeddings + Claude via OpenRouter
    ai_provider: str = "none"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-haiku-4.5"   # the LLM that writes answers
    embedding_model: str = "nvidia/nemotron-3-embed-1b:free"
    embedding_dim: int = 2048
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
