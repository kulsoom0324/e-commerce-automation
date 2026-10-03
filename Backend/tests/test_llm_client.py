# ═══════════════════════════════════════════════════════════════
# tests / test_llm_client.py
#
# PURPOSE: Unit tests for the LLMClient (Gemini-based).
#          All Gemini calls are mocked — no real API hits.
# ═══════════════════════════════════════════════════════════════

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.sdk.exceptions import LLMError
from src.sdk.llm.client import LLMClient


# ─── Empty API key behavior ───────────────────────────────────

@pytest.mark.asyncio
async def test_generate_raises_when_no_api_key(llm_client_no_key):
    """If GEMINI_API_KEY is empty, generate() should raise LLMError(503)."""
    with pytest.raises(LLMError) as exc_info:
        await llm_client_no_key.generate("Hello")
    assert exc_info.value.code == 503
    assert "GEMINI_API_KEY" in str(exc_info.value)


# ─── Lazy initialization ──────────────────────────────────────

def test_model_not_initialized_in_constructor(llm_client_with_key):
    """Model instance should be lazy — not created in __init__."""
    assert llm_client_with_key._model_instance is None


# ─── generate() with mocked Gemini ────────────────────────────

@pytest.mark.asyncio
async def test_generate_calls_gemini_and_returns_text(llm_client_with_key):
    """generate() should call Gemini and return response.text."""
    # Mock the model instance that _get_model() will return
    mock_response = MagicMock()
    mock_response.text = "Hello from Gemini!"

    mock_model = MagicMock()
    mock_model.generate_content = MagicMock(return_value=mock_response)

    # Patch _get_model to return our mock
    with patch.object(llm_client_with_key, "_get_model", return_value=mock_model):
        result = await llm_client_with_key.generate("Hi there")

    assert result == "Hello from Gemini!"
    assert llm_client_with_key.token_usage["calls"] == 1
    assert llm_client_with_key.token_usage["input"] > 0
    assert llm_client_with_key.token_usage["output"] > 0


@pytest.mark.asyncio
async def test_generate_with_system_prompt(llm_client_with_key):
    """System prompt should be prepended to the user prompt."""
    mock_response = MagicMock()
    mock_response.text = "OK"

    mock_model = MagicMock()
    mock_model.generate_content = MagicMock(return_value=mock_response)

    with patch.object(llm_client_with_key, "_get_model", return_value=mock_model):
        await llm_client_with_key.generate(
            "Test prompt",
            system="You are a helpful assistant.",
        )

    # Verify Gemini was called with combined prompt
    call_args = mock_model.generate_content.call_args
    full_prompt = call_args[0][0]
    assert "You are a helpful assistant." in full_prompt
    assert "Test prompt" in full_prompt


# ─── generate_structured() with mocked Gemini ──────────────────

@pytest.mark.asyncio
async def test_generate_structured_parses_json(llm_client_with_key):
    """generate_structured() should parse JSON from Gemini's response."""
    import json
    expected = {"sentiment": "positive", "score": 0.95}

    mock_response = MagicMock()
    mock_response.text = json.dumps(expected)

    mock_model = MagicMock()
    mock_model.generate_content = MagicMock(return_value=mock_response)

    with patch.object(llm_client_with_key, "_get_model", return_value=mock_model):
        result = await llm_client_with_key.generate_structured(
            "Analyze this",
            {"type": "object", "properties": {"sentiment": {"type": "string"}}},
        )

    assert result == expected
    assert result["sentiment"] == "positive"


# ─── Retry on transient errors ────────────────────────────────

@pytest.mark.asyncio
async def test_generate_retries_on_connection_error(llm_client_with_key):
    """ConnectionError should trigger retry, then succeed on 2nd attempt."""
    mock_response = MagicMock()
    mock_response.text = "Recovered!"

    mock_model = MagicMock()
    # First call raises ConnectionError, second call returns the response
    mock_model.generate_content = MagicMock(
        side_effect=[ConnectionError("network down"), mock_response]
    )

    with patch.object(llm_client_with_key, "_get_model", return_value=mock_model):
        # Patch sleep so test runs fast
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await llm_client_with_key.generate("Test")

    assert result == "Recovered!"
    assert mock_model.generate_content.call_count == 2


# ─── close() is safe to call ──────────────────────────────────

@pytest.mark.asyncio
async def test_close_clears_model_instance(llm_client_with_key):
    """close() should clear the model instance and not error."""
    llm_client_with_key._model_instance = MagicMock()
    await llm_client_with_key.close()
    assert llm_client_with_key._model_instance is None
