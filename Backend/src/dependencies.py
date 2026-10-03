# ═══════════════════════════════════════════════════════════════
# src / dependencies.py
#
# PURPOSE: FastAPI dependency injection hub.
#          Database sessions, Redis Event Bus, and User Auth.
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from fastapi import HTTPException

from src.sdk.database import get_db, async_session_factory
from src.sdk.event_bus import RedisEventBus
from src.sdk.config import get_settings
from src.sdk.llm.client import LLMClient

logger = logging.getLogger(__name__)

# ─── Event Bus Singleton ──────────────────────────────────────
_event_bus: Optional[RedisEventBus] = None


async def get_event_bus() -> Optional[RedisEventBus]:
    """Return the singleton event bus instance.
    Raises 503 if event bus is not connected."""
    global _event_bus
    if _event_bus is None:
        raise HTTPException(status_code=503, detail="Event bus unavailable — Redis not connected")
    return _event_bus


async def init_event_bus():
    """Called during lifespan startup."""
    global _event_bus
    settings = get_settings()
    _event_bus = RedisEventBus(settings.REDIS_URL)
    try:
        await _event_bus.connect()
        logger.info("Event bus connected to Redis")
    except Exception as e:
        logger.warning(f"Redis not available — event bus disabled: {e}")
        _event_bus = None


async def close_event_bus():
    """Called during lifespan shutdown."""
    global _event_bus
    if _event_bus:
        await _event_bus.disconnect()
        _event_bus = None


# ─── LLM Client Singleton ─────────────────────────────────────
# Google Gemini client — shared across all agents for rate limiting
# and connection pooling. Lazy-initialized so empty API key doesn't
# crash the app at startup.

_llm_client: Optional[LLMClient] = None


async def get_llm_client() -> LLMClient:
    """Return the singleton LLM client instance.
    Raises LLMError if GEMINI_API_KEY is empty."""
    global _llm_client
    if _llm_client is None:
        settings = get_settings()
        # Use GEMINI_API_KEY specifically (LLM_API_KEY is legacy alias)
        api_key = settings.GEMINI_API_KEY or settings.LLM_API_KEY
        _llm_client = LLMClient(
            api_key=api_key,
            model=settings.LLM_MODEL,
        )
        logger.info("LLM client singleton initialized (model=%s)", settings.LLM_MODEL)
    return _llm_client


async def close_llm_client():
    """Called during lifespan shutdown."""
    global _llm_client
    if _llm_client is not None:
        await _llm_client.close()
        _llm_client = None
        logger.info("LLM client singleton closed")
