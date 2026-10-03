# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / config.py
#
# PURPOSE: Content Scheduling Agent settings.
#          Platform API keys, scheduler interval.
#
# USED BY: handler.py, scheduler.py, worker.py
# ═══════════════════════════════════════════════════════════════

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Content Scheduling Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/digital_fte"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Meta / Instagram / Facebook
    META_ACCESS_TOKEN: str = ""

    # TikTok
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""

    # LinkedIn
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""

    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 120  # 2 minutes
    MAX_RETRIES: int = 3

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
