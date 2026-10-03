# ═══════════════════════════════════════════════════════════════
# fte_sdk / oauth / providers.py
#
# PURPOSE: OAuth provider configurations — authorize URL, token URL,
#          scopes, client IDs. Har platform ka config yahan hai.
#
# USED BY: backend OAuth routes, platform connectors
# ═══════════════════════════════════════════════════════════════

from dataclasses import dataclass
from typing import Optional
from src.sdk.config import get_settings


@dataclass
class OAuthProviderConfig:
    """Configuration for an OAuth provider.

    Har platform ke liye alag config — client ID, secret, scopes, URLs.
    Settings fte_sdk/config.py se aate hain (jo .env file se padhte hain).
    """
    platform: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    redirect_uri: str = ""
    extra_params: dict = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


class OAuthProviderRegistry:
    """Registry of OAuth provider configs.
    Settings directly .env se aati hain — no hardcoded secrets.
    """

    @staticmethod
    def get_config(platform: str) -> OAuthProviderConfig:
        """Get OAuth config for a platform.
        Reads settings from fte_sdk config (which reads from .env).
        """
        s = get_settings()

        configs = {
            "shopify": OAuthProviderConfig(
                platform="shopify",
                client_id=s.SHOPIFY_API_KEY or "",
                client_secret=s.SHOPIFY_API_SECRET or "",
                authorize_url="https://{shop_domain}/admin/oauth/authorize",
                token_url="https://{shop_domain}/admin/oauth/access_token",
                scopes=["read_products", "read_orders", "read_inventory",
                        "write_webhooks"],
                redirect_uri=s.SHOPIFY_REDIRECT_URI or "",
            ),
            # ─── WooCommerce ────────────────────────────────────
            # WooCommerce uses Basic Auth (not OAuth). Consumer key
            # + consumer secret are passed directly via headers.
            # No redirect flow — user provides keys during setup.
            "woocommerce": OAuthProviderConfig(
                platform="woocommerce",
                client_id="",    # consumer_key user se aata hai at connect time
                client_secret="",  # consumer_secret user se aata hai
                authorize_url="",
                token_url="",
                scopes=["read"],
                redirect_uri="",
            ),
            # ─── BigCommerce ────────────────────────────────────
            "bigcommerce": OAuthProviderConfig(
                platform="bigcommerce",
                client_id=s.BIGCOMMERCE_CLIENT_ID or "",
                client_secret=s.BIGCOMMERCE_CLIENT_SECRET or "",
                authorize_url="https://login.bigcommerce.com/oauth2/authorize",
                token_url="https://login.bigcommerce.com/oauth2/token",
                scopes=["store_v2_products_read_products",
                        "store_v2_orders_read_orders"],
                redirect_uri=s.BIGCOMMERCE_REDIRECT_URI or "",
                extra_params={"context": ""},  # set per-request
            ),
            # ─── Amazon SP-API ──────────────────────────────────
            "amazon": OAuthProviderConfig(
                platform="amazon",
                client_id=s.AMAZON_CLIENT_ID or "",
                client_secret=s.AMAZON_CLIENT_SECRET or "",
                authorize_url="https://sellercentral.amazon.com/apps/authorize",
                token_url="https://api.amazon.com/auth/o2/token",
                scopes=["sellingapi"],
                redirect_uri=s.AMAZON_REDIRECT_URI or "",
            ),
            # ─── Daraz / Lazada ─────────────────────────────────
            "daraz": OAuthProviderConfig(
                platform="daraz",
                client_id=s.DARAZ_APP_KEY or "",
                client_secret=s.DARAZ_APP_SECRET or "",
                authorize_url="https://api.daraz.com/oauth/authorize",
                token_url="https://api.daraz.com/oauth/token",
                scopes=["seller_product_read", "seller_order_read"],
                redirect_uri=s.DARAZ_REDIRECT_URI or "",
            ),
        }

        if platform not in configs:
            raise ValueError(
                f"Unknown OAuth provider: '{platform}'. "
                f"Available: {list(configs.keys())}"
            )
        return configs[platform]
