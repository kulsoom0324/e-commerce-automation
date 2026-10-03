from src.domains.ecommerce.routes import router as routes_router
from src.domains.ecommerce.webhooks import router as webhooks_router
from src.domains.ecommerce.oauth import router as oauth_router

__all__ = ["routes_router", "webhooks_router", "oauth_router"]
