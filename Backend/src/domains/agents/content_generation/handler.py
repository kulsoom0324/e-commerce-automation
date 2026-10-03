# ═══════════════════════════════════════════════════════════════
# agents / content_generation / handler.py
#
# PURPOSE: Core business logic — LLM Council pipeline for
#          generating social media posts with AI images.
#
#          Pipeline:
#            1. Research product data (LLM)
#            2. Write platform-specific caption (LLM)
#            3. Review caption against brand voice (LLM)
#            4. Generate image (Gemini / DALL-E 3)
#            5. Auto-approve or wait for human review
#
# USED BY: worker.py, api.py
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.content import GeneratedPost, ImageAsset, BrandVoiceProfile
from src.sdk.models.base import Product
from src.sdk.llm.client import LLMClient
from src.sdk.llm.prompts import (
    CONTENT_RESEARCH_PROMPT,
    CONTENT_WRITER_PROMPT,
    CONTENT_REVIEWER_PROMPT,
)
from src.sdk.events import Event, ContentApprovedEvent
from src.sdk.event_bus import RedisEventBus
from src.sdk.config import get_settings

from src.domains.agents.content_generation.config import get_settings as get_agent_settings
from src.domains.agents.content_generation.image_gen import create_image_generator, ImageGenerator

logger = logging.getLogger(__name__)


# ─── Platform-specific prompt instructions ─────────────────────

PLATFORM_INSTRUCTIONS = {
    "instagram": (
        "Write a short, engaging Instagram caption. Use emojis and 3-5 relevant hashtags. "
        "Include a question or call-to-action. Max 2200 characters, but 150 is ideal."
    ),
    "facebook": (
        "Write a conversational Facebook post. Friendly tone, 2-3 sentences. "
        "End with a question to encourage comments. No hashtags."
    ),
    "tiktok": (
        "Write a very short, trending TikTok caption. Use 2-3 popular hashtags. "
        "Hook in the first line. Use emojis. Max 150 characters."
    ),
    "linkedin": (
        "Write a professional LinkedIn post. 3-5 sentences with industry insight. "
        "Include a key takeaway. Use 2-3 relevant hashtags. Professional but conversational tone."
    ),
}


