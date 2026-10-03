# ═══════════════════════════════════════════════════════════════
# agents / content_generation / schemas.py
#
# PURPOSE: Pydantic models for Content Generation API requests/responses.
# USED BY: api.py, handler.py
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class GenerateRequest(BaseModel):
    """Request to generate a social media post for a product."""
    product_id: int
    platform: str = "instagram"              # instagram | facebook | tiktok | linkedin
    brand_voice_id: Optional[int] = None
    image_model: str = "gemini"              # gemini | dalle3
    auto_approve: Optional[bool] = None      # override global setting


class PostActionRequest(BaseModel):
    """Approve / Reject / Regenerate a generated post."""
    feedback: str = ""


class BrandVoiceCreate(BaseModel):
    """Create a brand voice profile."""
    name: str
    tone_guidelines: str = ""
    keywords_to_use: str = ""
    keywords_to_avoid: str = ""


class BrandVoiceUpdate(BaseModel):
    """Update a brand voice profile."""
    name: Optional[str] = None
    tone_guidelines: Optional[str] = None
    keywords_to_use: Optional[str] = None
    keywords_to_avoid: Optional[str] = None


class GeneratedPostOut(BaseModel):
    id: int
    product_id: int
    platform: str
    caption: str
    status: str
    review_notes: str = ""
    image_model_used: str = ""
    created_at: datetime
    approved_at: Optional[datetime] = None
    images: list = []

    model_config = ConfigDict(from_attributes=True)


class ImageAssetOut(BaseModel):
    id: int
    url: str
    prompt_used: str = ""
    model_used: str = ""
    status: str = ""

    model_config = ConfigDict(from_attributes=True)


class GenerateResponse(BaseModel):
    message: str
    post_id: int
    status: str
    caption: str = ""
    image_url: str = ""


class BrandVoiceOut(BaseModel):
    id: int
    store_id: int
    name: str
    tone_guidelines: str = ""
    keywords_to_use: str = ""
    keywords_to_avoid: str = ""
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
