# ═══════════════════════════════════════════════════════════════
# fte_sdk / oauth / __init__.py
#
# PURPOSE: Universal OAuth module — handles auth flow for ALL
#          e-commerce platforms. User sirf "Allow" button dabata
#          hai, baaki sab yahan automatically hota hai.
#
# USED BY: backend oauth_routes.py, ALL platform connectors
# ═══════════════════════════════════════════════════════════════

from src.sdk.oauth.base import OAuthFlow, OAuthResult
from src.sdk.oauth.providers import OAuthProviderRegistry, OAuthProviderConfig
from src.sdk.oauth.tokens import TokenManager

__all__ = [
    "OAuthFlow",
    "OAuthResult",
    "OAuthProviderRegistry",
    "OAuthProviderConfig",
    "TokenManager",
]
