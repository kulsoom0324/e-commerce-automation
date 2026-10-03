# ═══════════════════════════════════════════════════════════════
# fte_sdk / oauth / base.py
#
# PURPOSE: OAuth flow base class — har platform ka OAuth flow
#          isko extend karta hai. Handles:
#          1. Generate authorization URL (user ko redirect)
#          2. Exchange code → access_token
#          3. Refresh token when expired
#
# USED BY: backend oauth routes, platform connectors
# ═══════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class OAuthResult:
    """Result of OAuth token exchange or refresh."""
    access_token: str
    refresh_token: str = ""
    token_expires_at: Optional[datetime] = None
    store_id: Optional[str] = None          # Platform's own store ID
    store_name: str = ""
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class OAuthFlow(ABC):
    """Abstract OAuth flow for a platform.

    User experience:
    1. get_authorize_url() → link generate karo
    2. User ko link pe bhejo → "Allow" dabata hai
    3. Platform callback karega code ke saath
    4. exchange_code(code) → access_token milta hai
    5. (Optional) refresh_token(token) → token refresh
    """

    platform: str = ""

    @abstractmethod
    async def get_authorize_url(self, redirect_uri: str, state: str = "") -> str:
        """Generate the URL where user clicks 'Allow'.
        Example: https://shopify.com/admin/oauth/authorize?client_id=...&scope=...
        """
        pass

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthResult:
        """Exchange authorization code for access token.
        Called when platform redirects back with ?code=...
        """
        pass

    async def refresh_token(self, refresh_token: str) -> OAuthResult:
        """Refresh an expired token. Override for platforms with short-lived tokens."""
        raise NotImplementedError(f"{self.platform} does not support token refresh")

    @abstractmethod
    async def verify_token(self, access_token: str) -> bool:
        """Check if token is still valid (lightweight call)."""
        pass
