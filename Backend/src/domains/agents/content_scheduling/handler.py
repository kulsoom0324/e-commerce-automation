# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / handler.py
#
# PURPOSE: Content Scheduling Handler — manages social posts lifecycle.
#          Multi-platform: Meta (IG/FB), TikTok, LinkedIn.
#          Handles schedule, publish, retry, and event publishing.
#
# USED BY: scheduler.py, worker.py, api.py
# ═══════════════════════════════════════════════════════════════

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.social import SocialAccount, ScheduledPost
from src.sdk.models.content import GeneratedPost, ImageAsset
from src.sdk.events import Event

from src.domains.agents.content_scheduling.config import get_settings

logger = logging.getLogger(__name__)


class ContentSchedulingHandler:
    """Manages social media post scheduling and publishing."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    # ═══════════════════════════════════════════════════════════
    # SOCIAL ACCOUNTS
    # ═══════════════════════════════════════════════════════════

    async def connect_account(self, store_id: int, platform: str,
                                account_name: str, account_id: str,
                                access_token: str, refresh_token: str = "") -> SocialAccount:
        """Connect a new social media account."""
        account = SocialAccount(
            store_id=store_id,
            platform=platform,
            account_name=account_name,
            account_id=account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            is_active=True,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        logger.info(f"Connected {platform} account: {account_name}")
        return account

    async def disconnect_account(self, account_id: int):
        """Disconnect (soft-delete) a social account."""
        account = await self._get_account(account_id)
        account.is_active = False
        await self.db.commit()
        logger.info(f"Disconnected social account #{account_id}")

    async def list_accounts(self, store_id: int, platform: str = None) -> list[SocialAccount]:
        """List social accounts, optionally filtered by platform."""
        query = select(SocialAccount).where(
            SocialAccount.store_id == store_id,
            SocialAccount.is_active == True,
        )
        if platform:
            query = query.where(SocialAccount.platform == platform)
        result = await self.db.execute(query)
        return result.scalars().all()

    # ═══════════════════════════════════════════════════════════
    # SCHEDULED POSTS
    # ═══════════════════════════════════════════════════════════

    async def schedule_post(
        self,
        social_account_id: int,
        caption: str,
        media_urls: list[str],
        platform: str,
        scheduled_at: datetime,
        product_id: Optional[int] = None,
        generated_post_id: Optional[int] = None,
    ) -> ScheduledPost:
        """Create a scheduled post."""
        post = ScheduledPost(
            social_account_id=social_account_id,
            product_id=product_id,
            generated_post_id=generated_post_id,
            caption=caption,
            media_urls=json.dumps(media_urls),
            platform=platform,
            scheduled_at=scheduled_at,
            status="scheduled",
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        logger.info(f"Scheduled post #{post.id} for {platform} at {scheduled_at}")
        return post

    async def cancel_post(self, post_id: int):
        """Cancel a scheduled post."""
        post = await self._get_scheduled_post(post_id)
        if post.status in ("published", "permanently_failed"):
            raise ValueError(f"Cannot cancel post in '{post.status}' status")
        post.status = "draft"
        await self.db.commit()
        logger.info(f"Cancelled scheduled post #{post_id}")

    async def list_scheduled_posts(
        self, store_id: int, platform: str = None, status: str = None
    ) -> list[dict]:
        """List scheduled posts with filters."""
        query = (
            select(ScheduledPost)
            .join(SocialAccount)
            .where(SocialAccount.store_id == store_id)
        )
        if platform:
            query = query.where(ScheduledPost.platform == platform)
        if status:
            query = query.where(ScheduledPost.status == status)
        query = query.order_by(ScheduledPost.scheduled_at.asc())

        result = await self.db.execute(query)
        posts = result.scalars().all()
        return [
            {
                "id": p.id,
                "social_account_id": p.social_account_id,
                "product_id": p.product_id,
                "platform": p.platform,
                "caption_preview": p.caption[:100] if p.caption else "",
                "scheduled_at": p.scheduled_at,
                "status": p.status,
                "published_at": p.published_at,
                "retry_count": p.retry_count,
                "created_at": p.created_at,
            }
            for p in posts
        ]

    # ═══════════════════════════════════════════════════════════
    # PUBLISH LOGIC (Multi-Platform)
    # ═══════════════════════════════════════════════════════════

    async def publish_post(self, account: SocialAccount, caption: str,
                            media_urls: str = "") -> dict:
        """Publish a post to the correct platform.

        Dispatches to the right client based on account.platform.
        """
        # Parse media URLs
        urls = []
        if media_urls:
            try:
                urls = json.loads(media_urls)
            except (json.JSONDecodeError, TypeError):
                if isinstance(media_urls, str) and media_urls.strip():
                    urls = [media_urls]

        platform = account.platform
        logger.info(f"Publishing to {platform} via account #{account.id}")

        if platform in ("instagram", "facebook"):
            return await self._publish_to_meta(account, caption, urls)
        elif platform == "tiktok":
            return await self._publish_to_tiktok(account, caption, urls)
        elif platform == "linkedin":
            return await self._publish_to_linkedin(account, caption, urls)
        else:
            logger.error(f"Unknown platform: {platform}")
            return {"status": "failed", "error": f"Unsupported platform: {platform}"}

    async def _publish_to_meta(self, account: SocialAccount, caption: str,
                                 media_urls: list[str]) -> dict:
        """Publish to Instagram or Facebook via Meta Graph API."""
        try:
            from src.domains.agents.content_scheduling.meta_client import MetaClient
            client = MetaClient(account.access_token)
            page_id = account.account_id

            if account.platform == "instagram":
                result = await client.post_image(
                    page_id=page_id,
                    image_url=media_urls[0] if media_urls else "",
                    caption=caption,
                )
            else:  # facebook
                result = await client.post_to_facebook(
                    page_id=page_id,
                    message=caption,
                    link=media_urls[0] if media_urls else "",
                )

            return {
                "status": "published",
                "platform_post_id": result.get("id", ""),
                "platform": account.platform,
            }
        except Exception as e:
            logger.error(f"Meta publish error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _publish_to_tiktok(self, account: SocialAccount, caption: str,
                                   media_urls: list[str]) -> dict:
        """Publish to TikTok via TikTok API."""
        try:
            from src.domains.agents.content_scheduling.tiktok_client import TikTokClient
            client = TikTokClient(account.access_token)
            return await client.publish_video(
                caption=caption,
                video_url=media_urls[0] if media_urls else "",
            )
        except Exception as e:
            logger.error(f"TikTok publish error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _publish_to_linkedin(self, account: SocialAccount, caption: str,
                                     media_urls: list[str]) -> dict:
        """Publish to LinkedIn via LinkedIn API."""
        try:
            from src.domains.agents.content_scheduling.linkedin_client import LinkedInClient
            client = LinkedInClient(account.access_token)
            return await client.publish_post(
                company_id=account.account_id,
                content=caption,
                media_urls=media_urls,
            )
        except Exception as e:
            logger.error(f"LinkedIn publish error: {e}")
            return {"status": "failed", "error": str(e)}

    async def publish_now(self, post_id: int) -> dict:
        """Immediately publish a scheduled post (bypass scheduler)."""
        post = await self._get_scheduled_post(post_id)
        if post.status in ("published", "permanently_failed"):
            raise ValueError(f"Post already in '{post.status}' status")

        account = await self._get_account(post.social_account_id)
        post.status = "publishing"
        await self.db.flush()

        result = await self.publish_post(account, post.caption, post.media_urls)

        if result.get("status") == "published":
            post.status = "published"
            post.platform_post_id = result.get("platform_post_id", "")
            post.published_at = datetime.now(timezone.utc)
        else:
            post.status = "scheduled"
            post.retry_count += 1

        await self.db.commit()
        return result

    # ═══════════════════════════════════════════════════════════
    # CONTENT APPROVED EVENT HANDLER
    # ═══════════════════════════════════════════════════════════

    async def handle_content_approved(self, payload: dict) -> Optional[ScheduledPost]:
        """Process ContentApprovedEvent from Agent 3.

        Converts approved generated content into a ScheduledPost.
        """
        platform = payload.get("platform", "instagram")
        caption = payload.get("caption", "")
        media_urls = payload.get("media_urls", [])
        product_id = payload.get("product_id")
        generated_post_id = payload.get("post_id")

        # Find a social account for this platform
        result = await self.db.execute(
            select(SocialAccount).where(
                SocialAccount.platform == platform,
                SocialAccount.is_active == True,
            ).limit(1)
        )
        account = result.scalar_one_or_none()
        if not account:
            logger.warning(f"No active {platform} account found for approved content")
            return None

        # Schedule immediately (now) or with delay
        scheduled_at = payload.get("scheduled_at")
        if not scheduled_at:
            scheduled_at = datetime.now(timezone.utc)

        post = await self.schedule_post(
            social_account_id=account.id,
            caption=caption,
            media_urls=media_urls,
            platform=platform,
            scheduled_at=scheduled_at,
            product_id=product_id,
            generated_post_id=generated_post_id,
        )
        return post

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    async def _get_account(self, account_id: int) -> SocialAccount:
        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Social account #{account_id} not found")
        return account

    async def _get_scheduled_post(self, post_id: int) -> ScheduledPost:
        result = await self.db.execute(
            select(ScheduledPost).where(ScheduledPost.id == post_id)
        )
        post = result.scalar_one_or_none()
        if not post:
            raise ValueError(f"Scheduled post #{post_id} not found")
        return post
