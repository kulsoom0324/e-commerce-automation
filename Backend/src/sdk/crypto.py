# ═══════════════════════════════════════════════════════════════
# fte_sdk / crypto.py
#
# PURPOSE: Encrypt/decrypt sensitive tokens (Shopify access tokens)
#          at rest using Fernet symmetric encryption.
#
# USED BY: backend api.py (encrypt on save), agent handler (decrypt on read)
# ═══════════════════════════════════════════════════════════════

import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# ─── Key helpers ──────────────────────────────────────────────

def _derive_key(raw_key: str) -> bytes:
    """Convert any string key to a valid 32-byte Fernet key.
    Uses SHA-256 hash so any length key works."""
    import base64, hashlib
    digest = hashlib.sha256(raw_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


# ─── encrypt_token ────────────────────────────────────────────
# Encrypt a plaintext Shopify access token.
# Returns encrypted base64 string, or plaintext if no key set.

def encrypt_token(plaintext: str, key: str) -> str:
    """Encrypt token with Fernet symmetric cipher.
    If key is empty, returns plaintext (dev mode fallback)."""
    if not key:
        logger.warning("ENCRYPTION_KEY not set — token stored as plaintext!")
        return plaintext
    try:
        f = Fernet(_derive_key(key))
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Token encryption failed: {e}")
        return plaintext


# ─── decrypt_token ────────────────────────────────────────────
# Decrypt a previously encrypted token.
# Falls back to plaintext if token wasn't encrypted (migration).

def decrypt_token(ciphertext: str, key: str) -> str:
    """Decrypt Fernet-encrypted token.
    Falls back to plaintext if token not encrypted (legacy data)."""
    if not key:
        return ciphertext
    try:
        f = Fernet(_derive_key(key))
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Not encrypted or wrong key — return as-is (legacy fallback)
        return ciphertext
