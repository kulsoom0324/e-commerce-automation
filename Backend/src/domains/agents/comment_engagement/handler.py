# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / handler.py
#
# PURPOSE: Core business logic — classify comment, auto-reply
#          (rule-based or LLM), or escalate to a human.
#
# USED BY: worker.py (event-driven), api.py (manual dashboard actions)
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.social import Comment, Reply, SocialAccount, ScheduledPost
from src.sdk.models.base import Product, Variant
from src.sdk.llm.client import LLMClient
from src.sdk.crypto import decrypt_token
from src.sdk.config import get_settings as get_fte_settings

from src.domains.agents.comment_engagement.meta_client import MetaClient
from src.domains.agents.comment_engagement.rules import classify_comment, format_price_reply, CommentAction
from src.domains.agents.comment_engagement.config import get_settings

logger = logging.getLogger(__name__)


class CommentEngagementHandler:
    """Handles the full comment lifecycle: classify → reply or escalate."""

    def __init__(self, db: AsyncSession, llm_client: Optional[LLMClient] = None):
        self.db = db
        self.settings = get_settings()
        self.llm = llm_client or LLMClient(api_key=self.settings.LLM_API_KEY)

    # ─── process_comment() — main entry point ─────────────────
    # Called for every new comment, whether it arrived via the
    # background poller (worker.py) or a real Meta webhook later.

    async def process_comment(
        self,
        social_account_id: int,
        platform_post_id: str,
        platform_comment_id: str,
        author: str,
        text: str,
    ) -> Comment:
        """Save the comment, classify it, and act (reply or escalate)."""
        comment = Comment(
            social_account_id=social_account_id,
            platform_post_id=platform_post_id,
            author=author,
            text=text,
        )
        self.db.add(comment)
        await self.db.flush()  # get comment.id without committing yet

        action = classify_comment(
            text,
            price_keywords=self.settings.PRICE_KEYWORDS,
            escalation_keywords=self.settings.ESCALATION_KEYWORDS,
        )

        if action == CommentAction.ESCALATE:
            comment.sentiment = "negative"
            comment.is_escalated = True
            logger.info(f"Comment #{comment.id} escalated — matched an escalation keyword")
            return comment

        if action == CommentAction.PRICE_QUERY:
            reply_text = await self._build_price_reply(platform_post_id)
            await self._create_and_post_reply(comment, reply_text, social_account_id, generated_by_llm=False)
            return comment

        # NEEDS_LLM
        reply_text = await self._generate_llm_reply(text)
        await self._create_and_post_reply(comment, reply_text, social_account_id, generated_by_llm=True)
        return comment

    # ─── _build_price_reply() ──────────────────────────────────
    # Rule-based: look up the product linked to this post's
    # ScheduledPost row, pull its current price from Inventory
    # Sync's own tables (no new Shopify call needed).

    async def _build_price_reply(self, platform_post_id: str) -> str:
        result = await self.db.execute(
            select(ScheduledPost).where(ScheduledPost.platform_post_id == platform_post_id)
        )
        post = result.scalar_one_or_none()
        if not post or not post.product_id:
            return "Thanks for asking! Please DM us for the current price. 🙌"

        product_result = await self.db.execute(select(Product).where(Product.id == post.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            return "Thanks for asking! Please DM us for the current price. 🙌"

        variant_result = await self.db.execute(
            select(Variant).where(Variant.product_id == product.id).limit(1)
        )
        variant = variant_result.scalar_one_or_none()
        if not variant:
            return f"Thanks for asking about {product.title}! Please DM us for pricing. 🙌"

        return format_price_reply(product.title, float(variant.price))

    # ─── _generate_llm_reply() ──────────────────────────────────
    # Only reached for comments that aren't a simple price query
    # and aren't an escalation. Uses the shared LLMClient — same
    # provider wiring as content_generation (see fte_sdk/llm/client.py).

    async def _generate_llm_reply(self, comment_text: str) -> str:
        prompt = (
            f"A customer commented on our social media post: \"{comment_text}\". "
            f"Write a short, friendly, on-brand reply (under 2 sentences)."
        )
        try:
            return await self.llm.generate(prompt, system="You are a friendly brand social media assistant.")
        except NotImplementedError:
            # Same placeholder state as content_generation until a real
            # LLM provider key is wired in fte_sdk/llm/client.py.
            logger.warning("LLM provider not yet configured — using a generic fallback reply")
            return "Thanks so much for your comment! 🙌"

    # ─── _create_and_post_reply() ──────────────────────────────

    async def _create_and_post_reply(
        self, comment: Comment, text: str, social_account_id: int, generated_by_llm: bool
    ):
        reply = Reply(comment_id=comment.id, text=text, generated_by_llm=generated_by_llm, status="approved")
        self.db.add(reply)
        await self.db.flush()

        account_result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == social_account_id)
        )
        account = account_result.scalar_one_or_none()
        access_token = ""
        if account and account.access_token:
            enc_key = get_fte_settings().ENCRYPTION_KEY
            access_token = decrypt_token(account.access_token, enc_key)

        client = MetaClient(access_token)
        try:
            result = await client.post_reply(comment.platform_post_id, text)
            reply.status = "posted" if result.get("status") == "posted" else "rejected"
        finally:
            await client.close()

    # ─── Dashboard read helpers (used by api.py) ───────────────

    async def list_comments(self, social_account_id: Optional[int] = None, escalated_only: bool = False) -> list[Comment]:
        query = select(Comment).order_by(Comment.created_at.desc()).limit(100)
        if social_account_id:
            query = query.where(Comment.social_account_id == social_account_id)
        if escalated_only:
            query = query.where(Comment.is_escalated == True)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def manual_reply(self, comment_id: int, text: str) -> Reply:
        """Human writes a reply from the dashboard — bypasses classification entirely."""
        comment_result = await self.db.execute(select(Comment).where(Comment.id == comment_id))
        comment = comment_result.scalar_one_or_none()
        if not comment:
            raise ValueError("Comment not found")
        await self._create_and_post_reply(comment, text, comment.social_account_id, generated_by_llm=False)
        comment.is_escalated = False
        result = await self.db.execute(select(Reply).where(Reply.comment_id == comment_id).order_by(Reply.id.desc()))
        return result.scalars().first()
