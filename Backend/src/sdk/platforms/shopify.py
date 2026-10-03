# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / shopify.py
#
# PURPOSE: Shopify connector — implements PlatformConnector.
#          Talks to Shopify REST API via PyShopify SDK.
#          Returns normalized ProductData / OrderData.
#
# USED BY: PlatformRegistry, inventory_sync handler
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from asyncio import to_thread
from datetime import datetime, timezone

import shopify

from src.sdk.platforms.base import (
    PlatformConnector,
    PlatformAuth,
    ProductData,
    VariantData,
    OrderData,
    OrderItemData,
)

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2024-01"


class ShopifyConnector(PlatformConnector):
    """Shopify platform connector.

    Uses PyShopify SDK (synchronous, wrapped in asyncio.to_thread).
    OAuth: permanent access_token, no refresh needed.
    """

    platform = "shopify"

    # ─── Session Management ─────────────────────────────────────
    # PyShopify uses thread-local session — activate before each call.

    def _activate_session(self, auth: PlatformAuth):
        """Activate Shopify session for this request."""
        session = shopify.Session(auth.store_url, SHOPIFY_API_VERSION, auth.access_token)
        shopify.ShopifyResource.activate_session(session)

    def _clear_session(self):
        """Clear the active session."""
        shopify.ShopifyResource.clear_session()

    # ─── verify_credentials ─────────────────────────────────────
    # Lightweight check: try to fetch current shop.

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        try:
            self._activate_session(auth)
            result = await to_thread(shopify.Shop.current)
            self._clear_session()
            return result is not None
        except Exception as e:
            logger.warning(f"Shopify credential check failed: {e}")
            self._clear_session()
            return False

    # ─── fetch_products ─────────────────────────────────────────
    # Paginate through all products → normalize to ProductData.

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        self._activate_session(auth)
        try:
            products = await to_thread(shopify.Product.find, limit=250)
            all_products = []

            if isinstance(products, shopify.collection.PaginatedCollection):
                for page in shopify.PaginatedIterator(products):
                    for p in page:
                        all_products.append(self._product_to_data(p))
            else:
                for p in products:
                    all_products.append(self._product_to_data(p))

            return all_products
        finally:
            self._clear_session()

    # ─── fetch_orders ───────────────────────────────────────────
    # Paginate through orders within date range → OrderData.

    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        params = params or {}
        since_days = params.get("since_days", 90)
        status = params.get("status", None)

        since = (
            datetime.now(timezone.utc) - __import__("datetime").timedelta(days=since_days)
        ).isoformat() if since_days else None

        kwargs = {"limit": 250}
        if since:
            kwargs["query"] = f"created_at:>={since}"
        if status:
            kwargs["status"] = status

        self._activate_session(auth)
        try:
            orders = await to_thread(shopify.Order.find, **kwargs)
            all_orders = []

            if isinstance(orders, shopify.collection.PaginatedCollection):
                for page in shopify.PaginatedIterator(orders):
                    for o in page:
                        all_orders.append(self._order_to_data(o))
            else:
                for o in orders:
                    all_orders.append(self._order_to_data(o))

            return all_orders
        finally:
            self._clear_session()

    # ─── fetch_inventory ────────────────────────────────────────
    # Inventory is embedded in variants — extract from products.

    async def fetch_inventory(self, auth: PlatformAuth, params: dict = None) -> list:
        """Extract inventory from product variants."""
        products = await self.fetch_products(auth, params)
        inventory = []
        for p in products:
            for v in p.variants:
                from src.sdk.platforms.base import InventoryData
                inventory.append(InventoryData(
                    platform_variant_id=v.platform_variant_id,
                    quantity=v.inventory_quantity,
                ))
        return inventory

    # ─── Webhooks ───────────────────────────────────────────────
    # Register/unregister Shopify webhooks for real-time updates.

    async def register_webhook(self, auth: PlatformAuth, topic: str, callback_url: str) -> Optional[str]:
        self._activate_session(auth)
        try:
            hook = shopify.Webhook({"topic": topic, "address": callback_url, "format": "json"})
            await to_thread(hook.save)
            return str(hook.id)
        finally:
            self._clear_session()

    async def unregister_webhook(self, auth: PlatformAuth, webhook_id: str) -> bool:
        self._activate_session(auth)
        try:
            hook = await to_thread(shopify.Webhook.find, int(webhook_id))
            await to_thread(hook.destroy)
            return True
        except Exception as e:
            logger.warning(f"Failed to unregister webhook {webhook_id}: {e}")
            return False
        finally:
            self._clear_session()

    async def list_webhooks(self, auth: PlatformAuth) -> list[dict]:
        """List all registered webhooks (Shopify-specific helper)."""
        self._activate_session(auth)
        try:
            hooks = await to_thread(shopify.Webhook.find)
            return [{"id": h.id, "topic": h.topic, "address": h.address, "format": h.format}
                    for h in hooks]
        finally:
            self._clear_session()

    # ─── Normalization: Product → ProductData ───────────────────

    @staticmethod
    def _product_to_data(p: shopify.Product) -> ProductData:
        variants = []
        try:
            raw_variants = getattr(p, "variants", None) or []
        except AttributeError:
            raw_variants = []

        for v in raw_variants:
            try:
                c_at_price = float(v.compare_at_price) if getattr(v, "compare_at_price", None) else None
            except (AttributeError, TypeError, ValueError):
                c_at_price = None

            variants.append(VariantData(
                platform_variant_id=str(ShopifyConnector._parse_gid(getattr(v, "id", None)) or ""),
                title=str(getattr(v, "title", "") or ""),
                sku=str(getattr(v, "sku", "") or ""),
                price=float(getattr(v, "price", 0) or 0),
                compare_at_price=c_at_price,
                inventory_quantity=int(getattr(v, "inventory_quantity", 0) or 0),
            ))

        image_url = ""
        try:
            images = getattr(p, "images", None) or []
            if images:
                image_url = str(getattr(images[0], "src", "") or "")
        except (AttributeError, TypeError):
            image_url = ""

        return ProductData(
            platform_product_id=str(ShopifyConnector._parse_gid(getattr(p, "id", None)) or ""),
            title=str(getattr(p, "title", "") or ""),
            description=str(getattr(p, "body_html", "") or ""),
            vendor=str(getattr(p, "vendor", "") or ""),
            product_type=str(getattr(p, "product_type", "") or ""),
            status=(str(getattr(p, "status", "active") or "active")).lower(),
            image_url=image_url,
            variants=variants,
        )

    # ─── Normalization: Order → OrderData ───────────────────────

    @staticmethod
    def _order_to_data(o: shopify.Order) -> OrderData:
        line_items = []
        try:
            raw_items = getattr(o, "line_items", None) or []
        except AttributeError:
            raw_items = []

        for li in raw_items:
            vid = None
            raw_vid = getattr(li, "variant_id", None)
            if raw_vid:
                if isinstance(raw_vid, str) and "gid://" in raw_vid:
                    vid = str(ShopifyConnector._parse_gid(raw_vid))
                else:
                    vid = str(int(raw_vid)) if raw_vid else None
            line_items.append(OrderItemData(
                platform_variant_id=vid,
                quantity=int(getattr(li, "quantity", 1) or 1),
                price=float(getattr(li, "price", 0) or 0),
            ))

        ordered_at = getattr(o, "created_at", None)
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ordered_at = None

        return OrderData(
            platform_order_id=str(ShopifyConnector._parse_gid(getattr(o, "id", None)) or ""),
            order_number=str(getattr(o, "name", "") or ""),
            customer_email=str(getattr(o, "email", "") or ""),
            total_price=float(getattr(o, "total_price", 0) or 0),
            currency=str(getattr(o, "currency", "USD") or "USD"),
            financial_status=str(getattr(o, "financial_status", "pending") or "pending").lower(),
            fulfillment_status=getattr(o, "fulfillment_status", None),
            ordered_at=ordered_at,
            items=line_items,
        )

    # ─── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _parse_gid(gid: int | str | None) -> int | None:
        """Convert 'gid://shopify/Product/123456' → 123456."""
        if gid is None:
            return None
        gid_str = str(gid)
        if gid_str.startswith("gid://"):
            return int(gid_str.split("/")[-1])
        return int(gid)
