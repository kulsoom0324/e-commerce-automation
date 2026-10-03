# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / api.py
#
# PURPOSE: REST API endpoints for Content Scheduling Agent.
#          Connect accounts, list accounts, schedule posts, list scheduled posts.
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db

from src.domains.agents.content_scheduling.handler import ContentSchedulingHandler
from src.domains.auth.service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scheduling", tags=["Content Scheduling"])


# ─── Schemas ──────────────────────────────────────────────────

class ConnectSocialAccountRequest(BaseModel):
    store_id: int
    platform: str
    account_name: str
    account_id: str
    access_token: str
    refresh_token: str = ""


class SchedulePostRequest(BaseModel):
    social_account_id: int
    caption: str
    media_urls: list[str] = []
    platform: str
    scheduled_at: datetime
    product_id: Optional[int] = None
    generated_post_id: Optional[int] = None


# ─── Endpoints ────────────────────────────────────────────────

@router.post("/accounts")
async def connect_social_account(
    body: ConnectSocialAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Connect a social media account."""
    handler = ContentSchedulingHandler(db)
    account = await handler.connect_account(
        store_id=body.store_id,
        platform=body.platform,
        account_name=body.account_name,
        account_id=body.account_id,
        access_token=body.access_token,
        refresh_token=body.refresh_token,
    )
    return {
        "status": "connected",
        "account_id": account.id,
        "platform": account.platform,
        "account_name": account.account_name,
    }


@router.get("/accounts")
async def list_social_accounts(
    store_id: int = Query(...),
    platform: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List connected social media accounts."""
    handler = ContentSchedulingHandler(db)
    accounts = await handler.list_accounts(store_id=store_id, platform=platform)
    return [
        {
            "id": a.id,
            "store_id": a.store_id,
            "platform": a.platform,
            "account_name": a.account_name,
            "account_id": a.account_id,
            "is_active": a.is_active,
        }
        for a in accounts
    ]


@router.post("/posts")
async def schedule_social_post(
    body: SchedulePostRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Schedule a post."""
    handler = ContentSchedulingHandler(db)
    post = await handler.schedule_post(
        social_account_id=body.social_account_id,
        caption=body.caption,
        media_urls=body.media_urls,
        platform=body.platform,
        scheduled_at=body.scheduled_at,
        product_id=body.product_id,
        generated_post_id=body.generated_post_id,
    )
    return {
        "status": "scheduled",
        "post_id": post.id,
        "scheduled_at": post.scheduled_at,
        "platform": post.platform,
    }


@router.get("/posts")
async def list_scheduled_social_posts(
    store_id: int = Query(...),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List scheduled posts."""
    handler = ContentSchedulingHandler(db)
    return await handler.list_scheduled_posts(store_id=store_id, platform=platform, status=status)
