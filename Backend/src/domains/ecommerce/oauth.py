# ═══════════════════════════════════════════════════════════════
# src / domains / ecommerce / oauth.py
#
# PURPOSE: Universal OAuth callback routes for ALL platforms.
#          User ko platform ke auth page pe redirect karo ->
#          "Allow" -> callback -> code exchange -> token save.
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db
from src.sdk.models.base import Store
from src.sdk.platforms import PlatformRegistry, PlatformAuth
from src.sdk.oauth.providers import OAuthProviderRegistry
from src.sdk.oauth.tokens import TokenManager
from src.sdk.config import get_settings
from src.domains.security.jwt import create_access_token, decode_access_token
from src.domains.auth.service import get_current_user
from src.domains.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["OAuth"])
token_mgr = TokenManager()


def _extract_user_id_from_state(state: str) -> int | None:
    """Signed state token se user_id nikalo (OAuth CSRF + ownership ke liye)."""
    state_token = state.rsplit(":", 1)[1] if ":" in state else state
    if not state_token:
        return None
    try:
        payload = decode_access_token(state_token)
    except ValueError:
        return None
    if payload.get("type") != "oauth_state" or not payload.get("sub"):
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


@router.get("/{platform}/start")
async def oauth_start(
    platform: str,
    redirect_uri: str = "",
    state: str = "",
    current_user: User = Depends(get_current_user),
):
    """Step 1: User ko platform ke auth page pe redirect karo."""
    platform = platform.lower().strip()

    if not PlatformRegistry.is_supported(platform):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {platform}"
        )

    try:
        config = OAuthProviderRegistry.get_config(platform)
        redirect_target = config.redirect_uri or redirect_uri

        # User ID signed state mein embed karo taake callback par store
        # isi user se link ho (CSRF protection bhi).
        state_jwt = create_access_token(
            {"sub": str(current_user.id), "type": "oauth_state"},
            expires_delta=timedelta(minutes=15),
        )
        signed_state = f"{state}:{state_jwt}" if state else state_jwt

        # Shopify needs shop_name in the state
        if platform == "shopify":
            shop_name = state.split(":")[0] if ":" in state else state
            authorize_url = config.authorize_url.format(shop_domain=f"{shop_name}.myshopify.com")
            authorize_url += f"?client_id={config.client_id}&scope={','.join(config.scopes)}"
            authorize_url += f"&redirect_uri={redirect_target}&state={signed_state}"
        else:
            authorize_url = f"{config.authorize_url}?client_id={config.client_id}"
            authorize_url += f"&scope={','.join(config.scopes)}"
            authorize_url += f"&redirect_uri={redirect_target}&state={signed_state}"

        logger.info(f"OAuth redirect: {platform} -> {authorize_url}")
        return RedirectResponse(url=authorize_url)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth start failed for {platform}: {e}")
        raise HTTPException(status_code=502, detail="OAuth initiation failed")


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str = "",
    shop: str = "",
    state: str = "",
    hmac: str = "",
    timestamp: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Step 2: Platform wapas redirect karta hai code ke saath."""
    platform = platform.lower().strip()

    if not PlatformRegistry.is_supported(platform):
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    try:
        auth_code = code
        # state = "<shop_name>:<signed_jwt>" — JWT se user_id nikalo
        user_id = _extract_user_id_from_state(state)
        shop_name = state.split(":")[0] if ":" in state else state
        shop_name = shop or shop_name

        if not auth_code:
            raise HTTPException(status_code=400, detail="No authorization code received")

        if platform == "shopify":
            access_token = await _exchange_shopify_code(auth_code, shop_name)
            platform_store_id = f"{shop_name}.myshopify.com"
            store_name = shop_name
        else:
            # Future: implement OAuthFlow for other platforms
            raise HTTPException(
                status_code=501,
                detail=(
                    f"OAuth flow for {platform} is not yet implemented. "
                    f"Use POST /api/v1/stores/connect with API credentials instead."
                ),
            )

        existing = await db.execute(
            select(Store).where(Store.platform == platform, Store.platform_store_id == platform_store_id)
        )
        store = existing.scalar_one_or_none()

        if store:
            store.access_token = token_mgr.encrypt(access_token)
            store.is_active = True
            if user_id:
                store.user_id = user_id
        else:
            store = Store(
                user_id=user_id,
                platform=platform,
                name=store_name,
                platform_store_id=platform_store_id,
                access_token=token_mgr.encrypt(access_token),
                shop_name=shop_name,
                shop_domain=platform_store_id,
            )
            db.add(store)

        await db.commit()
        await db.refresh(store)
        logger.info(f"OAuth complete: {platform} store #{store.id} ({store_name})")

        return {
            "status": "connected",
            "store_id": store.id,
            "platform": platform,
            "message": f"{platform} store connected! Sync will begin shortly.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback failed for {platform}: {e}")
        raise HTTPException(status_code=502, detail=f"OAuth token exchange failed: {str(e)}")


async def _exchange_shopify_code(code: str, shop_name: str) -> str:
    """Exchange Shopify OAuth code for access token (direct API call)."""
    import httpx

    s = get_settings()
    shop_domain = f"{shop_name}.myshopify.com"
    token_url = f"https://{shop_domain}/admin/oauth/access_token"

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, json={
            "client_id": s.SHOPIFY_API_KEY,
            "client_secret": s.SHOPIFY_API_SECRET,
            "code": code,
        })
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Shopify token exchange failed: {response.text}"
            )
        return response.json()["access_token"]


@router.post("/{platform}/verify")
async def verify_platform_credentials(
    platform: str,
    api_key: str = Query(""),
    api_secret: str = Query(""),
    store_url: str = Query(""),
    access_token: str = Query(""),
):
    """Verify credentials for a platform without full OAuth.

    Useful for WooCommerce (consumer key/secret) or direct token entry.
    """
    platform = platform.lower().strip()

    if not PlatformRegistry.is_supported(platform):
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    auth = PlatformAuth(
        platform=platform,
        store_id=0,
        access_token=access_token,
        api_key=api_key,
        api_secret=api_secret,
        store_url=store_url,
    )

    try:
        connector = PlatformRegistry.get_connector(platform)
        valid = await connector.verify_credentials(auth)
        if valid:
            return {"status": "valid", "platform": platform}
        else:
            return {"status": "invalid", "platform": platform}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Verification failed: {str(e)}")
