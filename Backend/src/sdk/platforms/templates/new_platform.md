# How to Add a New E-Commerce Platform Connector

## 1. Create the Connector Class

Create `fte_sdk/platforms/your_platform.py`:

```python
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fte_sdk.platforms.base import (
    PlatformConnector, PlatformAuth,
    ProductData, VariantData, OrderData, OrderItemData,
)

logger = logging.getLogger(__name__)


class YourPlatformConnector(PlatformConnector):
    """YourPlatform connector.

    Auth: OAuth 2.0 / Basic Auth / API Key
    Token: Permanent / 30-day / 1-hour
    API: REST / GraphQL
    Webhooks: Supported / Not Supported
    """

    platform = "your_platform"  # Unique name, lowercase

    async def verify_credentials(self, auth: PlatformAuth) -> bool:
        """Check if credentials are valid."""
        # ... implement ...
        pass

    async def fetch_products(self, auth: PlatformAuth, params: dict = None) -> list[ProductData]:
        """Fetch ALL products → normalize to ProductData."""
        # ... implement ...
        pass

    async def fetch_orders(self, auth: PlatformAuth, params: dict = None) -> list[OrderData]:
        """Fetch orders → normalize to OrderData."""
        # ... implement ...
        pass
```

## 2. Register in `fte_sdk/platforms/__init__.py`

```python
from fte_sdk.platforms.your_platform import YourPlatformConnector
PlatformRegistry.register("your_platform", YourPlatformConnector)
```

## 3. Add OAuth Config (if OAuth-based)

In `fte_sdk/oauth/providers.py`:

```python
"your_platform": OAuthProviderConfig(
    platform="your_platform",
    client_id=s.YOUR_PLATFORM_CLIENT_ID or "",
    client_secret=s.YOUR_PLATFORM_CLIENT_SECRET or "",
    authorize_url="...",
    token_url="...",
    scopes=["..."],
    redirect_uri=s.YOUR_PLATFORM_REDIRECT_URI or "",
),
```

## 4. Add Config Fields

In `fte_sdk/config.py`:

```python
YOUR_PLATFORM_CLIENT_ID: str = ""
YOUR_PLATFORM_CLIENT_SECRET: str = ""
YOUR_PLATFORM_REDIRECT_URI: str = "..."
```

## 5. Add OAuth Callback Route (if OAuth-based)

In `backend/app/oauth_routes.py` — add handler for the new platform.

## 6. Add Tests

In `tests/test_platforms.py` — add a test class with mocked HTTP responses.

---

## Checklist

- [ ] Connector class created with all abstract methods
- [ ] `verify_credentials()` implemented
- [ ] `fetch_products()` with pagination
- [ ] `fetch_orders()` with date filtering
- [ ] Product → ProductData normalization
- [ ] Order → OrderData normalization
- [ ] Registered in PlatformRegistry
- [ ] OAuth provider config added
- [ ] .env fields added to config
- [ ] OAuth callback route added
- [ ] Tests written with mocked HTTP
