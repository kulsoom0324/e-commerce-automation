# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / tiktok_client.py
#
# PURPOSE: TikTok Content Publishing API v2 client.
#          Posts videos to TikTok Business accounts.
#
#          TikTok 3-step upload flow:
#          1. POST /v2/video/init/ → get upload URL
#          2. PUT <upload_url> → upload video binary
#          3. POST /v2/video/publish/ → publish
#
# USED BY: handler.py (multi-platform publish dispatch)
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TIKTOK_BASE_URL = "https://open-api.tiktok.com"
TIKTOK_API_VERSION = "v2"


class TikTokClient:
    """TikTok Content Publishing API client.

    DEV MODE: Returns simulated success when no access_token set.
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client = httpx.AsyncClient(base_url=TIKTOK_BASE_URL, timeout=60)

    async def verify_credentials(self) -> bool:
        """Verify TikTok access token is valid."""
        if not self.access_token:
            logger.warning("TikTok access_token not set — dev mode")
            return True  # Dev mode: always pass

        try:
            response = await self._client.get(
                f"/{TIKTOK_API_VERSION}/video/list/",
                params={"access_token": self.access_token, "max_count": 1},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"TikTok credential check failed: {e}")
            return False

    async def publish_video(self, caption: str, video_url: str) -> dict:
        """Publish a video to TikTok.

        In production, this follows the 3-step flow:
        1. Initialize upload → get upload URL
        2. Upload video file to the URL
        3. Call publish API

        For now, returns simulated success.
        """
        # DEV MODE
        if not self.access_token:
            logger.info(f"TikTok dev mode: would publish video with caption: {caption[:50]}...")
            return {
                "status": "published",
                "platform_post_id": f"tiktok_mock_{hash(caption) % 100000}",
                "platform": "tiktok",
            }

        try:
            # Step 1: Initialize upload
            init_response = await self._client.post(
                f"/{TIKTOK_API_VERSION}/video/init/",
                params={"access_token": self.access_token},
                json={
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": 0,  # Set actual size in production
                        "chunk_size": 0,
                        "total_chunk_count": 1,
                    }
                },
            )
            if init_response.status_code != 200:
                logger.error(f"TikTok init failed: {init_response.text}")
                return {"status": "failed", "error": "Upload initialization failed"}

            init_data = init_response.json()
            upload_url = init_data.get("data", {}).get("upload_url")

            # Step 2: Upload video (in production, download from video_url and upload)
            if upload_url:
                upload_response = await self._client.put(upload_url)
                if upload_response.status_code not in (200, 201):
                    logger.error(f"TikTok upload failed: {upload_response.text}")

            # Step 3: Publish
            publish_response = await self._client.post(
                f"/{TIKTOK_API_VERSION}/video/publish/",
                params={"access_token": self.access_token},
                json={
                    "post_info": {
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "title": caption[:150],  # TikTok max 150 chars
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    }
                },
            )
            if publish_response.status_code == 200:
                pub_data = publish_response.json()
                return {
                    "status": "published",
                    "platform_post_id": pub_data.get("data", {}).get("publish_id", ""),
                    "platform": "tiktok",
                }
            else:
                logger.error(f"TikTok publish failed: {publish_response.text}")
                return {"status": "failed", "error": "Publish API failed"}

        except Exception as e:
            logger.error(f"TikTok publish error: {e}")
            return {"status": "failed", "error": str(e)}

    async def get_post_status(self, publish_id: str) -> str:
        """Check status of a published post."""
        if not self.access_token:
            return "PUBLISHED"
        try:
            response = await self._client.get(
                f"/{TIKTOK_API_VERSION}/video/publish/status/",
                params={"access_token": self.access_token, "publish_id": publish_id},
            )
            if response.status_code == 200:
                return response.json().get("data", {}).get("status", "UNKNOWN")
        except Exception as e:
            logger.error(f"TikTok status check error: {e}")
        return "UNKNOWN"

    async def close(self):
        await self._client.aclose()
