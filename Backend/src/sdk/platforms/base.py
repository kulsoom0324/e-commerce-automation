# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / base.py
#
# PURPOSE: Abstract Platform Connector — sabhi e-commerce platforms
#          (Shopify, WooCommerce, Amazon, Daraz, etc.) is interface
#          ko implement karte hain. Har connector = ek class.
#
# USED BY: inventory_sync handler, backend API, ALL agents
# ═══════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ─── Data Transfer Objects (Platform-Agnostic) ────────────────
# Ye universal format hai — har connector platform-specific data
# ko inme convert karega. Agents sirf inhe dekhte hain.

@dataclass
class ProductData:
    platform_product_id: str
    title: str
    description: str = ""
    vendor: str = ""
    product_type: str = ""
    status: str = "active"
    image_url: str = ""
    variants: list = field(default_factory=list)  # list[VariantData]
    extra_data: dict = field(default_factory=dict)


@dataclass
class VariantData:
    platform_variant_id: str
    title: str = ""
    sku: str = ""
    price: float = 0.0
    compare_at_price: Optional[float] = None
    inventory_quantity: int = 0
    extra_data: dict = field(default_factory=dict)


@dataclass
class OrderData:
    platform_order_id: str
    order_number: str
    customer_email: str = ""
    total_price: float = 0.0
    currency: str = "USD"
    financial_status: str = "pending"
    fulfillment_status: Optional[str] = None
    ordered_at: Optional[datetime] = None
    items: list = field(default_factory=list)  # list[OrderItemData]
    extra_data: dict = field(default_factory=dict)


@dataclass
class OrderItemData:
    platform_variant_id: Optional[str] = None
    quantity: int = 1
    price: float = 0.0
    extra_data: dict = field(default_factory=dict)


@dataclass
class InventoryData:
    platform_variant_id: str
    quantity: int = 0
    extra_data: dict = field(default_factory=dict)


@dataclass
class CategoryData:
    platform_category_id: str
    name: str
    parent_id: Optional[str] = None
    extra_data: dict = field(default_factory=dict)


@dataclass
class PlatformAuth:
    """Authentication credentials for any platform.

    Har platform ka apna auth pattern hota hai:
    - Shopify:       access_token (OAuth 2.0, permanent)
    - WooCommerce:   api_key + api_secret (Basic Auth)
    - Amazon SP-API: access_token + refresh_token (OAuth 2.0, 1hr)
    - Daraz:         access_token + refresh_token (OAuth 2.0, 30d)
    """
    platform: str
    store_id: int
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: Optional[datetime] = None
    api_key: str = ""
    api_secret: str = ""
    store_url: str = ""          # For self-hosted (WooCommerce, etc.)
    extra: dict = field(default_factory=dict)


# ─── PlatformConnector (Abstract Base Class) ──────────────────
# Har platform ka connector isko extend karega.
# Naya platform add karna = ek class likho + PlatformRegistry mein register.

class PlatformConnector(ABC):
    """Abstract interface for all e-commerce platform connectors.

    Har connector:
    - platform = "shopify" / "woocommerce" / "amazon" / "daraz" / etc.
    - Implement karega fetch_products, fetch_orders, verify_credentials
    - Platform-specific API calls → normalize to ProductData/OrderData
    """

    platform: str = ""

    # ─── Required: Auth ────────────────────────────────────────

    @abstractmethod
    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        """Check if credentials are valid.
        Shopify: Shop.current() call
        WooCommerce: GET /wc/v3/orders (1 record)
        Amazon: getServiceStatus()
        Daraz: /auth/token/refresh
        """
        pass

    # ─── Required: Products ────────────────────────────────────

    @abstractmethod
    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        """Fetch ALL products from platform → normalized ProductData list.
        Handles pagination internally.
        """
        pass

    # ─── Required: Orders ──────────────────────────────────────

    @abstractmethod
    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        """Fetch orders from platform → normalized OrderData list.
        params: since_days, status, etc.
        """
        pass

    # ─── Optional: Inventory ───────────────────────────────────

    async def fetch_inventory(self, auth: PlatformAuth, params: dict = None) -> list[InventoryData]:
        """Fetch current inventory levels.
        Default: extract from products (most platforms include stock).
        """
        return []

    # ─── Optional: Categories ──────────────────────────────────

    async def fetch_categories(self, auth: PlatformAuth) -> list[CategoryData]:
        """Fetch product categories/taxonomy."""
        return []

    # ─── Optional: Webhooks ────────────────────────────────────

    async def register_webhook(self, auth: PlatformAuth, topic: str, callback_url: str) -> Optional[str]:
        """Register a webhook for real-time updates.
        Returns webhook ID or None if not supported.
        """
        return None

    async def unregister_webhook(self, auth: PlatformAuth, webhook_id: str) -> bool:
        """Remove a webhook."""
        return False

    # ─── Optional: Rate Limiting ───────────────────────────────

    async def get_rate_limit_info(self, auth: PlatformAuth) -> dict:
        """Return current rate limit status."""
        return {}


# ─── PlatformRegistry ────────────────────────────────────────
# Connectors ka registry. Naya connector add karo:
#   PlatformRegistry.register("shopify", ShopifyConnector)
# Phir use karo:
#   connector = PlatformRegistry.get_connector("shopify")

class PlatformRegistry:
    _connectors: dict[str, type[PlatformConnector]] = {}

    @classmethod
    def register(cls, platform_name: str, connector_class: type[PlatformConnector]):
        """Register a new platform connector."""
        cls._connectors[platform_name] = connector_class

    @classmethod
    def get_connector(cls, platform_name: str) -> PlatformConnector:
        """Get an instance of the connector for a platform."""
        if platform_name not in cls._connectors:
            raise ValueError(
                f"Unknown platform: '{platform_name}'. "
                f"Available: {list(cls._connectors.keys())}"
            )
        return cls._connectors[platform_name]()

    @classmethod
    def list_platforms(cls) -> list[str]:
        """List all registered platforms."""
        return list(cls._connectors.keys())

    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """Check if a platform is supported."""
        return platform_name in cls._connectors
