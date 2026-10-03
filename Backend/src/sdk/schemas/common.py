# ═══════════════════════════════════════════════════════════════
# fte_sdk / schemas / common.py
#
# PURPOSE: Generic Pydantic response schemas — sab API endpoints
#          aur agents yehi use karte hain consistent responses ke
#          liye. PaginatedResponse, ErrorResponse, HealthResponse.
#
# USED BY: backend (API responses), all agents (health checks)
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

# ─── PaginatedResponse ────────────────────────────────────────
# Generic wrapper for paginated list endpoints.
# Usage: PaginatedResponse[ProductOut]
#   → items field will be typed as list[ProductOut]

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    limit: int
    items: list[T]


# ─── ErrorResponse ────────────────────────────────────────────
# Standard error response for all API endpoints.

class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    code: int = 400


# ─── HealthResponse ───────────────────────────────────────────
# Standard health check response for all services.

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
