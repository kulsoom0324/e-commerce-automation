# ═══════════════════════════════════════════════════════════════
# agents / content_generation / api.py
#
# PURPOSE: REST API endpoints for Content Generation Agent.
#          Also registered as routes in the central Backend API.
#
# USED BY: main.py, backend/api.py
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db
from src.sdk.models.content import GeneratedPost, BrandVoiceProfile
from src.sdk.event_bus import RedisEventBus

from src.dependencies import get_event_bus

from src.domains.agents.content_generation.config import get_settings
from src.domains.agents.content_generation.schemas import (
    GenerateRequest, PostActionRequest, GenerateResponse,
    BrandVoiceCreate, BrandVoiceUpdate, BrandVoiceOut,
)
from src.domains.agents.content_generation.handler import ContentGenerationHandler
from src.domains.auth.service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/content", tags=["Content Generation"])


# ─── Generate Post ────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate_post(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    bus=Depends(get_event_bus),
    current_user=Depends(get_current_user),
):
    """Generate a social media post for a product using AI (LLM council + image gen)."""
    handler = ContentGenerationHandler(db=db, event_bus=bus)
    try:
        post = await handler.generate_post(
            product_id=body.product_id,
            brand_voice_id=body.brand_voice_id,
            platform=body.platform,
            image_model=body.image_model,
            auto_approve=body.auto_approve,
        )
        image_url = post.images[0].url if post.images else ""
        return GenerateResponse(
            message="Content generated successfully",
            post_id=post.id,
            status=post.status,
            caption=post.caption[:200],  # preview
            image_url=image_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Generate failed: {e}")
        raise HTTPException(status_code=500, detail="Content generation failed")


# ─── List / Get Posts ─────────────────────────────────────────

@router.get("/history")
async def list_posts(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List generated posts with optional status filter."""
    query = select(GeneratedPost).order_by(GeneratedPost.created_at.desc())
    if status:
        query = query.where(GeneratedPost.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()
    return [
        {
            "id": p.id,
            "product_id": p.product_id,
            "platform": p.platform,
            "caption_preview": p.caption[:150] if p.caption else "",
            "status": p.status,
            "image_model_used": p.image_model_used,
            "created_at": p.created_at,
            "has_image": len(p.images) > 0,
        }
        for p in posts
    ]


@router.get("/posts/{post_id}")
async def get_post(post_id: int, db: AsyncSession = Depends(get_db), _auth=Depends(get_current_user)):
    """Get single generated post with images."""
    result = await db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {
        "id": post.id,
        "product_id": post.product_id,
        "platform": post.platform,
        "caption": post.caption,
        "status": post.status,
        "review_notes": post.review_notes,
        "image_model_used": post.image_model_used,
        "created_at": post.created_at,
        "approved_at": post.approved_at,
        "images": [
            {"id": img.id, "url": img.url, "model_used": img.model_used, "status": img.status}
            for img in post.images
        ],
    }


# ─── Approve / Reject / Regenerate ────────────────────────────

@router.post("/posts/{post_id}/approve")
async def approve_post(
    post_id: int,
    body: PostActionRequest = PostActionRequest(),
    db: AsyncSession = Depends(get_db),
    bus=Depends(get_event_bus),
    current_user=Depends(get_current_user),
):
    """Approve a generated post → sends to scheduling agent."""
    handler = ContentGenerationHandler(db=db, event_bus=bus)
    try:
        post = await handler.approve_post(post_id, body.feedback)
        return {"message": "Post approved", "post_id": post.id, "status": post.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/posts/{post_id}/reject")
async def reject_post(
    post_id: int,
    body: PostActionRequest = PostActionRequest(),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Reject a generated post with feedback."""
    handler = ContentGenerationHandler(db=db)
    try:
        post = await handler.reject_post(post_id, body.feedback)
        return {"message": "Post rejected", "post_id": post.id, "status": post.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/posts/{post_id}/regenerate")
async def regenerate_post(
    post_id: int,
    body: PostActionRequest = PostActionRequest(),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Regenerate a rejected post with feedback."""
    handler = ContentGenerationHandler(db=db)
    try:
        post = await handler.regenerate_post(post_id, body.feedback)
        return {"message": "Post regenerated", "post_id": post.id, "status": post.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Brand Voice CRUD ─────────────────────────────────────────

@router.get("/brand-voices", response_model=list[BrandVoiceOut])
async def list_brand_voices(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all brand voice profiles for a store."""
    handler = ContentGenerationHandler(db=db)
    return await handler.list_brand_voices(store_id)


@router.post("/brand-voices", response_model=BrandVoiceOut)
async def create_brand_voice(
    store_id: int,
    body: BrandVoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new brand voice profile."""
    handler = ContentGenerationHandler(db=db)
    return await handler.create_brand_voice(
        store_id=store_id,
        name=body.name,
        tone_guidelines=body.tone_guidelines,
        keywords_to_use=body.keywords_to_use,
        keywords_to_avoid=body.keywords_to_avoid,
    )


@router.put("/brand-voices/{voice_id}", response_model=BrandVoiceOut)
async def update_brand_voice(
    voice_id: int,
    body: BrandVoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a brand voice profile."""
    handler = ContentGenerationHandler(db=db)
    try:
        return await handler.update_brand_voice(
            voice_id=voice_id,
            name=body.name,
            tone_guidelines=body.tone_guidelines,
            keywords_to_use=body.keywords_to_use,
            keywords_to_avoid=body.keywords_to_avoid,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/brand-voices/{voice_id}")
async def delete_brand_voice(voice_id: int, db: AsyncSession = Depends(get_db), _auth=Depends(get_current_user)):
    """Delete a brand voice profile."""
    result = await db.execute(select(BrandVoiceProfile).where(BrandVoiceProfile.id == voice_id))
    bv = result.scalar_one_or_none()
    if not bv:
        raise HTTPException(status_code=404, detail="Brand voice not found")
    await db.delete(bv)
    await db.commit()
    return {"status": "deleted"}
