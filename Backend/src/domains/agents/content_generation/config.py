# ═══════════════════════════════════════════════════════════════
# agents / content_generation / config.py
#
# PURPOSE: Content Generation Agent settings.
#          LLM model selection, image model (Gemini/DALL-E),
#          auto-approve defaults.
#
# USED BY: handler.py, worker.py, main.py, api.py
# ═══════════════════════════════════════════════════════════════

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Content Generation Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/digital_fte"
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM — which model to use for content council
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

    # Image Generation — Gemini or DALL-E 3
    GEMINI_API_KEY: str = ""
    DALLE_API_KEY: str = ""
    IMAGE_MODEL_DEFAULT: str = "gemini-2.0-flash-exp"
    IMAGE_COUNT: int = 1
    IMAGE_SIZE: str = "1024x1024"

    # Auto-approve: if True, posts skip human review
    HUMAN_REVIEW_REQUIRED: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8003

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
