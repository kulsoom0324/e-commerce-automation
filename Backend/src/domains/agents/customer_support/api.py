# ═══════════════════════════════════════════════════════════════
# agents / customer_support / api.py
#
# PURPOSE: REST API endpoints for Customer Support Agent.
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db

from src.domains.agents.customer_support.handler import CustomerSupportHandler
from src.domains.auth.service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/support", tags=["Customer Support"])


# ─── Schemas ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    store_id: int
    message: str
    customer_email: str = "customer@example.com"
    conversation_id: Optional[int] = None
    language: str = ""


class HumanReplyRequest(BaseModel):
    text: str


# ─── Endpoints ────────────────────────────────────────────────

@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Customer chat message endpoint (handles RAG, cart, order lookup, handoff)."""
    handler = CustomerSupportHandler(db)
    result = await handler.process_message(
        store_id=body.store_id,
        customer_email=body.customer_email,
        text=body.message,
        conversation_id=body.conversation_id,
        language=body.language,
    )
    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/human-reply")
async def human_reply(
    conversation_id: int,
    body: HumanReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Support dashboard endpoint: Human agent sends reply to conversation."""
    handler = CustomerSupportHandler(db)
    try:
        msg = await handler.human_reply(conversation_id, body.text)
        await db.commit()
        return {
            "status": "posted",
            "message_id": msg.id,
            "conversation_id": conversation_id,
            "role": msg.role,
            "content": msg.content,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/conversations/{conversation_id}/close")
async def close_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Close an active support conversation."""
    handler = CustomerSupportHandler(db)
    try:
        conv = await handler.close_conversation(conversation_id)
        await db.commit()
        return {"status": "closed", "conversation_id": conv.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    store_id: int = Query(...),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List customer support conversations."""
    handler = CustomerSupportHandler(db)
    convs = await handler.list_conversations(store_id, status)
    return [
        {
            "id": c.id,
            "store_id": c.store_id,
            "customer_email": c.customer_email,
            "status": c.status,
            "created_at": c.created_at,
            "closed_at": c.closed_at,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get full conversation with message history."""
    handler = CustomerSupportHandler(db)
    data = await handler.get_conversation(conversation_id)
    if not data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return data


@router.get("/handoffs")
async def list_handoffs(
    store_id: Optional[int] = Query(None),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List escalated conversations waiting for human attention."""
    handler = CustomerSupportHandler(db)
    handoffs = await handler.list_handoffs(store_id, limit)
    return [
        {
            "id": h.id,
            "conversation_id": h.conversation_id,
            "reason": h.reason,
            "assigned_to": h.assigned_to,
            "created_at": h.created_at,
        }
        for h in handoffs
    ]
