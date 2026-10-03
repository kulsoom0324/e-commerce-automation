"""
Rate limiter for Auth endpoints (in-memory sliding window).
"""

import time
from collections import defaultdict, deque
from typing import Deque
from fastapi import HTTPException, Request

from src.sdk.config import get_settings

_attempts: dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def login_rate_limiter(request: Request) -> None:
    settings = get_settings()
    ip = _client_ip(request)
    now = time.time()
    q = _attempts[ip]

    while q and now - q[0] > settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS:
        q.popleft()

    if len(q) >= settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please try again after some time.",
        )

    q.append(now)
