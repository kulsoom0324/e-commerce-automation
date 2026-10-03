# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / woo_commerce.py
#
# PURPOSE: WooCommerce connector — implements PlatformConnector.
#          REST API via Basic Auth (Consumer Key + Consumer Secret).
#          Self-hosted WordPress stores ke liye.
#
# USED BY: PlatformRegistry, inventory_sync handler
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import base64

import httpx

from src.sdk.platforms.base import (
    PlatformConnector,
    PlatformAuth,
    ProductData,
    VariantData,
    OrderData,
    OrderItemData,
)

logger = logging.getLogger(__name__)

WOOCOMMERCE_API_VERSION = "wc/v3"


class WooCommerceConnector(PlatformConnector):
    """WooCommerce platform connector.

    Auth: Basic Auth (Consumer Key + Consumer Secret)
    Token: Permanent (no refresh needed)
    API: REST (raw httpx, no SDK)
    Webhooks: Supported
    """

    platform = "woocommerce"

    def _get_client(self, auth: PlatformAuth) -> httpx.AsyncClient:
        """Create authenticated HTTP client for WooCommerce REST API."""
        base_url = auth.store_url.rstrip("/")
        api_url = f"{base_url}/wp-json/{WOOCOMMERCE_API_VERSION}"

        if not auth.api_key or not auth.api_secret:
            raise ValueError("WooCommerce requires api_key (consumer_key) and api_secret (consumer_secret)")

        # Basic Auth: base64(consumer_key:consumer_secret)
        auth_header = base64.b64encode(f"{auth.api_key}:{auth.api_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json",
            "User-Agent": "FTE-Agent/1.0",
        }
        return httpx.AsyncClient(base_url=api_url, headers=headers, timeout=30)

    # ─── verify_credentials ─────────────────────────────────────
    # Fetch 1 order to verify credentials.

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        try:
            client = self._get_client(auth)
            response = await client.get("/orders", params={"per_page": 1})
            await client.aclose()
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"WooCommerce credential check failed: {e}")
            return False

    # ─── fetch_products ─────────────────────────────────────────

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        client = self._get_client(auth)
        try:
            all_products = []
            page = 1

            while True:
                response = await client.get("/products", params={
                    "per_page": 100,
                    "page": page,
                })
                if response.status_code != 200:
                    logger.error(f"WooCommerce products fetch failed: {response.text}")
                    break

                data = response.json()
                if not data:
                    break

                for p in data:
                    all_products.append(self._product_to_data(p))
                page += 1

            return all_products
        finally:
            await client.aclose()

    # ─── fetch_orders ───────────────────────────────────────────

    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        params = params or {}
        since_days = params.get("since_days", 90)

        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

        client = self._get_client(auth)
        try:
            all_orders = []
            page = 1

            while True:
                response = await client.get("/orders", params={
                    "per_page": 100,
                    "page": page,
                    "after": since,
                })
                if response.status_code != 200:
                    logger.error(f"WooCommerce orders fetch failed: {response.text}")
                    break

                data = response.json()
                if not data:
                    break

                for o in data:
                    all_orders.append(self._order_to_data(o))
                page += 1

            return all_orders
        finally:
            await client.aclose()

    # ─── fetch_categories ───────────────────────────────────────

    async def fetch_categories(self, auth: PlatformAuth) -> list:
        from src.sdk.platforms.base import CategoryData
        client = self._get_client(auth)
        try:
            response = await client.get("/products/categories", params={"per_page": 100})
            if response.status_code != 200:
                return []
            return [
                CategoryData(
                    platform_category_id=str(c["id"]),
                    name=c["name"],
                    parent_id=str(c["parent"]) if c.get("parent") else None,
                )
                for c in response.json()
            ]
        finally:
            await client.aclose()

    # ─── Webhooks ───────────────────────────────────────────────

    async def register_webhook(self, auth: PlatformAuth, topic: str, callback_url: str) -> Optional[str]:
        client = self._get_client(auth)
        try:
            response = await client.post("/webhooks", json={
                "name": f"FTE {topic}",
                "topic": topic,
                "delivery_url": callback_url,
            })
            if response.status_code in (200, 201):
                return str(response.json()["id"])
            logger.warning(f"WooCommerce webhook registration failed: {response.text}")
            return None
        finally:
            await client.aclose()

    async def unregister_webhook(self, auth: PlatformAuth, webhook_id: str) -> bool:
        client = self._get_client(auth)
        try:
            response = await client.delete(f"/webhooks/{webhook_id}")
            return response.status_code in (200, 204)
        finally:
            await client.aclose()

    # ─── Normalization: Product → ProductData ───────────────────

    @staticmethod
    def _product_to_data(p: dict) -> ProductData:
        variants = []

        # WooCommerce has variations (separate endpoint) and also simple products
        if p.get("type") == "variable":
            # Variable products have no own price — variations are the real variants
            # We'll add a single placeholder, variations fetched separately
            variants.append(VariantData(
                platform_variant_id=str(p["id"]),
                title=p.get("name", ""),
                sku=p.get("sku", ""),
                price=float(p.get("price", 0) or 0),
                compare_at_price=float(p["regular_price"]) if p.get("regular_price") else None,
                inventory_quantity=int(p.get("stock_quantity", 0) or 0),
            ))
        else:
            variants.append(VariantData(
                platform_variant_id=str(p["id"]),
                title=p.get("name", ""),
                sku=p.get("sku", ""),
                price=float(p.get("price", 0) or 0),
                compare_at_price=float(p["regular_price"]) if p.get("regular_price") else None,
                inventory_quantity=int(p.get("stock_quantity", 0) or 0),
            ))

        image_url = ""
        images = p.get("images", [])
        if images:
            image_url = images[0].get("src", "")

        return ProductData(
            platform_product_id=str(p["id"]),
            title=p.get("name", ""),
            description=p.get("description", "") or "",
            vendor="",
            product_type="",
            status="active" if p.get("status") == "publish" else "inactive",
            image_url=image_url,
            variants=variants,
        )

    # ─── Normalization: Order → OrderData ───────────────────────

    @staticmethod
    def _order_to_data(o: dict) -> OrderData:
        line_items = []
        for li in (o.get("line_items") or []):
            line_items.append(OrderItemData(
                platform_variant_id=str(li.get("variation_id") or li.get("product_id", "")),
                quantity=int(li.get("quantity", 1)),
                price=float(li.get("price", 0) or 0),
            ))

        ordered_at = o.get("date_created")
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ordered_at = None

        return OrderData(
            platform_order_id=str(o["id"]),
            order_number=str(o.get("number", "") or o.get("id", "")),
            customer_email=o.get("billing", {}).get("email", "") if o.get("billing") else "",
            total_price=float(o.get("total", 0) or 0),
            currency=o.get("currency", "USD"),
            financial_status=o.get("status", "pending"),
            fulfillment_status="completed" if o.get("date_completed") else "pending",
            ordered_at=ordered_at,
            items=line_items,
        )
