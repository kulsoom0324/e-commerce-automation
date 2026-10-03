# ═══════════════════════════════════════════════════════════════
# fte_sdk / events.py
#
# PURPOSE: Standard event models for ALL inter-agent communication.
#          Event = base, specific events inherit from it.
#          Har agent in events ko publish/subscribe karta hai
#          through event_bus.py.
#
# USED BY: ALL — agents publish events, orchestrator routes them
# ═══════════════════════════════════════════════════════════════

from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


# ─── Event (Base) ─────────────────────────────────────────────
# Every event has: event_id (unique), event_type (routing key),
# source (which agent), target_agent (optional — direct routing),
# correlation_id (track multi-step workflows), payload (dict).

class Event(BaseModel):
    event_id: str = ""
    event_type: str
    source: str
    target_agent: str = ""           # "" = broadcast, "inventory_sync" = specific agent
    correlation_id: str = ""         # Track multi-step workflows across agents
    timestamp: datetime = None
    payload: dict = {}

    def __init__(self, **data):
        if not data.get("event_id"):
            data["event_id"] = str(uuid4())
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)


# ─── Specific Event Types ─────────────────────────────────────
# Har event type ek specific use-case cover karta hai.
# New event type add karna easy — just inherit Event.

class WebhookEvent(Event):
    """Shopify webhook → backend receives → forwards to inventory_sync via event bus.
       Payload: shop_name, topic, data (raw Shopify webhook body)"""
    event_type: str = "webhook.received"


class SyncRequestEvent(Event):
    """Manual / scheduled sync trigger → inventory_sync processes it.
       Payload: store_id, sync_type (full|products|orders), since_days"""
    event_type: str = "sync.requested"


class ContentRequestEvent(Event):
    """Content generation request → content_generation agent.
       Payload: product_id, platform, brand_voice_id, count"""
    event_type: str = "content.generation.requested"


class ContentApprovedEvent(Event):
    """Approved content → content_scheduling agent → schedule for publish.
       Payload: post_id, platform, scheduled_at, media_urls"""
    event_type: str = "content.approved"


class CommentEvent(Event):
    """New social media comment → comment_engagement agent → analyze + reply.
       Payload: comment_id, social_account_id, author, text, platform"""
    event_type: str = "comment.received"


class SupportTicketEvent(Event):
    """Customer support ticket → customer_support agent.
       Payload: conversation_id, customer_email, product_id, query"""
    event_type: str = "support.ticket.created"


class AnalyticsEvent(Event):
    """Periodic or triggered refresh → analytics_insights agent.
       Payload: metric_ids, period_start, period_end"""
    event_type: str = "analytics.refresh.requested"


class WorkflowEvent(Event):
    """Multi-step workflow step execution → collaboration_orchestrator.
       Payload: workflow_id, step_name, inputs, context"""
    event_type: str = "workflow.step.execute"


class HeartbeatEvent(Event):
    """Agent liveness check → orchestrator. Sent every 30s.
       Payload: agent_name, status, queue_depth"""
    event_type: str = "agent.heartbeat"


# ─── Content Generation Events (Agent 3 → Agent 2) ─────────────
# Triggered when new product arrives or user clicks "Generate Post".

class ContentGenerateEvent(Event):
    """Auto/content generation trigger → content_generation agent.
       Payload: product_id, platform, brand_voice_id, image_model, auto_approve"""
    event_type: str = "content.generate.requested"


class ContentRejectedEvent(Event):
    """Human rejected content → content_generation knows to regenerate.
       Payload: post_id, feedback, agent"""
    event_type: str = "content.rejected"


# ─── Content Publishing Events (Agent 2 → Analytics) ───────────

class PostPublishedEvent(Event):
    """Post published successfully on social platform.
       Payload: scheduled_post_id, platform, platform_post_id, published_at"""
    event_type: str = "post.published"


class PostPublishFailedEvent(Event):
    """Post publish failed permanently (retries exhausted).
       Payload: scheduled_post_id, platform, error, retry_count"""
    event_type: str = "post.publish.failed"
