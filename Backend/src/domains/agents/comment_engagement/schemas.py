# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / schemas.py
#
# PURPOSE: Pydantic request/response models for the dashboard API.
# ═══════════════════════════════════════════════════════════════

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CommentOut(BaseModel):
    id: int
    social_account_id: int
    platform_post_id: str
    author: str
    text: str
    sentiment: str
    is_escalated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReplyOut(BaseModel):
    id: int
    comment_id: int
    text: str
    status: str
    generated_by_llm: bool
    created_at: datetime
    posted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    comments: list[CommentOut]
    total: int


class ManualReplyRequest(BaseModel):
    text: str


class SimulateCommentRequest(BaseModel):
    """Manually trigger the pipeline with a fake comment — useful for
    testing the full classify → reply/escalate flow without a real
    Meta webhook (same purpose as MetaClient's dev-mode)."""
    social_account_id: int
    platform_post_id: str
    author: str = "test_user"
    text: str
