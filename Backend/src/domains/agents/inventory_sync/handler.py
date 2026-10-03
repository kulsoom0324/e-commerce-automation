# ═══════════════════════════════════════════════════════════════
# agents / inventory_sync / handler.py
#
# PURPOSE: Inventory Sync Handler — MULTI-PLATFORM now.
#          PlatformRegistry use karta hai, direct Shopify calls nahi.
#          Kisi bhi e-commerce platform se data sync kar sakta hai.
#
# USED BY: worker.py
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.base import Store, Product, Variant, Order, OrderItem, LowStockAlert
from src.sdk.platforms import PlatformRegistry, PlatformAuth
from src.sdk.platforms.base import ProductData, OrderData, VariantData, OrderItemData
from src.sdk.oauth.tokens import TokenManager
from src.sdk.config import get_settings

logger = logging.getLogger(__name__)


class InventorySyncHandler:
    """Multi-platform inventory sync handler.

    Works with ANY platform (Shopify, WooCommerce, Amazon, Daraz, etc.)
    Auto-detects platform from Store record → uses right connector.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.token_mgr = TokenManager()

    # ─── Core: Get Store + Build Auth ───────────────────────────

    async def _get_store(self, store_id: int) -> Store:
        result = await self.db.execute(select(Store).where(Store.id == store_id))
        store = result.scalar_one_or_none()
        if not store:
            raise ValueError(f"Store {store_id} not found")
        return store

    def _build_auth(self, store: Store) -> PlatformAuth:
        """Build PlatformAuth from store record (auto-decrypts tokens)."""
        return self.token_mgr.build_auth(store)

    # ─── Full Sync ──────────────────────────────────────────────

    async def initial_full_sync(self, store_id: int) -> dict:
        """Full sync — works with ANY platform.
        Auto-detects → fetches products + orders → saves to DB.
        """
        logger.info(f"Starting full sync for store_id={store_id}")
        store = await self._get_store(store_id)
        auth = self._build_auth(store)
        connector = PlatformRegistry.get_connector(store.platform)

        # 1. Sync all products
        products = await connector.fetch_products(auth)
        products_result = await self._upsert_products(store_id, products)

        # 2. Sync recent orders
        orders = await connector.fetch_orders(auth, {"since_days": self.settings.ORDERS_SYNC_DAYS})
        orders_result = await self._upsert_orders(store_id, orders)

        summary = {
            "status": "completed",
            "platform": store.platform,
            "products_synced": products_result["products_count"],
            "variants_synced": products_result["variants_count"],
            "orders_synced": orders_result["orders_count"],
        }
        logger.info(f"Full sync complete for store_id={store_id}: {summary}")
        return summary

    async def refresh_products(self, store_id: int) -> dict:
        """Refresh just products."""
        store = await self._get_store(store_id)
        auth = self._build_auth(store)
        connector = PlatformRegistry.get_connector(store.platform)

        products = await connector.fetch_products(auth)
        result = await self._upsert_products(store_id, products)
        return {"status": "completed", "products_synced": result["products_count"]}

    async def refresh_orders(self, store_id: int, since_days: int = 30) -> dict:
        """Refresh just orders."""
        store = await self._get_store(store_id)
        auth = self._build_auth(store)
        connector = PlatformRegistry.get_connector(store.platform)

        orders = await connector.fetch_orders(auth, {"since_days": since_days})
        result = await self._upsert_orders(store_id, orders)
        return {"status": "completed", "orders_synced": result["orders_count"]}

    # ─── Webhook Event Processing ───────────────────────────────

    async def handle_webhook_event(self, store_id: int, topic: str, payload: dict):
        """Process webhook event — platform-agnostic router."""
        store = await self._get_store(store_id)
        logger.info(f"Webhook: topic={topic}, store={store_id}, platform={store.platform}")

        # Platform-specific webhook handling
        # Shopify webhooks come in Shopify format → normalize → upsert
        if store.platform == "shopify":
            await self._handle_shopify_webhook(store_id, topic, payload)
        else:
            logger.warning(f"Webhooks for {store.platform} not yet implemented")

    async def _handle_shopify_webhook(self, store_id: int, topic: str, payload: dict):
        """Handle Shopify-specific webhook events."""
        if topic in ("products/create", "products/update"):
            data = self._shopify_product_webhook_to_data(payload)
            await self._upsert_products(store_id, [data])
        elif topic == "products/delete":
            await self._handle_product_delete(store_id, payload)
        elif topic == "inventory_levels/update":
            await self._handle_inventory_update(store_id, payload)
        elif topic in ("orders/create", "orders/updated"):
            data = self._shopify_order_webhook_to_data(payload)
            await self._upsert_orders(store_id, [data])
        else:
            logger.warning(f"Unknown webhook topic: {topic}")

    # ─── UPSERT Products ────────────────────────────────────────

    async def _upsert_products(self, store_id: int, products: list[ProductData]) -> dict:
        """Generic product upsert — works with ANY platform."""
        products_count = 0
        variants_count = 0

        for p in products:
            await self._upsert_product(store_id, p)
            products_count += 1
            variants_count += len(p.variants)

        return {"products_count": products_count, "variants_count": variants_count}

    async def _upsert_product(self, store_id: int, data: ProductData):
        """Insert or update a product + its variants."""
        # Try by platform_product_id first, then fallback to shopify_id
        stmt = select(Product).where(
            Product.store_id == store_id,
            Product.platform_product_id == data.platform_product_id
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()

        if product:
            product.title = data.title
            product.description = data.description
            product.vendor = data.vendor
            product.product_type = data.product_type
            product.status = data.status
            product.image_url = data.image_url
            product.extra_data = data.extra_data
        else:
            product = Product(
                store_id=store_id,
                platform_product_id=data.platform_product_id,
                title=data.title,
                description=data.description,
                vendor=data.vendor,
                product_type=data.product_type,
                status=data.status,
                image_url=data.image_url,
                extra_data=data.extra_data,
            )
            self.db.add(product)

        await self.db.flush()

        # Upsert variants
        for v_data in data.variants:
            await self._upsert_variant(product.id, v_data)

    async def _upsert_variant(self, product_id: int, data: VariantData):
        """Insert or update a variant."""
        stmt = select(Variant).where(
            Variant.product_id == product_id,
            Variant.platform_variant_id == data.platform_variant_id
        )
        result = await self.db.execute(stmt)
        variant = result.scalar_one_or_none()

        if variant:
            variant.title = data.title
            variant.sku = data.sku
            variant.price = data.price
            variant.compare_at_price = data.compare_at_price
            old_qty = variant.inventory_quantity
            variant.inventory_quantity = data.inventory_quantity
            variant.extra_data = data.extra_data
        else:
            variant = Variant(
                product_id=product_id,
                platform_variant_id=data.platform_variant_id,
                title=data.title,
                sku=data.sku,
                price=data.price,
                compare_at_price=data.compare_at_price,
                inventory_quantity=data.inventory_quantity,
                low_stock_threshold=self.settings.LOW_STOCK_THRESHOLD,
                extra_data=data.extra_data,
            )
            self.db.add(variant)

        await self.db.flush()

        # Check low stock
        await self._check_and_alert_low_stock(variant)

    # ─── UPSERT Orders ──────────────────────────────────────────

    async def _upsert_orders(self, store_id: int, orders: list[OrderData]) -> dict:
        """Generic order upsert — works with ANY platform."""
        orders_count = 0

        for o in orders:
            await self._upsert_order(store_id, o)
            orders_count += 1

        return {"orders_count": orders_count}

    async def _upsert_order(self, store_id: int, data: OrderData):
        """Insert or update an order."""
        stmt = select(Order).where(
            Order.store_id == store_id,
            Order.platform_order_id == data.platform_order_id
        )
        result = await self.db.execute(stmt)
        order = result.scalar_one_or_none()

        if order:
            order.financial_status = data.financial_status
            order.fulfillment_status = data.fulfillment_status
            order.total_price = data.total_price
            order.extra_data = data.extra_data
        else:
            order = Order(
                store_id=store_id,
                platform_order_id=data.platform_order_id,
                order_number=data.order_number,
                customer_email=data.customer_email,
                total_price=data.total_price,
                currency=data.currency,
                financial_status=data.financial_status,
                fulfillment_status=data.fulfillment_status,
                ordered_at=data.ordered_at or datetime.now(timezone.utc),
                extra_data=data.extra_data,
            )
            self.db.add(order)

        await self.db.flush()

        # Replace order items (delete old, insert new)
        if order.id:
            await self.db.execute(
                delete(OrderItem).where(OrderItem.order_id == order.id)
            )

        for item_data in data.items:
            variant_id = await self._resolve_variant_id(store_id, item_data.platform_variant_id)
            if variant_id:
                item = OrderItem(
                    order_id=order.id,
                    variant_id=variant_id,
                    quantity=item_data.quantity,
                    price=item_data.price,
                )
                self.db.add(item)

    async def _resolve_variant_id(self, store_id: int, platform_variant_id: str) -> int | None:
        """Resolve platform variant ID → internal DB variant ID."""
        if not platform_variant_id:
            return None
        stmt = select(Variant.id).where(
            Variant.platform_variant_id == platform_variant_id,
            Variant.product.has(store_id=store_id),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ─── Webhook Helpers (Shopify-specific normalization) ───────

    @staticmethod
    def _shopify_product_webhook_to_data(payload: dict) -> ProductData:
        """Convert Shopify webhook payload → ProductData."""
        variants = []
        for v in (payload.get("variants") or []):
            variants.append(VariantData(
                platform_variant_id=str(v.get("id", "")),
                title=v.get("title", ""),
                sku=v.get("sku", ""),
                price=float(v.get("price", 0)),
                compare_at_price=float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                inventory_quantity=int(v.get("inventory_quantity", 0)),
            ))

        image_url = ""
        images = payload.get("images") or []
        if images:
            image_url = images[0].get("src", "") or images[0].get("src", "")

        # Try to resolve Shopify ID → string platform ID
        pid = str(payload.get("id", ""))
        return ProductData(
            platform_product_id=pid,
            title=payload.get("title", ""),
            description=payload.get("body_html") or "",
            vendor=payload.get("vendor") or "",
            product_type=payload.get("product_type") or "",
            status=payload.get("status", "active"),
            image_url=image_url,
            variants=variants,
        )

    @staticmethod
    def _shopify_order_webhook_to_data(payload: dict) -> OrderData:
        """Convert Shopify order webhook → OrderData."""
        line_items = []
        for li in (payload.get("line_items") or []):
            vid = li.get("variant_id")
            line_items.append(OrderItemData(
                platform_variant_id=str(vid) if vid else None,
                quantity=li.get("quantity", 1),
                price=float(li.get("price", 0)),
            ))

        ordered_at = payload.get("created_at")
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ordered_at = None

        return OrderData(
            platform_order_id=str(payload.get("id", "")),
            order_number=payload.get("name") or "",
            customer_email=payload.get("email") or "",
            total_price=float(payload.get("total_price", 0)),
            currency=payload.get("currency", "USD"),
            financial_status=payload.get("financial_status", "pending"),
            fulfillment_status=payload.get("fulfillment_status"),
            ordered_at=ordered_at,
            items=line_items,
        )

    # ─── Legacy Product Delete / Inventory Update ────────────────

    async def _handle_product_delete(self, store_id: int, payload: dict):
        pid = str(payload.get("id", ""))
        stmt = select(Product).where(
            Product.platform_product_id == pid,
            Product.store_id == store_id,
        )
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            product.status = "archived"
            await self.db.flush()

    async def _handle_inventory_update(self, store_id: int, payload: dict):
        """Update variant stock from inventory webhook."""
        inventory_item_id = str(payload.get("inventory_item_id", ""))
        available = payload.get("available")

        stmt = (
            select(Variant)
            .join(Product)
            .where(Product.store_id == store_id)
            .where(Variant.platform_variant_id == inventory_item_id)
        )
        result = await self.db.execute(stmt)
        variant = result.scalar_one_or_none()

        if variant and available is not None:
            variant.inventory_quantity = available
            await self.db.flush()
            await self._check_and_alert_low_stock(variant)

    # ─── Low Stock Logic ─────────────────────────────────────────

    async def _check_and_alert_low_stock(self, variant: Variant):
        """If stock below threshold, create/update alert."""
        threshold = variant.low_stock_threshold or self.settings.LOW_STOCK_THRESHOLD

        if variant.inventory_quantity <= threshold:
            stmt = select(LowStockAlert).where(
                LowStockAlert.variant_id == variant.id,
                LowStockAlert.is_resolved == False,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                product = variant.product
                alert = LowStockAlert(
                    store_id=product.store_id,
                    variant_id=variant.id,
                    product_title=product.title,
                    variant_title=variant.title,
                    sku=variant.sku,
                    current_stock=variant.inventory_quantity,
                    threshold=threshold,
                )
                self.db.add(alert)
                logger.warning(
                    f"LOW STOCK: {product.title} / {variant.title} "
                    f"— {variant.inventory_quantity} left (threshold: {threshold})"
                )
            else:
                existing.current_stock = variant.inventory_quantity
        else:
            stmt = select(LowStockAlert).where(
                LowStockAlert.variant_id == variant.id,
                LowStockAlert.is_resolved == False,
            )
            result = await self.db.execute(stmt)
            for alert in result.scalars().all():
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)

    async def _count_active_low_stock(self, store_id: int) -> int:
        stmt = select(func.count(LowStockAlert.id)).where(
            LowStockAlert.store_id == store_id,
            LowStockAlert.is_resolved == False,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    # ─── Stats ──────────────────────────────────────────────────

    async def get_store_stats(self, store_id: int) -> dict:
        store_result = await self.db.execute(select(Store).where(Store.id == store_id))
        store = store_result.scalar_one_or_none()
        if not store:
            return {"error": "Store not found"}

        prod_count = (await self.db.execute(
            select(func.count(Product.id)).where(Product.store_id == store_id)
        )).scalar() or 0

        order_count = (await self.db.execute(
            select(func.count(Order.id)).where(Order.store_id == store_id)
        )).scalar() or 0

        low_count = await self._count_active_low_stock(store_id)

        return {
            "store": store.name or store.platform_store_id or store.shop_domain,
            "platform": store.platform,
            "total_products": prod_count,
            "total_orders": order_count,
            "last_sync": store.updated_at,
            "low_stock_count": low_count,
        }
