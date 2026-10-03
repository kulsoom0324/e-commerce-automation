# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / daraz.py
#
# PURPOSE: Daraz / Lazada connector — implements PlatformConnector.
#          REST API via OAuth 2.0 (30-day tokens + refresh).
#          Covers: Daraz (PK, BD, LK, NP), Lazada (SG, MY, TH, PH, ID, VN)
#
# NOTE: Daraz API uses app_key + app_secret for auth.
#       Region is encoded in the API endpoint URL.
#
# USED BY: PlatformRegistry, inventory_sync handler
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import hashlib
import hmac

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

# Daraz/Lazada API endpoints per region
DARAZ_ENDPOINTS = {
    "pk": "https://api.daraz.pk/rest",       # Pakistan
    "bd": "https://api.daraz.com.bd/rest",   # Bangladesh
    "lk": "https://api.daraz.lk/rest",       # Sri Lanka
    "np": "https://api.daraz.com.np/rest",   # Nepal
    "sg": "https://api.lazada.sg/rest",      # Singapore (Lazada)
    "my": "https://api.lazada.com.my/rest",  # Malaysia (Lazada)
    "th": "https://api.lazada.co.th/rest",   # Thailand (Lazada)
    "ph": "https://api.lazada.com.ph/rest",  # Philippines (Lazada)
    "id": "https://api.lazada.co.id/rest",   # Indonesia (Lazada)
    "vn": "https://api.lazada.vn/rest",      # Vietnam (Lazada)
}


