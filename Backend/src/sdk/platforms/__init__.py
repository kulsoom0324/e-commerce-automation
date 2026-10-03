# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / __init__.py
#
# PURPOSE: Auto-registers all platform connectors on import.
#          Naya connector add karo → yahan import karo → auto-register.
# ═══════════════════════════════════════════════════════════════

from src.sdk.platforms.base import (
    PlatformConnector,
    PlatformRegistry,
    PlatformAuth,
    ProductData,
    VariantData,
    OrderData,
    OrderItemData,
    InventoryData,
    CategoryData,
)

# ─── Auto-register all platform connectors ────────────────────
# Har naya connector yahan import karo, yeh auto-register ho jayega.

from src.sdk.platforms.shopify import ShopifyConnector
PlatformRegistry.register("shopify", ShopifyConnector)

from src.sdk.platforms.woo_commerce import WooCommerceConnector
PlatformRegistry.register("woocommerce", WooCommerceConnector)

from src.sdk.platforms.big_commerce import BigCommerceConnector
PlatformRegistry.register("bigcommerce", BigCommerceConnector)

from src.sdk.platforms.amazon import AmazonConnector
PlatformRegistry.register("amazon", AmazonConnector)

from src.sdk.platforms.daraz import DarazConnector
PlatformRegistry.register("daraz", DarazConnector)

__all__ = [
    "PlatformConnector",
    "PlatformRegistry",
    "PlatformAuth",
    "ProductData",
    "VariantData",
    "OrderData",
    "OrderItemData",
    "InventoryData",
    "CategoryData",
]
