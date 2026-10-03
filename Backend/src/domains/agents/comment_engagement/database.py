# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / database.py
#
# PURPOSE: Re-exports — all DB setup lives in fte_sdk/database.py.
#          Kept so agent imports (from database import ...) work,
#          same convention as inventory_sync/database.py.
# ═══════════════════════════════════════════════════════════════

from src.sdk.database import engine, async_session_factory, Base, get_db, init_db

__all__ = ["engine", "async_session_factory", "Base", "get_db", "init_db"]
