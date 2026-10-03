# ═══════════════════════════════════════════════════════════════
# fte_sdk / platforms / amazon.py
#
# PURPOSE: Amazon SP-API (Selling Partner API) connector.
#          Fetches products + orders from Amazon Seller Central.
#          OAuth 2.0 with 1-hour tokens + refresh.
#
# NOTE: Amazon SP-API is complex — this is the READ-ONLY baseline.
#       Full implementation requires IAM roles + SP-API registration.
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

AMAZON_API_ENDPOINTS = {
    "NA": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}

# Marketplace IDs
AMAZON_MARKETPLACES = {
    "US": "ATVPDKIKX0DER",
    "CA": "A2EUQ1WTGCTBG2",
    "MX": "A1AM78C64UM0Y8",
    "UK": "A1F83G8C2ARO7P",
    "DE": "A1PA6795UKMFR9",
    "FR": "A13V1IB3VIYZZH",
    "IT": "APJ6JRA9NG5V4",
    "ES": "A1RKKUPIHCS9H3",
    "JP": "A1VC38T7YXB528",
    "AU": "A39IBJ37TRP1C6",
    "AE": "A2VIGQ35RCS4UG",
    "SA": "A17E79C6D8DWNP",
    "SG": "A19VAU5U5O7RUS",
    "BR": "A2Q3Y263D00KWC",
}


