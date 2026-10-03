# ═══════════════════════════════════════════════════════════════
# fte_sdk / models / content.py
#
# PURPOSE: AI-generated content models — LLM council ke output
#          ko store karta hai. Brand voice + generated posts.
#
# USED BY: content_generation (write, review, approve)
# ═══════════════════════════════════════════════════════════════

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import relationship

from src.sdk.database import Base


# ─── BrandVoiceProfile ────────────────────────────────────────
# Brand tone guidelines for LLM content generation.
# Tells the LLM: how to write, what words to use/avoid.

class BrandVoiceProfile(Base):
    __tablename__ = "brand_voice_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tone_guidelines = Column(Text, default="")
    keywords_to_use = Column(Text, default="")             # comma-separated
    keywords_to_avoid = Column(Text, default="")           # comma-separated
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─── GeneratedPost ────────────────────────────────────────────
# AI-generated social media post for a product.
# Flow: draft → review → approved → content_scheduling picks it up.

class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    brand_voice_id = Column(Integer, ForeignKey("brand_voice_profiles.id"), nullable=True)
    platform = Column(String(50), nullable=False)            # instagram | facebook | tiktok | linkedin
    caption = Column(Text, default="")
    status = Column(String(50), default="draft")             # draft | review | approved | rejected
    review_notes = Column(Text, default="")
    image_model_used = Column(String(50), default="")        # "gemini" | "dalle3" | ""
    scheduled_post_id = Column(Integer, ForeignKey("scheduled_posts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)

    images = relationship("ImageAsset", back_populates="post", cascade="all, delete-orphan")


# ─── ImageAsset ───────────────────────────────────────────────
# AI-generated image for a GeneratedPost.

class ImageAsset(Base):
    __tablename__ = "image_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("generated_posts.id"), nullable=False, index=True)
    url = Column(String(512), nullable=False)
    prompt_used = Column(Text, default="")
    model_used = Column(String(50), default="gemini")        # "gemini" | "dalle3"
    status = Column(String(50), default="generated")         # generated | approved | rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("GeneratedPost", back_populates="images")
