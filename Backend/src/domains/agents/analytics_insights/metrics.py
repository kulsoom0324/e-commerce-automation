# ═══════════════════════════════════════════════════════════════
# agents / analytics_insights / metrics.py
#
# PURPOSE: Metric definitions catalog & seed functions for Analytics Agent.
# ═══════════════════════════════════════════════════════════════

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.sdk.models.analytics import MetricDefinition


METRIC_SPECS: dict[str, dict] = {
    "posts_published": {
        "description": "Total social media posts successfully published",
        "refresh_interval": "daily",
        "agent_source": "content_scheduling",
        "sql_query": "SELECT count(*) FROM scheduled_posts WHERE status='published'",
    },
    "posts_per_week": {
        "description": "Average social posts published per week",
        "refresh_interval": "weekly",
        "agent_source": "content_scheduling",
        "sql_query": "SELECT count(*)/4.0 FROM scheduled_posts WHERE status='published'",
    },
    "reply_accuracy": {
        "description": "Ratio of approved/posted comment replies to total comments",
        "refresh_interval": "daily",
        "agent_source": "comment_engagement",
        "sql_query": "SELECT count(r.id)*100.0/NULLIF(count(c.id),0) FROM comments c LEFT JOIN replies r ON r.comment_id=c.id WHERE r.status='posted'",
    },
    "replies_sent": {
        "description": "Total automated/manual replies sent on social platforms",
        "refresh_interval": "daily",
        "agent_source": "comment_engagement",
        "sql_query": "SELECT count(*) FROM replies WHERE status='posted'",
    },
    "escalation_rate": {
        "description": "Percentage of comments escalated to human review",
        "refresh_interval": "daily",
        "agent_source": "comment_engagement",
        "sql_query": "SELECT count(*)*100.0/NULLIF((SELECT count(*) FROM comments),0) FROM comments WHERE is_escalated=true",
    },
    "revenue_total": {
        "description": "Total store gross revenue from synced orders",
        "refresh_interval": "daily",
        "agent_source": "inventory_sync",
        "sql_query": "SELECT sum(total_price) FROM orders WHERE financial_status='paid'",
    },
    "orders_count": {
        "description": "Total number of orders ingested",
        "refresh_interval": "daily",
        "agent_source": "inventory_sync",
        "sql_query": "SELECT count(*) FROM orders",
    },
    "low_stock_open": {
        "description": "Active unresolved low stock alerts",
        "refresh_interval": "daily",
        "agent_source": "inventory_sync",
        "sql_query": "SELECT count(*) FROM low_stock_alerts WHERE is_resolved=false",
    },
    "handoffs_count": {
        "description": "Total customer support conversations escalated to humans",
        "refresh_interval": "daily",
        "agent_source": "customer_support",
        "sql_query": "SELECT count(*) FROM handoff_logs",
    },
}


async def seed_default_metrics(db: AsyncSession) -> None:
    """Idempotently seed default metric definitions into the database."""
    for name, spec in METRIC_SPECS.items():
        res = await db.execute(
            select(MetricDefinition).where(MetricDefinition.name == name)
        )
        existing = res.scalar_one_or_none()
        if not existing:
            metric = MetricDefinition(
                name=name,
                description=spec["description"],
                sql_query=spec["sql_query"],
                refresh_interval=spec["refresh_interval"],
                agent_source=spec["agent_source"],
                is_active=True,
            )
            db.add(metric)
    await db.flush()
