# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / big_commerce.py
#
# PURPOSE: BigCommerce connector — implements PlatformConnector.
#          REST API via OAuth 2.0 (X-Auth-Token). BigCommerce
#          uses store hash + permanent access token.
#
# USED BY: PlatformRegistry, inventory_sync handler
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

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

BIGCOMMERCE_API_VERSION = "v3"


class BigCommerceConnector(PlatformConnector):
    """BigCommerce platform connector.

    Auth: X-Auth-Token header (permanent OAuth token)
    Store URL: https://api.bigcommerce.com/stores/{store_hash}/
    API: REST (raw httpx)
    Webhooks: Supported
    """

    platform = "bigcommerce"

    def _get_client(self, auth: PlatformAuth) -> httpx.AsyncClient:
        """Create authenticated HTTP client for BigCommerce API."""
        if not auth.access_token:
            raise ValueError("BigCommerce requires access_token (X-Auth-Token)")
        if not auth.store_url:
            raise ValueError("BigCommerce requires store_url (store_hash)")

        base_url = f"https://api.bigcommerce.com/{BIGCOMMERCE_API_VERSION}"
        headers = {
            "X-Auth-Token": auth.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FTE-Agent/1.0",
        }
        return httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30)

    def _get_store_hash(self, auth: PlatformAuth) -> str:
        """Extract store hash from store_url."""
        # store_url could be: "abc123" or "https://abc123.mybigcommerce.com"
        url = auth.store_url
        if "://" in url:
            url = url.split("://")[1].split(".")[0]
        return url

    # ─── verify_credentials ─────────────────────────────────────

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        try:
            store_hash = self._get_store_hash(auth)
            client = self._get_client(auth)
            response = await client.get(f"/stores/{store_hash}/v3/catalog/summary")
            await client.aclose()
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"BigCommerce credential check failed: {e}")
            return False

    # ─── fetch_products ─────────────────────────────────────────

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        store_hash = self._get_store_hash(auth)
        client = self._get_client(auth)
        try:
            all_products = []
            page = 1

            while True:
                response = await client.get(
                    f"/stores/{store_hash}/v3/catalog/products",
                    params={
                        "limit": 250,
                        "page": page,
                        "include": "variants,images",
                    },
                )
                if response.status_code != 200:
                    logger.error(f"BigCommerce products fetch failed: {response.text}")
                    break

                data = response.json()
                products = data.get("data", [])
                if not products:
                    break

                for p in products:
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
        store_hash = self._get_store_hash(auth)

        client = self._get_client(auth)
        try:
            all_orders = []
            page = 1

            while True:
                response = await client.get(
                    f"/stores/{store_hash}/v2/orders",
                    params={
                        "limit": 250,
                        "page": page,
                        "min_date_created": since,
                    },
                )
                if response.status_code != 200:
                    logger.error(f"BigCommerce orders fetch failed: {response.text}")
                    break

                data = response.json()
                if not data:
                    break

                for o in data:
                    # Fetch order products for each order
                    order_products = await self._fetch_order_products(store_hash, o["id"], client)
                    all_orders.append(self._order_to_data(o, order_products))
                page += 1

            return all_orders
        finally:
            await client.aclose()

    async def _fetch_order_products(self, store_hash: str, order_id: int, client: httpx.AsyncClient) -> list:
        """Fetch products/line items for a specific order."""
        try:
            response = await client.get(
                f"/stores/{store_hash}/v2/orders/{order_id}/products"
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch order products for {order_id}: {e}")
        return []

    # ─── fetch_categories ───────────────────────────────────────

    async def fetch_categories(self, auth: PlatformAuth) -> list:
        from src.sdk.platforms.base import CategoryData
        store_hash = self._get_store_hash(auth)
        client = self._get_client(auth)
        try:
            response = await client.get(f"/stores/{store_hash}/v3/catalog/categories", params={"limit": 250})
            if response.status_code != 200:
                return []
            return [
                CategoryData(
                    platform_category_id=str(c["id"]),
                    name=c["name"],
                    parent_id=str(c["parent_id"]) if c.get("parent_id") else None,
                )
                for c in response.json().get("data", [])
            ]
        finally:
            await client.aclose()

    # ─── Webhooks ───────────────────────────────────────────────

    async def register_webhook(self, auth: PlatformAuth, topic: str, callback_url: str) -> Optional[str]:
        store_hash = self._get_store_hash(auth)
        client = self._get_client(auth)
        try:
            # Map our topic names to BigCommerce webhook topics
            topic_map = {
                "products/create": "store/product/created",
                "products/update": "store/product/updated",
                "products/delete": "store/product/deleted",
                "orders/create": "store/order/created",
                "orders/updated": "store/order/updated",
            }
            bc_topic = topic_map.get(topic, topic)

            response = await client.post(
                f"/stores/{store_hash}/v2/hooks",
                json={
                    "scope": bc_topic,
                    "destination": callback_url,
                    "is_active": True,
                },
            )
            if response.status_code in (200, 201):
                return str(response.json()["id"])
            logger.warning(f"BigCommerce webhook registration failed: {response.text}")
            return None
        finally:
            await client.aclose()

    async def unregister_webhook(self, auth: PlatformAuth, webhook_id: str) -> bool:
        store_hash = self._get_store_hash(auth)
        client = self._get_client(auth)
        try:
            response = await client.delete(f"/stores/{store_hash}/v2/hooks/{webhook_id}")
            return response.status_code in (200, 204)
        finally:
            await client.aclose()

    # ─── Normalization: Product → ProductData ───────────────────

    @staticmethod
    def _product_to_data(p: dict) -> ProductData:
        variants = []
        for v in (p.get("variants") or []):
            variants.append(VariantData(
                platform_variant_id=str(v["id"]),
                title=v.get("sku", ""),
                sku=v.get("sku", ""),
                price=float(v.get("price", 0) or 0),
                compare_at_price=float(v.get("sale_price")) if v.get("sale_price") else None,
                inventory_quantity=int(v.get("inventory_level", 0) or 0),
            ))

        # If no variants returned, create one from the product itself
        if not variants:
            variants.append(VariantData(
                platform_variant_id=str(p["id"]),
                title=p.get("name", ""),
                sku=p.get("sku", ""),
                price=float(p.get("price", 0) or 0),
                compare_at_price=float(p.get("sale_price")) if p.get("sale_price") else None,
                inventory_quantity=int(p.get("inventory_level", 0) or 0),
            ))

        image_url = ""
        images = p.get("images") or []
        if images:
            image_url = images[0].get("url_standard", "")

        return ProductData(
            platform_product_id=str(p["id"]),
            title=p.get("name", ""),
            description=p.get("description", "") or "",
            vendor=p.get("brand_name", ""),
            product_type=p.get("type", ""),
            status="active" if p.get("is_visible", True) else "inactive",
            image_url=image_url,
            variants=variants,
        )

    # ─── Normalization: Order → OrderData ───────────────────────

    @staticmethod
    def _order_to_data(o: dict, order_products: list = None) -> OrderData:
        line_items = []
        if order_products:
            for op in order_products:
                line_items.append(OrderItemData(
                    platform_variant_id=str(op.get("product_id", "")),
                    quantity=int(op.get("quantity", 1)),
                    price=float(op.get("price_inc_tax", 0) or 0),
                ))

        ordered_at = o.get("date_created")
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ordered_at = None

        return OrderData(
            platform_order_id=str(o["id"]),
            order_number=str(o.get("order_id", "") or o.get("id", "")),
            customer_email=o.get("billing_address", {}).get("email", "") if o.get("billing_address") else "",
            total_price=float(o.get("total_inc_tax", 0) or 0),
            currency=o.get("currency_code", "USD"),
            financial_status=o.get("status", "pending"),
            fulfillment_status="shipped" if o.get("status") == "shipped" else "pending",
            ordered_at=ordered_at,
            items=line_items,
        )