class DarazConnector(PlatformConnector):
    """Daraz / Lazada platform connector.

    Auth: OAuth 2.0 (app_key + app_secret for token, refresh_token for refresh)
    Token: 30 days — auto-refresh via refresh_token
    API: REST (raw httpx)
    Webhooks: NOT SUPPORTED — polling only
    Rate Limit: ~100 requests per minute

    ⚠️ Note: Daraz API requires certain API permissions to be
    enabled in the seller center. Some endpoints may be restricted
    based on seller account type.
    """

    platform = "daraz"

    def _get_region(self, auth: PlatformAuth) -> str:
        """Get region code from auth extra or default to 'pk'."""
        return auth.extra.get("region", "pk")

    def _get_endpoint(self, auth: PlatformAuth) -> str:
        """Get API endpoint for the configured region."""
        region = self._get_region(auth)
        return DARAZ_ENDPOINTS.get(region, DARAZ_ENDPOINTS["pk"])

    # ─── Auth Helpers ───────────────────────────────────────────

    def _sign_request(self, auth: PlatformAuth, params: dict) -> dict:
        """Daraz API requires HMAC-SHA256 signature for every request.

        Signature = HMAC-SHA256(app_secret, sorted params string)
        """
        if not auth.api_secret:
            logger.error("Daraz requires api_secret (app_secret)")
            return params

        # Add timestamp and app_key
        params["app_key"] = auth.api_key
        params["timestamp"] = str(int(datetime.now().timestamp() * 1000))

        # Sort params alphabetically and create sign string
        sorted_keys = sorted(params.keys())
        sign_string = ""
        for key in sorted_keys:
            sign_string += f"{key}{params[key]}"

        # Generate signature
        signature = hmac.new(
            auth.api_secret.encode(),
            sign_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        params["sign"] = signature
        return params

    # ─── Token Management ───────────────────────────────────────

    async def _refresh_access_token(self, auth: PlatformAuth) -> Optional[str]:
        """Refresh 30-day token."""
        if not auth.refresh_token:
            logger.error("Daraz refresh_token required but missing")
            return None

        endpoint = self._get_endpoint(auth)
        params = {
            "method": "refresh_access_token",
            "refresh_token": auth.refresh_token,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=self._sign_request(auth, params))
                if response.status_code == 200:
                    data = response.json().get("data", {}) or response.json()
                    if data.get("access_token"):
                        auth.access_token = data["access_token"]
                        if data.get("refresh_token"):
                            auth.refresh_token = data["refresh_token"]
                        if data.get("expires_in"):
                            auth.token_expires_at = datetime.now(timezone.utc) + timedelta(
                                seconds=int(data["expires_in"])
                            )
                        return auth.access_token
                logger.error(f"Daraz token refresh failed: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Daraz token refresh error: {e}")
            return None

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        try:
            endpoint = self._get_endpoint(auth)
            params = {
                "method": "get_seller",
                "access_token": auth.access_token,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=self._sign_request(auth, params))
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Daraz credential check failed: {e}")
            return False

    # ─── fetch_products ─────────────────────────────────────────
    # Daraz product API returns paginated results.

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        endpoint = self._get_endpoint(auth)
        all_products = []
        offset = 0
        limit = 100

        while True:
            api_params = {
                "method": "get_products",
                "access_token": auth.access_token,
                "offset": str(offset),
                "limit": str(limit),
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        params=self._sign_request(auth, api_params),
                    )
                    if response.status_code != 200:
                        break

                    data = response.json()
                    products = data.get("data", {}).get("products", []) if data.get("data") else data.get("products", [])
                    if not products:
                        break

                    for p in products:
                        all_products.append(self._product_to_data(p))

                    offset += limit
                    if len(products) < limit:
                        break

            except Exception as e:
                logger.error(f"Daraz products fetch error: {e}")
                break

        return all_products

    # ─── fetch_orders ───────────────────────────────────────────
    # Daraz order API with date range and pagination.

    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        params = params or {}
        since_days = params.get("since_days", 30)

        created_after = datetime.now(timezone.utc) - timedelta(days=since_days)
        created_after_str = created_after.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        endpoint = self._get_endpoint(auth)
        all_orders = []
        offset = 0
        limit = 100

        while True:
            api_params = {
                "method": "get_orders",
                "access_token": auth.access_token,
                "created_after": created_after_str,
                "offset": str(offset),
                "limit": str(limit),
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        params=self._sign_request(auth, api_params),
                    )
                    if response.status_code != 200:
                        break

                    data = response.json()
                    orders = data.get("data", {}).get("orders", []) if data.get("data") else data.get("orders", [])
                    if not orders:
                        break

                    for o in orders:
                        all_orders.append(self._order_to_data(o))

                    offset += limit
                    if len(orders) < limit:
                        break

            except Exception as e:
                logger.error(f"Daraz orders fetch error: {e}")
                break

        return all_orders

    # ─── Normalization: Product → ProductData ───────────────────

    @staticmethod
    def _product_to_data(p: dict) -> ProductData:
        # Daraz products can have multiple SKUs (variations)
        skus = p.get("skus") or []
        variants = []

        for s in skus:
            variants.append(VariantData(
                platform_variant_id=str(s.get("SkuId", "") or s.get("sku_id", "")),
                title=s.get("SkuCode", "") or s.get("sku_code", ""),
                sku=s.get("SellerSku", "") or s.get("seller_sku", ""),
                price=float(s.get("price", 0) or 0),
                compare_at_price=float(s.get("special_price", 0)) if s.get("special_price") else None,
                inventory_quantity=int(s.get("quantity", 0) or 0),
            ))

        # If no SKUs, create one from the product
        if not variants:
            variants.append(VariantData(
                platform_variant_id=str(p.get("item_id", "") or p.get("item_id", "")),
                title=p.get("name", "") or p.get("item_name", ""),
                sku=p.get("item_sku", ""),
                price=float(p.get("price", 0) or 0),
                compare_at_price=float(p.get("special_price", 0)) if p.get("special_price") else None,
                inventory_quantity=int(p.get("quantity", 0) or 0),
            ))

        image_url = ""
        images = p.get("images") or []
        if images:
            if isinstance(images[0], dict):
                image_url = images[0].get("url", "")
            else:
                image_url = str(images[0])

        return ProductData(
            platform_product_id=str(p.get("item_id", "") or p.get("item_id", "")),
            title=p.get("name", "") or p.get("item_name", ""),
            description=p.get("description", "") or p.get("short_description", ""),
            vendor="",
            product_type=p.get("category_name", "") or p.get("category_name", ""),
            status="active" if p.get("status") in ("active", "publish", "published") else "inactive",
            image_url=image_url,
            variants=variants,
        )

    # ─── Normalization: Order → OrderData ───────────────────────

    @staticmethod
    def _order_to_data(o: dict) -> OrderData:
        line_items = []
        order_items = o.get("order_items", []) or o.get("items", [])
        if order_items:
            for item in order_items:
                line_items.append(OrderItemData(
                    platform_variant_id=str(item.get("sku_id", "") or item.get("SkuId", "")),
                    quantity=int(item.get("quantity", 1) or 1),
                    price=float(item.get("unit_price", 0) or 0),
                ))

        ordered_at = o.get("created_at") or o.get("order_created_at") or o.get("gmt_create")
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    ordered_at = datetime.strptime(ordered_at, "%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    ordered_at = None

        return OrderData(
            platform_order_id=str(o.get("order_id", "") or o.get("OrderId", "")),
            order_number=str(o.get("order_number", "") or o.get("order_id", "")),
            customer_email=o.get("customer_email", "") or "",
            total_price=float(o.get("total_amount", 0) or o.get("price", 0) or 0),
            currency=o.get("currency", "PKR"),
            financial_status=o.get("status", "pending"),
            fulfillment_status="shipped" if o.get("status") in ("shipped", "delivered") else "pending",
            ordered_at=ordered_at,
            items=line_items,
        )