class AmazonConnector(PlatformConnector):
    """Amazon Selling Partner API connector.

    Auth: OAuth 2.0 (refresh_token, client_id, client_secret)
    Token: 1 hour — auto-refresh via refresh_token
    API: REST (raw httpx, no SDK)
    Webhooks: NOT SUPPORTED — polling only
    Note: Full SP-API requires IAM role + STS. This implements
          the simplified OAuth flow for public apps.
    """

    platform = "amazon"

    def _get_marketplace_id(self, auth: PlatformAuth) -> str:
        """Get marketplace ID from auth extra or default to US."""
        return auth.extra.get("marketplace_id", AMAZON_MARKETPLACES.get("US", "ATVPDKIKX0DER"))

    def _get_endpoint(self, auth: PlatformAuth) -> str:
        """Get API endpoint based on marketplace region."""
        region = auth.extra.get("region", "NA")
        return AMAZON_API_ENDPOINTS.get(region, AMAZON_API_ENDPOINTS["NA"])

    # ─── Token Management ───────────────────────────────────────

    async def _refresh_access_token(self, auth: PlatformAuth) -> Optional[str]:
        """Refresh the 1-hour access token using refresh_token."""
        if not auth.refresh_token:
            logger.error("Amazon refresh_token is required but missing")
            return None

        from src.sdk.config import get_settings
        s = get_settings()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.amazon.com/auth/o2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": auth.refresh_token,
                        "client_id": s.AMAZON_CLIENT_ID,
                        "client_secret": s.AMAZON_CLIENT_SECRET,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    auth.access_token = data.get("access_token", "")
                    # expires_in is in seconds (usually 3600)
                    if "expires_in" in data:
                        auth.token_expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=data["expires_in"]
                        )
                    return auth.access_token
                else:
                    logger.error(f"Amazon token refresh failed: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Amazon token refresh error: {e}")
            return None

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        try:
            if not auth.access_token:
                await self._refresh_access_token(auth)

            endpoint = self._get_endpoint(auth)
            headers = self._build_headers(auth)

            async with httpx.AsyncClient() as client:
                # Try marketplace participant status
                response = await client.get(
                    f"{endpoint}/sell/accounts/v1",
                    headers=headers,
                )
                return response.status_code in (200, 403)  # 403 = valid auth, insufficient scope
        except Exception as e:
            logger.warning(f"Amazon credential check failed: {e}")
            return False

    def _build_headers(self, auth: PlatformAuth) -> dict:
        """Build standard SP-API headers."""
        return {
            "x-amz-access-token": auth.access_token,
            "Content-Type": "application/json",
            "User-Agent": "FTE-Agent/1.0",
        }

    # ─── fetch_products ─────────────────────────────────────────
    # Amazon SP-API doesn't have a simple "list my products" endpoint
    # for seller catalogs. We use the Catalog Items API (v2022-04-01)
    # with search or list marketplace items.

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        logger.info("Amazon catalog item retrieval requires specific ASINs or SKUs.")
        logger.info("Implementing via Inventory + Catalog search.")
        return []  # Implement when we have specific ASIN/SKU list

    # ─── fetch_orders ───────────────────────────────────────────

    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        params = params or {}
        since_days = params.get("since_days", 30)

        if not auth.access_token:
            await self._refresh_access_token(auth)
        if not auth.access_token:
            logger.error("Cannot fetch Amazon orders: no access token")
            return []

        created_after = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        marketplace_id = self._get_marketplace_id(auth)
        endpoint = self._get_endpoint(auth)
        headers = self._build_headers(auth)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{endpoint}/orders/v0/orders",
                    headers=headers,
                    params={
                        "MarketplaceIds": marketplace_id,
                        "CreatedAfter": created_after,
                        "MaxResultsPerPage": 100,
                    },
                )
                if response.status_code != 200:
                    logger.error(f"Amazon orders fetch failed: {response.text}")
                    return []

                data = response.json()
                orders = data.get("payload", {}).get("Orders", []) if data.get("payload") else []
                result = []

                for o in orders:
                    # Fetch order items for each order
                    order_items = await self._fetch_order_items(
                        client, endpoint, headers, o.get("AmazonOrderId", "")
                    )
                    result.append(self._order_to_data(o, order_items))

                # Handle pagination
                next_token = data.get("payload", {}).get("NextToken") if data.get("payload") else None
                while next_token:
                    response = await client.get(
                        f"{endpoint}/orders/v0/orders",
                        headers=headers,
                        params={"NextToken": next_token},
                    )
                    if response.status_code != 200:
                        break
                    data = response.json()
                    page_orders = data.get("payload", {}).get("Orders", [])
                    for o in page_orders:
                        order_items = await self._fetch_order_items(
                            client, endpoint, headers, o.get("AmazonOrderId", "")
                        )
                        result.append(self._order_to_data(o, order_items))
                    next_token = data.get("payload", {}).get("NextToken")

                return result

            except Exception as e:
                logger.error(f"Amazon orders fetch error: {e}")
                return []

    async def _fetch_order_items(self, client: httpx.AsyncClient, endpoint: str, headers: dict, order_id: str) -> list:
        """Fetch items for a single Amazon order."""
        try:
            response = await client.get(
                f"{endpoint}/orders/v0/orders/{order_id}/orderItems",
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("payload", {}).get("OrderItems", []) if data.get("payload") else []
        except Exception as e:
            logger.warning(f"Failed to fetch Amazon order items for {order_id}: {e}")
        return []

    # ─── Normalization: Order → OrderData ───────────────────────

    @staticmethod
    def _order_to_data(o: dict, order_items: list = None) -> OrderData:
        line_items = []
        if order_items:
            for item in order_items:
                line_items.append(OrderItemData(
                    platform_variant_id=item.get("SellerSKU", ""),
                    quantity=int(item.get("QuantityOrdered", 1)),
                    price=float(item.get("ItemPrice", {}).get("Amount", 0) or 0) if item.get("ItemPrice") else 0,
                ))

        ordered_at = o.get("PurchaseDate")
        if ordered_at and isinstance(ordered_at, str):
            try:
                ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ordered_at = None

        return OrderData(
            platform_order_id=o.get("AmazonOrderId", ""),
            order_number=o.get("AmazonOrderId", ""),
            customer_email=o.get("BuyerEmail", ""),
            total_price=float(o.get("OrderTotal", {}).get("Amount", 0) or 0) if o.get("OrderTotal") else 0,
            currency=o.get("OrderTotal", {}).get("CurrencyCode", "USD") if o.get("OrderTotal") else "USD",
            financial_status=o.get("OrderStatus", "pending"),
            fulfillment_status=o.get("FulfillmentChannel", ""),
            ordered_at=ordered_at,
            items=line_items,
        )
