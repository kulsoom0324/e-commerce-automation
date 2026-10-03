# ═══════════════════════════════════════════════════════════════
# fte_sdk / event_bus.py
#
# PURPOSE: Event Bus abstraction — agents iske through async
#          communication karte hain (publish/subscribe).
#          AbstractEventBus = interface, RedisEventBus = impl.
#
# USED BY: All 7 agents, backend, orchestrator
# DEPENDS ON: Redis (async), json
# ═══════════════════════════════════════════════════════════════

import json
from abc import ABC, abstractmethod
from typing import Callable, Awaitable
from redis.asyncio import Redis


# ─── AbstractEventBus (Interface) ─────────────────────────────
# Contract for any event bus. Redis abhi, RabbitMQ Phase 2 mein
# same interface implement karega — agents ko koi change nahi.

class AbstractEventBus(ABC):
    @abstractmethod
    async def connect(self):
        """Initialize connection to the message broker."""
        ...

    @abstractmethod
    async def publish(self, channel: str, event: dict):
        """Publish event dict (JSON) to a channel. All subscribers receive it."""
        ...

    @abstractmethod
    async def subscribe(self, channel: str, callback: Callable[[dict], Awaitable[None]]):
        """Subscribe to channel. callback runs async on each message.
        Runs in an infinite loop — start as asyncio.create_task()."""
        ...

    @abstractmethod
    async def disconnect(self):
        """Unsubscribe all channels and close broker connection."""
        ...


# ─── RedisEventBus (Redis Implementation) ─────────────────────
# Pub/Sub using Redis async client. Agents publish events to
# channels, other agents subscribe and get real-time updates.

class RedisEventBus(AbstractEventBus):
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Redis | None = None
        self._pubsub = None

    async def connect(self):
        """Connect to Redis using async client with decode_responses=True."""
        self._redis = Redis.from_url(self.redis_url, decode_responses=True)

    async def publish(self, channel: str, event: dict):
        """Serialize event to JSON and publish to Redis channel."""
        if not self._redis:
            raise ConnectionError("Redis not connected. Call connect() first.")
        await self._redis.publish(channel, json.dumps(event, default=str))
    async def subscribe(self, channel: str, callback: Callable[[dict], Awaitable[None]]):
        """Subscribe to a Redis channel. Runs callback on every message.
        Blocking — run this in a separate asyncio task."""
        if not self._pubsub:
            self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(channel)
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)

    async def disconnect(self):
        """Unsubscribe all channels and close Redis connection."""
        if self._pubsub:
            await self._pubsub.unsubscribe()
        if self._redis:
            await self._redis.close()
            self._redis = None
