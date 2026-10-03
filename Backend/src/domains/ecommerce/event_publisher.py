# ═══════════════════════════════════════════════════════════════
# src / domains / ecommerce / event_publisher.py
#
# PURPOSE: Typed event publisher helpers. Backend REST API
#          endpoints publish events through this → Redis →
#          agents consume them asynchronously.
# ═══════════════════════════════════════════════════════════════

from src.sdk.events import (
    Event, WebhookEvent, SyncRequestEvent
)
from src.sdk.event_bus import RedisEventBus


class EventPublisher:
    """Publishes typed events to Redis. Agents subscribe and process."""

    def __init__(self, bus: RedisEventBus):
        self.bus = bus

    def _dump(self, event: Event) -> dict:
        """Serialize event to JSON-safe dict (datetimes → ISO strings)."""
        return event.model_dump(mode="json")

    async def publish_webhook(self, shop_name: str, topic: str, payload: dict, store_id: int):
        """Forward webhook event to inventory_sync agent."""
        event = WebhookEvent(
            source="backend",
            target_agent="inventory_sync",
            payload={
                "shop_name": shop_name,
                "topic": topic,
                "data": payload,
                "store_id": store_id,
            },
        )
        await self.bus.publish("webhooks", self._dump(event))

    async def publish_sync_request(
        self, store_id: int, sync_type: str = "full", since_days: int = 30
    ):
        """Request sync from inventory_sync agent."""
        event = SyncRequestEvent(
            source="backend",
            target_agent="inventory_sync",
            payload={
                "store_id": store_id,
                "sync_type": sync_type,
                "since_days": since_days,
            },
        )
        await self.bus.publish("sync", self._dump(event))

    async def publish_event(self, channel: str, event: Event):
        """Publish a generic Event to any channel."""
        await self.bus.publish(channel, self._dump(event))
