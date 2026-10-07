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
    ai_provider: str = "none"
    openrouter_api_key: str = ""
    openrouter_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
