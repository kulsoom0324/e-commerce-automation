# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / meta_client.py
#
# PURPOSE: Meta Graph API client — reads comments on Instagram/
#          Facebook posts and posts replies.
#
#          DEV MODE: same convention as content_scheduling's
#          linkedin_client.py / tiktok_client.py — if no access
#          token is set, returns simulated data instead of failing,
#          so the agent is testable without real Meta app review
#          (which can take 1-4 weeks per the architecture doc).
#
# USED BY: handler.py, worker.py (poller)
# ═══════════════════════════════════════════════════════════════

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

META_BASE_URL = "https://graph.facebook.com/v19.0"


class MetaClient:
    """Meta Graph API client for reading/replying to comments.

    DEV MODE: Returns simulated comments/replies when no access_token set.
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client = httpx.AsyncClient(base_url=META_BASE_URL, timeout=30)

    async def verify_credentials(self) -> bool:
        """Verify the Meta access token by fetching /me."""
        if not self.access_token:
            logger.warning("Meta access_token not set — dev mode")
            return True
        try:
            response = await self._client.get("/me", params={"access_token": self.access_token})
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Meta credential check failed: {e}")
            return False

    async def fetch_comments(self, platform_post_id: str, since_id: Optional[str] = None) -> list[dict]:
        """Fetch comments on a published post.

        Returns a list of dicts: {id, author, text, created_time}.
        In dev mode, returns one simulated comment per call so the
        rest of the pipeline (rule engine → reply) can be exercised
        end-to-end without a real Meta app.
        """
        if not self.access_token:
            fake_id = f"meta_mock_comment_{int(time.time())}"
            logger.info(f"Meta dev mode: simulating a new comment on post {platform_post_id}")
            return [{
                "id": fake_id,
                "author": "dev_test_user",
                "text": "What's the price of this?",
                "created_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }]

        try:
            params = {"access_token": self.access_token, "fields": "id,from,message,created_time"}
            if since_id:
                params["since"] = since_id
            response = await self._client.get(f"/{platform_post_id}/comments", params=params)
            if response.status_code != 200:
                logger.error(f"Meta fetch_comments failed: {response.text}")
                return []
            data = response.json().get("data", [])
            return [
                {
                    "id": c.get("id", ""),
                    "author": c.get("from", {}).get("name", "unknown"),
                    "text": c.get("message", ""),
                    "created_time": c.get("created_time", ""),
                }
                for c in data
            ]
        except Exception as e:
            logger.error(f"Meta fetch_comments error: {e}")
            return []

    async def post_reply(self, platform_comment_id: str, text: str) -> dict:
        """Reply to a comment on Instagram/Facebook.

        Returns dict with status + platform_reply_id.
        """
        if not self.access_token:
            logger.info(f"Meta dev mode: would reply to {platform_comment_id}: {text[:50]}...")
            return {"status": "posted", "platform_reply_id": f"meta_mock_reply_{hash(text) % 100000}"}

        try:
            response = await self._client.post(
                f"/{platform_comment_id}/comments",
                data={"message": text, "access_token": self.access_token},
            )
            if response.status_code in (200, 201):
                reply_id = response.json().get("id", "")
                return {"status": "posted", "platform_reply_id": reply_id}
            logger.error(f"Meta post_reply failed: {response.text}")
            return {"status": "failed", "error": "Meta API error"}
        except Exception as e:
            logger.error(f"Meta post_reply error: {e}")
            return {"status": "failed", "error": str(e)}

    async def close(self):
        await self._client.aclose()
