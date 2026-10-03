# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / meta_client.py
#
# PURPOSE: Meta Graph API client for publishing posts to Instagram & Facebook.
#          Supports dev mode when token is absent or mock.
# ═══════════════════════════════════════════════════════════════

import logging
import uuid
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

META_BASE_URL = "https://graph.facebook.com/v19.0"


class MetaClient:
    """Client for publishing media to Instagram and Facebook via Meta Graph API."""

    def __init__(self, access_token: str = ""):
        self.access_token = access_token
        self.is_dev_mode = not bool(access_token) or access_token.startswith("mock_")

    async def verify_credentials(self) -> bool:
        if self.is_dev_mode:
            return True
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{META_BASE_URL}/me",
                    params={"access_token": self.access_token},
                )
                return res.status_code == 200
        except Exception:
            return False

    async def post_image(self, page_id: str, image_url: str, caption: str) -> dict:
        """Publish image to Instagram Graph API."""
        if self.is_dev_mode:
            return {
                "id": f"ig_post_{uuid.uuid4().hex[:8]}",
                "status": "published",
            }
        async with httpx.AsyncClient() as client:
            # Step 1: Create media container
            res = await client.post(
                f"{META_BASE_URL}/{page_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.access_token,
                },
            )
            data = res.json()
            creation_id = data.get("id")

            # Step 2: Publish media
            pub_res = await client.post(
                f"{META_BASE_URL}/{page_id}/media_publish",
                params={
                    "creation_id": creation_id,
                    "access_token": self.access_token,
                },
            )
            return pub_res.json()

    async def post_to_facebook(self, page_id: str, message: str, link: str = "") -> dict:
        """Publish post to Facebook Page."""
        if self.is_dev_mode:
            return {
                "id": f"fb_post_{uuid.uuid4().hex[:8]}",
                "status": "published",
            }
        async with httpx.AsyncClient() as client:
            params = {
                "message": message,
                "access_token": self.access_token,
            }
            if link:
                params["link"] = link
            res = await client.post(
                f"{META_BASE_URL}/{page_id}/feed",
                params=params,
            )
            return res.json()