class ContentGenerationHandler:
    """Handles content generation lifecycle — from product to published post."""

    def __init__(self, db: AsyncSession, llm_client: Optional[LLMClient] = None,
                 event_bus: Optional[RedisEventBus] = None):
        self.db = db
        self.settings = get_agent_settings()
        self.fte_settings = get_settings()
        self.llm = llm_client or LLMClient(
            api_key=self.settings.LLM_API_KEY or self.fte_settings.LLM_API_KEY,
            model=self.settings.LLM_MODEL or self.fte_settings.LLM_MODEL,
        )
        self.event_bus = event_bus

    # ─── Main: Generate a Post ──────────────────────────────────

    async def generate_post(
        self,
        product_id: int,
        brand_voice_id: Optional[int] = None,
        platform: str = "instagram",
        image_model: str = "",
        auto_approve: Optional[bool] = None,
    ) -> GeneratedPost:
        """Full content generation pipeline.

        1. Fetch product + brand voice from DB
        2. LLM Council: Research → Write → Review
        3. Image Generation: via Gemini or DALL-E
        4. Save to DB → Auto-approve or wait
        """
        # 1. Fetch product from DB
        product = await self._get_product(product_id)
        logger.info(f"Generating content for product [{product_id}]: {product.title}")

        # 2. Fetch brand voice
        brand_voice = await self._get_brand_voice(brand_voice_id)
        product_data = self._format_product_data(product)

        # 3. LLM Council — Research
        research = await self._research_product(product_data)
        logger.info(f"  Research complete: extracted {len(research)} key points")

        # 4. LLM Council — Write caption for specific platform
        platform_instruction = PLATFORM_INSTRUCTIONS.get(platform, PLATFORM_INSTRUCTIONS["instagram"])
        caption = await self._write_caption(product_data, brand_voice, research, platform_instruction)
        logger.info(f"  Caption written ({len(caption)} chars)")

        # 5. LLM Council — Review caption
        review_result = await self._review_caption(caption, brand_voice)
        logger.info(f"  Review: {review_result.get('verdict', 'unknown')}")

        # 6. Save GeneratedPost to DB
        post = GeneratedPost(
            product_id=product_id,
            brand_voice_id=brand_voice_id,
            platform=platform,
            caption=caption,
            status="review",  # default: wait for human
            review_notes=review_result.get("suggestions", ""),
        )
        self.db.add(post)
        await self.db.flush()
        await self.db.refresh(post)

        # 7. Generate Image
        model_name = image_model or self.settings.IMAGE_MODEL_DEFAULT
        image_gen = self._get_image_generator(model_name)

        # Craft image prompt from product + caption
        image_prompt = f"Product: {product.title}. Style: {product_data.get('vendor', '')}. "
        image_prompt += f"Create a professional e-commerce social media image."
        if review_result.get("suggestions"):
            image_prompt += f" Context: {review_result['suggestions']}"

        image_result = await image_gen.generate(
            prompt=image_prompt,
            size=self.settings.IMAGE_SIZE,
        )

        # Save ImageAsset
        image = ImageAsset(
            post_id=post.id,
            url=image_result["url"],
            prompt_used=image_result["prompt_used"],
            model_used=image_result["model"],
            status="generated",
        )
        self.db.add(image)
        post.image_model_used = image_result["model"]

        # 8. Auto-approve or leave for human review
        should_auto_approve = auto_approve if auto_approve is not None else not self.settings.HUMAN_REVIEW_REQUIRED

        if should_auto_approve:
            post.status = "approved"
            post.approved_at = datetime.now(timezone.utc)
            image.status = "approved"
            try:
                await self._publish_approved_event(post, image)
            except Exception:
                pass
            logger.info(f"  ✅ Auto-approved post #{post.id}")
        else:
            logger.info(f"  ⏳ Post #{post.id} in review — waiting for human approval")

        await self.db.commit()
        return post

    # ─── Approve / Reject / Regenerate ──────────────────────────

    async def approve_post(self, post_id: int, feedback: str = "") -> GeneratedPost:
        """Approve a generated post → publishes ContentApprovedEvent."""
        post = await self._get_generated_post(post_id)
        post.status = "approved"
        post.approved_at = datetime.now(timezone.utc)
        post.review_notes = (post.review_notes or "") + f"\n[Approved] {feedback}".strip()

        # Approve all associated images via direct query (avoid lazy-load issues)
        try:
            img_result = await self.db.execute(
                select(ImageAsset).where(ImageAsset.post_id == post_id)
            )
            images = img_result.scalars().all()
            for img in images:
                img.status = "approved"
            first_image = images[0] if images else None
        except Exception:
            first_image = None

        try:
            await self._publish_approved_event(post, first_image)
        except Exception:
            pass  # Event bus not available in some contexts (tests)
        await self.db.commit()
        logger.info(f"✅ Post #{post_id} approved")
        return post

    async def reject_post(self, post_id: int, feedback: str = "") -> GeneratedPost:
        """Reject a generated post."""
        post = await self._get_generated_post(post_id)
        post.status = "rejected"
        post.review_notes = (post.review_notes or "") + f"\n[Rejected] {feedback}".strip()
        # Reject all images too via direct query
        try:
            img_result = await self.db.execute(
                select(ImageAsset).where(ImageAsset.post_id == post_id)
            )
            for img in img_result.scalars().all():
                img.status = "rejected"
        except Exception:
            pass

        if self.event_bus:
            event = Event(
                event_type="content.rejected",
                source="content_generation",
                payload={"post_id": post_id, "feedback": feedback},
            )
            try:
                await self.event_bus.publish("events", event.model_dump())
            except Exception:
                pass

        await self.db.commit()
        logger.info(f"❌ Post #{post_id} rejected: {feedback}")
        return post

    async def regenerate_post(self, post_id: int, feedback: str = "") -> GeneratedPost:
        """Regenerate a rejected post with feedback as context."""
        old_post = await self._get_generated_post(post_id)
        # Re-generate with the feedback as additional context
        product = await self._get_product(old_post.product_id)
        brand_voice = await self._get_brand_voice(old_post.brand_voice_id)
        product_data = self._format_product_data(product)

        # Enhance the writer prompt with feedback
        enhanced_instruction = PLATFORM_INSTRUCTIONS.get(old_post.platform, "")
        if feedback:
            enhanced_instruction += f"\nPrevious feedback to address: {feedback}"

        caption = await self._write_caption(
            product_data, brand_voice,
            {"previous_feedback": feedback},
            enhanced_instruction
        )

        old_post.caption = caption
        old_post.status = "review"
        old_post.review_notes = feedback
        await self.db.commit()
        logger.info(f"🔄 Post #{post_id} regenerated with feedback")
        return old_post

    # ─── Brand Voice CRUD ───────────────────────────────────────

    async def list_brand_voices(self, store_id: int) -> list[BrandVoiceProfile]:
        result = await self.db.execute(
            select(BrandVoiceProfile).where(BrandVoiceProfile.store_id == store_id)
        )
        return result.scalars().all()

    async def create_brand_voice(self, store_id: int, name: str,
                                  tone_guidelines: str = "",
                                  keywords_to_use: str = "",
                                  keywords_to_avoid: str = "") -> BrandVoiceProfile:
        bv = BrandVoiceProfile(
            store_id=store_id,
            name=name,
            tone_guidelines=tone_guidelines,
            keywords_to_use=keywords_to_use,
            keywords_to_avoid=keywords_to_avoid,
        )
        self.db.add(bv)
        await self.db.commit()
        await self.db.refresh(bv)
        return bv

    async def update_brand_voice(self, voice_id: int, **kwargs) -> BrandVoiceProfile:
        result = await self.db.execute(
            select(BrandVoiceProfile).where(BrandVoiceProfile.id == voice_id)
        )
        bv = result.scalar_one_or_none()
        if not bv:
            raise ValueError(f"Brand voice #{voice_id} not found")
        for key, val in kwargs.items():
            if val is not None and hasattr(bv, key):
                setattr(bv, key, val)
        await self.db.commit()
        await self.db.refresh(bv)
        return bv

    # ─── LLM Council Steps ──────────────────────────────────────

    async def _research_product(self, product_data: dict) -> str:
        """LLM Step 1: Research product → extract key selling points."""
        prompt = CONTENT_RESEARCH_PROMPT.format(product_data=product_data)
        return await self.llm.generate(prompt, system="You are a product researcher.")

    async def _write_caption(self, product_data: dict, brand_voice: str,
                              research: str, platform_instruction: str) -> str:
        """LLM Step 2: Write platform-specific caption."""
        prompt = CONTENT_WRITER_PROMPT.format(
            product_data=product_data,
            brand_voice=brand_voice,
            research=research,
            platform=platform_instruction,
        )
        return await self.llm.generate(prompt, system="You are a social media copywriter.")

    async def _review_caption(self, caption: str, brand_voice: str) -> dict:
        """LLM Step 3: Review caption against brand voice."""
        prompt = CONTENT_REVIEWER_PROMPT.format(
            writer=caption,
        )
        # Add brand voice context
        if brand_voice:
            prompt += f"\nBrand Voice Guidelines: {brand_voice}"

        result = await self.llm.generate(prompt, system="You are a brand tone reviewer.")
        # Parse verdict from result
        verdict = "pass" if "pass" in result.lower() else "fail"
        return {"verdict": verdict, "suggestions": result}

    # ─── Helpers ────────────────────────────────────────────────

    async def _get_product(self, product_id: int) -> Product:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product #{product_id} not found")
        return product

    async def _get_generated_post(self, post_id: int) -> GeneratedPost:
        result = await self.db.execute(select(GeneratedPost).where(GeneratedPost.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            raise ValueError(f"Generated post #{post_id} not found")
        return post

    async def _get_brand_voice(self, brand_voice_id: Optional[int]) -> str:
        if not brand_voice_id:
            return "Professional, friendly, helpful. Write in clear English."
        result = await self.db.execute(
            select(BrandVoiceProfile).where(BrandVoiceProfile.id == brand_voice_id)
        )
        bv = result.scalar_one_or_none()
        if not bv:
            return "Professional, friendly, helpful."
        return f"Tone: {bv.tone_guidelines}. Use: {bv.keywords_to_use}. Avoid: {bv.keywords_to_avoid}."

    @staticmethod
    def _format_product_data(product: Product) -> dict:
        return {
            "title": product.title,
            "description": product.description,
            "vendor": product.vendor,
            "product_type": product.product_type,
            "status": product.status,
        }

    def _get_image_generator(self, model_name: str = "") -> ImageGenerator:
        """Factory-wrapper to create the right image generator."""
        model_name = model_name or self.settings.IMAGE_MODEL_DEFAULT

        if "gemini" in model_name.lower():
            return create_image_generator("gemini", self.settings.GEMINI_API_KEY or self.fte_settings.GEMINI_API_KEY)
        elif "dalle" in model_name.lower() or "dall-e" in model_name.lower():
            return create_image_generator("dalle3", self.settings.DALLE_API_KEY or self.fte_settings.DALLE_API_KEY)
        else:
            # Default to Gemini
            return create_image_generator("gemini", self.settings.GEMINI_API_KEY or self.fte_settings.GEMINI_API_KEY)

    async def _publish_approved_event(self, post: GeneratedPost, image: Optional[ImageAsset]):
        """Publish ContentApprovedEvent → Agent 2 picks it up for scheduling."""
        if not self.event_bus:
            return

        try:
            event = ContentApprovedEvent(
                source="content_generation",
                target_agent="content_scheduling",
                payload={
                    "post_id": post.id,
                    "product_id": post.product_id,
                    "platform": post.platform,
                    "caption": post.caption,
                    "media_urls": [image.url] if image else [],
                    "image_model": post.image_model_used,
                },
            )
            await self.event_bus.publish("events", event.model_dump())
            logger.info(f"  📤 Published ContentApprovedEvent for post #{post.id}")
        except Exception as e:
            logger.warning(f"  Could not publish event (bus not available): {e}")
