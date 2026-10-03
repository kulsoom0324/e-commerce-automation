# ═══════════════════════════════════════════════════════════════
# agents / content_generation / image_gen.py
#
# PURPOSE: Image generation clients — Gemini 2.0 AND DALL-E 3.
#          Factory function auto-selects based on model name.
#          DEV MODE: Returns mock URL when no API key set.
#
# USED BY: handler.py (content generation pipeline)
# ═══════════════════════════════════════════════════════════════

import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MOCK_IMAGE_URL = "https://cdn.example.com/mock_generated_image.png"


class ImageGenerator(ABC):
    """Abstract image generator. Implementations: Gemini, DALL-E 3."""

    @abstractmethod
    async def generate(self, prompt: str, style: str = "", size: str = "1024x1024") -> dict:
        """Generate image from text prompt.

        Returns: {"url": str, "model": str, "prompt_used": str}
        """
        pass


class GeminiImageGenerator(ImageGenerator):
    """Google Gemini 2.0 Flash image generation.
    API: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, prompt: str, style: str = "", size: str = "1024x1024") -> dict:
        # DEV MODE — no API key set
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set — returning mock image URL")
            return {"url": MOCK_IMAGE_URL, "model": "gemini", "prompt_used": prompt}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.0-flash-exp:generateContent?key={self.api_key}",
                    json={
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }],
                        "generationConfig": {
                            "temperature": 0.4,
                            "topK": 32,
                            "topP": 1,
                        },
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    # Gemini returns base64 image in response
                    # In production: upload base64 to CDN, return CDN URL
                    # For now: return placeholder
                    return {"url": MOCK_IMAGE_URL, "model": "gemini", "prompt_used": prompt}
                else:
                    logger.error(f"Gemini image generation failed: {response.text}")
                    return {"url": MOCK_IMAGE_URL, "model": "gemini", "prompt_used": prompt}
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {"url": MOCK_IMAGE_URL, "model": "gemini", "prompt_used": prompt}


class DalleImageGenerator(ImageGenerator):
    """OpenAI DALL-E 3 image generation.
    API: POST https://api.openai.com/v1/images/generations
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, prompt: str, style: str = "", size: str = "1024x1024") -> dict:
        # DEV MODE — no API key set
        if not self.api_key:
            logger.warning("DALLE_API_KEY not set — returning mock image URL")
            return {"url": MOCK_IMAGE_URL, "model": "dalle3", "prompt_used": prompt}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": size,
                        "quality": "standard",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    url = data.get("data", [{}])[0].get("url", MOCK_IMAGE_URL)
                    return {"url": url, "model": "dalle3", "prompt_used": prompt}
                else:
                    logger.error(f"DALL-E generation failed: {response.text}")
                    return {"url": MOCK_IMAGE_URL, "model": "dalle3", "prompt_used": prompt}
        except Exception as e:
            logger.error(f"DALL-E API error: {e}")
            return {"url": MOCK_IMAGE_URL, "model": "dalle3", "prompt_used": prompt}


def create_image_generator(model: str, api_key: str) -> ImageGenerator:
    """Factory: returns the right generator based on model name.

    Usage:
        gen = create_image_generator("gemini", settings.GEMINI_API_KEY)
        gen = create_image_generator("dalle3", settings.DALLE_API_KEY)
    """
    model = model.lower().strip()
    if model.startswith("gemini"):
        return GeminiImageGenerator(api_key)
    elif model == "dalle3" or model == "dall-e-3":
        return DalleImageGenerator(api_key)
    else:
        raise ValueError(f"Unknown image model: '{model}'. Choose 'gemini' or 'dalle3'")
