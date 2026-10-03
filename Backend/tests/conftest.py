# ═══════════════════════════════════════════════════════════════
# tests / conftest.py
#
# PURPOSE: Shared pytest fixtures for the Digital FTE test suite.
# ═══════════════════════════════════════════════════════════════

import pytest

from src.sdk.llm.client import LLMClient


# ─── LLM client fixtures ──────────────────────────────────────

@pytest.fixture
def llm_client_with_key() -> LLMClient:
    """LLM client with a fake API key — no real network calls made."""
    return LLMClient(api_key="test-fake-key", model="gemini-2.0-flash-exp")


@pytest.fixture
def llm_client_no_key() -> LLMClient:
    """LLM client with NO API key — should raise LLMError on first call."""
    return LLMClient(api_key="", model="gemini-2.0-flash-exp")
