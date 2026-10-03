# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / scheduler.py
#
# PURPOSE: Background polling scheduler — checks for due posts
#          every N minutes and publishes them to the right platform.
#
#          Platform dispatch:
#          - instagram/facebook → MetaClient
#          - tiktok → TikTokClient
#          - linkedin → LinkedInClient
#
# USED BY: worker.py (started via BaseAgent.on_start())
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import delete

from src.sdk.models.social import ScheduledPost, SocialAccount
from src.sdk.events import Event, PostPublishedEvent, PostPublishFailedEvent
from src.sdk.event_bus import RedisEventBus

from src.domains.agents.content_scheduling.handler import ContentSchedulingHandler

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
DEFAULT_INTERVAL_SECONDS = 120  # 2 minutes


class ContentScheduler:
    """Background loop that polls for due posts and publishes them.

    Runs as an asyncio.Task inside the worker lifecycle.
    """

    def __init__(
        self,
        db_factory: async_sessionmaker,
        event_bus: RedisEventBus,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ):
        self.db_factory = db_factory
        self.event_bus = event_bus
        self.interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the background polling loop."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Content scheduler started (interval={self.interval}s)")

    async def stop(self):
        """Stop the background polling loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Content scheduler stopped")

    async def _loop(self):
        """Main scheduler loop — runs forever until stopped."""
        while self._running:
            try:
                await self._check_and_publish()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(self.interval)

    async def _check_and_publish(self):
        """Check for due posts and publish them.

        SELECT * FROM scheduled_posts
        WHERE status = 'scheduled'
          AND scheduled_at <= now()
        ORDER BY scheduled_at ASC
        """
        async with self.db_factory() as db:
            try:
                now = datetime.now(timezone.utc)
                result = await db.execute(
                    select(ScheduledPost)
                    .where(ScheduledPost.status == "scheduled")
                    .where(ScheduledPost.scheduled_at <= now)
                    .where(ScheduledPost.retry_count < MAX_RETRIES)
                    .order_by(ScheduledPost.scheduled_at.asc())
                    .limit(20)  # Process max 20 per cycle
                )
                due_posts = result.scalars().all()

                if not due_posts:
                    return

                logger.info(f"Scheduler: {len(due_posts)} due post(s) found")

                for post in due_posts:
                    await self._publish_single(db, post)

                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(f"Scheduler cycle failed: {e}")

    async def _publish_single(self, db: AsyncSession, post: ScheduledPost):
        """Publish a single post to its target platform."""
        # Get social account for token
        account_result = await db.execute(
            select(SocialAccount).where(SocialAccount.id == post.social_account_id)
        )
        account = account_result.scalar_one_or_none()
        if not account or not account.is_active:
            logger.warning(f"Social account #{post.social_account_id} not found/inactive for post #{post.id}")
            post.status = "failed"
            post.retry_count = MAX_RETRIES  # No retry if account missing
            return

        handler = ContentSchedulingHandler(db)

        # Set to publishing
        post.status = "publishing"
        await db.flush()

        # Publish
        result = await handler.publish_post(
            account=account,
            caption=post.caption,
            media_urls=post.media_urls,
        )

        if result.get("status") == "published":
            post.status = "published"
            post.platform_post_id = result.get("platform_post_id", "")
            post.published_at = datetime.now(timezone.utc)
            logger.info(f"  ✅ Post #{post.id} published to {post.platform}")

            # Publish event for analytics
            if self.event_bus:
                event = PostPublishedEvent(
                    source="content_scheduling",
                    payload={
                        "scheduled_post_id": post.id,
                        "platform": post.platform,
                        "platform_post_id": post.platform_post_id,
                        "published_at": post.published_at.isoformat(),
                    },
                )
                await self.event_bus.publish("events", event.model_dump())

        else:
            post.retry_count += 1
            if post.retry_count >= MAX_RETRIES:
                post.status = "permanently_failed"
                logger.warning(f"  ❌ Post #{post.id} permanently failed after {MAX_RETRIES} retries")
            else:
                post.status = "scheduled"  # Will retry next cycle
                logger.warning(f"  ⚠️ Post #{post.id} failed (retry {post.retry_count}/{MAX_RETRIES})")

            # Publish failure event
            if self.event_bus:
                event = PostPublishFailedEvent(
                    source="content_scheduling",
                    payload={
                        "scheduled_post_id": post.id,
                        "platform": post.platform,
                        "error": result.get("error", "Unknown"),
                        "retry_count": post.retry_count,
                    },
                )
                await self.event_bus.publish("events", event.model_dump())
