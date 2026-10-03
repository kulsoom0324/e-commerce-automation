# ═══════════════════════════════════════════════════════════════
# fte_sdk / exceptions.py
#
# PURPOSE: Standardized error classes. Har agent aur SDK module
#          specific exceptions throw karta hai → caller easily
#          catch aur handle kar sakta hai.
#
# USED BY: ALL — error propagation across all agents
# ═══════════════════════════════════════════════════════════════


class FTEError(Exception):
    """Base exception for all FTE errors."""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


class ConfigError(FTEError):
    """Missing/invalid configuration or env vars."""
    pass


class AuthError(FTEError):
    """Invalid token, expired credentials, HMAC mismatch."""
    pass


class EventError(FTEError):
    """Event publish/subscribe failed — bus disconnected or channel error."""
    pass


class AgentError(FTEError):
    """Agent-level failure — handler error, external API error."""
    pass


class CouncilError(FTEError):
    """LLM council pipeline failed — step timed out or LLM error."""
    pass


class LLMError(FTEError):
    """LLM API returned error, rate limited, or timeout."""
    pass
