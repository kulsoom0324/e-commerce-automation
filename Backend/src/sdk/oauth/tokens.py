# ═══════════════════════════════════════════════════════════════
# fte_sdk / oauth / tokens.py
#
# PURPOSE: Token management — encrypt, decrypt, auto-refresh.
#          PlatformAuth tokens ko securely store karta hai using
#          fte_sdk/crypto.py (Fernet symmetric encryption).
#
# USED BY: platform connectors, backend API, agent handlers
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone
from typing import Optional

from src.sdk.crypto import encrypt_token, decrypt_token
from src.sdk.config import get_settings
from src.sdk.platforms.base import PlatformAuth
from src.sdk.oauth.base import OAuthResult

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages token lifecycle — encrypt, decrypt, auto-refresh.

    User sirf "Allow" dabata hai, token management automatically hota hai:
    1. encrypt() → token store karne se pehle encrypt karo
    2. decrypt() → token use karne se pehle decrypt karo
    3. needs_refresh() → check if token is about to expire
    4. build_auth() → from Store record → PlatformAuth ready to use
    """

    def __init__(self):
        self.settings = get_settings()
        self.encryption_key = self.settings.ENCRYPTION_KEY

    # ─── Encrypt / Decrypt ──────────────────────────────────────
    # Tokens at rest encrypt. Dev mode mein key na ho to plaintext.

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a token before storing in DB."""
        return encrypt_token(plaintext, self.encryption_key)

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a token after reading from DB."""
        return decrypt_token(ciphertext, self.encryption_key)

    # ─── Build PlatformAuth from Store record ───────────────────
    # DB se Store record aaya → decrypt tokens → PlatformAuth banao.

    def build_auth(self, store: any) -> PlatformAuth:
        """Build PlatformAuth from a Store DB record.
        Decrypts tokens automatically.
        """
        return PlatformAuth(
            platform=store.platform,
            store_id=store.id,
            access_token=self.decrypt(store.access_token),
            refresh_token=self.decrypt(store.refresh_token) if store.refresh_token else "",
            token_expires_at=store.token_expires_at if hasattr(store, 'token_expires_at') else None,
            store_url=getattr(store, 'platform_store_id', ''),
        )

    # ─── Token Refresh Check ────────────────────────────────────
    # Check if token needs refresh (1 day before expiry).

    def needs_refresh(self, auth: PlatformAuth) -> bool:
        """Check if token expires within 1 day (or already expired)."""
        if not auth.token_expires_at:
            return False  # Permanent token (Shopify, WooCommerce)
        now = datetime.now(timezone.utc)
        expires = auth.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return (expires - now).total_seconds() < 86400  # 1 day

    # ─── Save OAuth Result to Store ────────────────────────────
    # OAuth exchange / refresh ke result ko store-ready format mein convert.

    def prepare_store_data(self, result: OAuthResult) -> dict:
        """Convert OAuthResult → dict for DB store update.
        Tokens are encrypted automatically.
        """
        data = {
            "access_token": self.encrypt(result.access_token),
        }
        if result.refresh_token:
            data["refresh_token"] = self.encrypt(result.refresh_token)
        if result.token_expires_at:
            data["token_expires_at"] = result.token_expires_at
        if result.store_id:
            data["platform_store_id"] = result.store_id
        if result.store_name:
            data["name"] = result.store_name
        return data
