# ═══════════════════════════════════════════════════════════════
# agents / content_scheduling / linkedin_client.py
#
# PURPOSE: LinkedIn Company Page API v2 client.
#          Posts text + image content to LinkedIn company pages.
#
#          API: POST /rest/posts (urn:li:organization:{company_id})
#          Images: POST /rest/images?action=initializeUpload
#
# USED BY: handler.py (multi-platform publish dispatch)
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LINKEDIN_BASE_URL = "https://api.linkedin.com"
LINKEDIN_API_VERSION = "v2"


class LinkedInClient:
    """LinkedIn Company Page API client.

    DEV MODE: Returns simulated success when no access_token set.
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client = httpx.AsyncClient(base_url=LINKEDIN_BASE_URL, timeout=30)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "User-Agent": "FTE-Agent/1.0",
        }

    async def verify_credentials(self) -> bool:
        """Verify LinkedIn access token by fetching user profile."""
        if not self.access_token:
            logger.warning("LinkedIn access_token not set — dev mode")
            return True

        try:
            response = await self._client.get(
                f"/{LINKEDIN_API_VERSION}/me",
                headers=self._headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"LinkedIn credential check failed: {e}")
            return False

    async def publish_post(self, company_id: str, content: str, media_urls: list[str] = None) -> dict:
        """Publish a text/image post to a LinkedIn company page.

        Args:
            company_id: LinkedIn organization URN (e.g., "1234567")
            content: Post text content
            media_urls: Optional list of image URLs to attach

        Returns:
            dict with status, platform_post_id, platform
        """
        if not self.access_token:
            logger.info(f"LinkedIn dev mode: would post to company {company_id}: {content[:50]}...")
            return {
                "status": "published",
                "platform_post_id": f"linkedin_mock_{hash(content) % 100000}",
                "platform": "linkedin",
            }

        try:
            # Build the post body
            author_urn = f"urn:li:organization:{company_id}"

            if media_urls:
                # Register image upload first
                image_urn = await self._register_image_upload(company_id)
                if image_urn:
                    # Post with image
                    post_body = {
                        "author": author_urn,
                        "commentary": content,
                        "visibility": "PUBLIC",
                        "distribution": {
                            "feedDistribution": "MAIN_FEED",
                            "targetEntities": [],
                            "thirdPartyDistributionChannels": [],
                        },
                        "content": {
                            "media": {
                                "title": "",
                                "id": image_urn,
                            }
                        },
                        "lifecycleState": "PUBLISHED",
                    }
                else:
                    # Fallback to text-only
                    post_body = await self._text_only_post(author_urn, content)
            else:
                post_body = await self._text_only_post(author_urn, content)

            response = await self._client.post(
                "/rest/posts",
                headers=self._headers(),
                json=post_body,
            )

            if response.status_code in (200, 201):
                post_id = response.headers.get("x-restli-id", "")
                return {
                    "status": "published",
                    "platform_post_id": post_id or f"linkedin_{company_id}",
                    "platform": "linkedin",
                }
            else:
                logger.error(f"LinkedIn publish failed: {response.text}")
                return {"status": "failed", "error": "LinkedIn API error"}

        except Exception as e:
            logger.error(f"LinkedIn publish error: {e}")
            return {"status": "failed", "error": str(e)}

    async def _text_only_post(self, author_urn: str, content: str) -> dict:
        """Build a text-only LinkedIn post body."""
        return {
            "author": author_urn,
            "commentary": content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

    async def _register_image_upload(self, company_id: str) -> Optional[str]:
        """Register an image upload with LinkedIn.

        Returns the image URN if registration succeeds, None otherwise.
        """
        try:
            response = await self._client.post(
                "/rest/images?action=initializeUpload",
                headers=self._headers(),
                json={
                    "initializeUploadRequest": {
                        "owner": f"urn:li:organization:{company_id}",
                    }
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", {}).get("image", "")
        except Exception as e:
            logger.warning(f"LinkedIn image upload registration failed: {e}")
        return None

    async def close(self):
        await self._client.aclose()
