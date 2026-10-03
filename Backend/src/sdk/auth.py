# ═══════════════════════════════════════════════════════════════
# fte_sdk / auth.py
#
# PURPOSE: Authentication helpers — token verification aur Shopify
#          webhook HMAC validation. Backend aur agents dono use
#          karte hain.
#
# USED BY: backend (webhook HMAC), orchestrator (agent tokens),
#          agents (inter-agent auth)
# ═══════════════════════════════════════════════════════════════

import hashlib
import hmac
import base64
from typing import Optional


# ─── verify_token (Constant-Time) ─────────────────────────────
# Agent-to-agent aur orchestrator communication ke liye.
# hmac.compare_digest = timing attack safe comparison.

def verify_token(token: str, expected_token: str) -> bool:
    """Constant-time token comparison — safe against timing attacks."""
    return hmac.compare_digest(token, expected_token)


# ─── verify_hmac (Shopify Webhook HMAC) ───────────────────────
# Shopify webhook payload verify karta hai. Secret = API_SECRET.
# Backend webhooks.py ise call karta hai har incoming webhook pe.

def verify_hmac(body: bytes, header_hmac: str, secret: str) -> bool:
    """HMAC-SHA256 verification for Shopify webhooks."""
    if not header_hmac or not secret:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, header_hmac)
