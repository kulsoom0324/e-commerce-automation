# ═══════════════════════════════════════════════════════════════
# src / domains / ecommerce / webhooks.py
#
# PURPOSE: Shopify webhook receiver. HMAC verify -> lookup store ->
#          publish event to Redis -> inventory_sync agent processes.
# ═══════════════════════════════════════════════════════════════

import logging
import re

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db
from src.sdk.models import Store
from src.sdk.auth import verify_hmac
from src.sdk.config import get_settings

from src.dependencies import get_event_bus
from src.domains.ecommerce.event_publisher import EventPublisher

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/{shop_name}/{topic}", status_code=202)
async def receive_webhook(
    shop_name: str,
    topic: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    bus=Depends(get_event_bus),
):
    """Receive Shopify webhook -> verify HMAC -> publish event -> return 202."""
    # 0. Validate shop_name - prevent path injection
    clean_shop_name = shop_name.split(".")[0]
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,}$", clean_shop_name):
        raise HTTPException(status_code=400, detail="Invalid shop name")

    # 1. Get store from DB
    stmt = select(Store).where(Store.shop_name == clean_shop_name)
    result = await db.execute(stmt)
    store = result.scalar_one_or_none()
    if not store:
        logger.warning(f"Webhook for unknown store: {shop_name}")
        raise HTTPException(status_code=404, detail="Store not found")

    # 2. Verify HMAC signature
    raw_body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    secret = get_settings().SHOPIFY_API_SECRET
    if secret and not verify_hmac(raw_body, hmac_header, secret):
        logger.warning(f"HMAC mismatch for store {shop_name}")
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    # 3. Parse payload
    payload = await request.json()
    logger.info(f"Webhook received: store={shop_name}, topic={topic}")

    # 4. Publish event -> inventory_sync agent picks it up
    publisher = EventPublisher(bus)
    await publisher.publish_webhook(shop_name, topic, payload, store.id)

    return {"status": "accepted"}
