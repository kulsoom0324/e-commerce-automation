# ═══════════════════════════════════════════════════════════════
# fte_sdk / llm / client.py
#
# PURPOSE: LLM API client wrapper. Rate-limited, retry, token
#          tracking. content_generation, comment_engagement,
#          customer_support, collaboration — sab agents LLM calls
#          ke liye yehi use karte hain.
#
# PROVIDER: Google Gemini (gemini-3.5-flash-lite default)
# USED BY: content_generation, comment_engagement, customer_support,
#          collaboration_orchestrator
# ═══════════════════════════════════════════════════════════════

import asyncio
import json
import logging
from typing import Optional

import google.generativeai as genai

from src.sdk.exceptions import LLMError

logger = logging.getLogger(__name__)


# ─── Retryable network errors (transient — safe to retry) ─────
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Exponential backoff delays (seconds): 0.5s, 1.5s, 3.0s
RETRY_DELAYS = (0.5, 1.5, 3.0)


# ─── LLMClient ────────────────────────────────────────────────
# Google Gemini API wrapper.
# Features:
#   - Rate limiting (max 3 concurrent calls via Semaphore)
#   - Retry logic (exponential backoff on transient network errors)
#   - Token tracking (rough estimate via character count)
#   - Structured JSON output via Gemini's native response_schema

class LLMClient:
    """Wrapper around Google Gemini API — rate-limited + retry."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        max_concurrent: int = 3,
    ):
        self.api_key = api_key
        self.model = model
        self._rate_limiter = asyncio.Semaphore(max_concurrent)
        self._model_instance = None  # Lazy init on first call
        self.token_usage = {"input": 0, "output": 0, "calls": 0}

    # ─── _get_model() ─────────────────────────────────────────
    # Lazy initialization — SDK instance is created on first use
    # so an empty API key doesn't crash the app at startup.

    def _get_model(self):
        if self._model_instance is None:
            if not self.api_key:
                raise LLMError(
                    "GEMINI_API_KEY is empty — cannot call LLM. "
                    "Set GEMINI_API_KEY in your .env file.",
                    code=503,
                )

            genai.configure(api_key=self.api_key)

            self._model_instance = genai.GenerativeModel(
                self.model
            )

            logger.info(
                "LLM client initialized with model: %s",
                self.model,
            )

        return self._model_instance

    # ─── generate() ──────────────────────────────────────────
    # Send a text prompt to the LLM and get a text response.
    # Used by: content_generation, comment_engagement,
    #          customer_support, analytics_insights,
    #          collaboration_orchestrator

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1000,
    ) -> str:
        """Send prompt to LLM, return text response.

        Rate-limited to max_concurrent calls.
        """

        async with self._rate_limiter:
            model = self._get_model()

            # Combine system + user prompt.
            # Gemini uses a single prompt string.
            full_prompt = (
                f"{system}\n\n{prompt}"
                if system
                else prompt
            )

            # Try with exponential backoff.
            for attempt, delay in enumerate(
                (0.0,) + RETRY_DELAYS
            ):
                if delay > 0:
                    await asyncio.sleep(delay)

                try:
                    # Gemini SDK is sync — run in a thread
                    # to avoid blocking the async event loop.
                    response = await asyncio.to_thread(
                        model.generate_content,
                        full_prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=max_tokens,
                        ),
                    )

                    # Track token usage.
                    # Rough estimate: 1 token ≈ 4 characters.
                    response_text = response.text

                    self.token_usage["input"] += (
                        len(full_prompt) // 4
                    )
                    self.token_usage["output"] += (
                        len(response_text) // 4
                    )
                    self.token_usage["calls"] += 1

                    logger.info(
                        "LLM call #%d "
                        "(in=%d, out=%d tokens, model=%s)",
                        self.token_usage["calls"],
                        self.token_usage["input"],
                        self.token_usage["output"],
                        self.model,
                    )

                    return response_text

                except RETRYABLE_EXCEPTIONS as e:
                    if attempt >= len(RETRY_DELAYS):
                        logger.error(
                            "LLM call failed after %d retries: %s",
                            len(RETRY_DELAYS),
                            e,
                        )

                        raise LLMError(
                            f"Gemini call failed after retries: {e}",
                            code=502,
                        ) from e

                    logger.warning(
                        "LLM retry %d/%d: %s",
                        attempt + 1,
                        len(RETRY_DELAYS),
                        e,
                    )

                    continue

                except Exception as e:
                    # Non-retryable error.
                    logger.exception(
                        "LLM call failed with non-retryable error: %s",
                        e,
                    )

                    raise LLMError(
                        f"Gemini error: {str(e)}",
                        code=500,
                    ) from e

            # Should never reach here.
            raise LLMError(
                "LLM call exhausted retries",
                code=502,
            )

    # ─── generate_structured() ───────────────────────────────
    # Send a prompt + JSON schema → LLM returns structured dict.
    # Uses Gemini's native response_schema for JSON output.
    # For: sentiment scores, classification, extraction.

    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
    ) -> dict:
        """Get validated structured JSON output from LLM.

        Uses Gemini's response_schema parameter.
        """

        async with self._rate_limiter:
            model = self._get_model()

            for attempt, delay in enumerate(
                (0.0,) + RETRY_DELAYS
            ):
                if delay > 0:
                    await asyncio.sleep(delay)

                try:
                    response = await asyncio.to_thread(
                        model.generate_content,
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                        ),
                    )

                    self.token_usage["calls"] += 1

                    logger.info(
                        "LLM structured call #%d",
                        self.token_usage["calls"],
                    )

                    # Parse JSON response.
                    return json.loads(response.text)

                except RETRYABLE_EXCEPTIONS as e:
                    if attempt >= len(RETRY_DELAYS):
                        raise LLMError(
                            f"Gemini structured call failed: {e}",
                            code=502,
                        ) from e

                    logger.warning(
                        "Gemini structured retry %d: %s",
                        attempt + 1,
                        e,
                    )

                    continue

                except json.JSONDecodeError as e:
                    raise LLMError(
                        f"Gemini returned invalid JSON: {e}",
                        code=500,
                    ) from e

                except Exception as e:
                    logger.exception(
                        "LLM structured call failed: %s",
                        e,
                    )

                    raise LLMError(
                        f"Gemini structured error: {str(e)}",
                        code=500,
                    ) from e

            raise LLMError(
                "LLM structured call exhausted retries",
                code=502,
            )

    # ─── close() ──────────────────────────────────────────────
    # Cleanup — clear the lazy SDK model instance.

    async def close(self) -> None:
        """Close the LLM client and release resources."""

        self._model_instance = None

        logger.info("LLM client closed")