# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / api.py
#
# PURPOSE: REST API — dashboard reads comments/escalations here,
#          and can send a manual reply or simulate an incoming
#          comment for testing (same idea as inventory_sync's
#          manual /sync trigger).
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db
from src.domains.agents.comment_engagement.config import get_settings
from src.domains.agents.comment_engagement.handler import CommentEngagementHandler
from src.domains.auth.service import get_current_user
from src.domains.agents.comment_engagement.schemas import (
    CommentOut, CommentListResponse, ReplyOut,
    ManualReplyRequest, SimulateCommentRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Comment Engagement"])


# ─── Auth Dependency (same pattern as inventory_sync) ──────────


@router.get("/comments", response_model=CommentListResponse)
async def list_comments(
    social_account_id: Optional[int] = Query(None),
    escalated_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List comments for the dashboard. Set escalated_only=true to see
    only the ones flagged for human review."""
    handler = CommentEngagementHandler(db)
    comments = await handler.list_comments(social_account_id, escalated_only)
    return {"comments": comments, "total": len(comments)}


@router.get("/comments/escalated", response_model=CommentListResponse)
async def list_escalated(db: AsyncSession = Depends(get_db), _auth=Depends(get_current_user)):
    """Shortcut for the dashboard's 'needs your attention' view."""
    handler = CommentEngagementHandler(db)
    comments = await handler.list_comments(escalated_only=True)
    return {"comments": comments, "total": len(comments)}


@router.post("/comments/{comment_id}/reply", response_model=ReplyOut)
async def reply_to_comment(
    comment_id: int,
    body: ManualReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Human sends a manual reply from the dashboard — for escalated
    comments the agent wouldn't auto-reply to."""
    handler = CommentEngagementHandler(db)
    try:
        reply = await handler.manual_reply(comment_id, body.text)
        await db.commit()
        return reply
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/comments/simulate", response_model=CommentOut)
async def simulate_comment(
    body: SimulateCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Feed a fake comment through the real pipeline (classify →
    auto-reply or escalate) — for testing without a live Meta app."""
    handler = CommentEngagementHandler(db)
    comment = await handler.process_comment(
        social_account_id=body.social_account_id,
        platform_post_id=body.platform_post_id,
        platform_comment_id=f"sim_{body.author}",
        author=body.author,
        text=body.text,
    )
    await db.commit()
    return comment
