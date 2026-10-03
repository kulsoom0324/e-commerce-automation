# ═══════════════════════════════════════════════════════════════
# agents / analytics_insights / handler.py
#
# PURPOSE: Business logic for Analytics & Insights Agent.
#          Aggregates metrics from shared DB tables across all agents.
# ═══════════════════════════════════════════════════════════════

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.analytics import MetricDefinition, ReportSnapshot, KPI
from src.sdk.models.base import Order, LowStockAlert, Store
from src.sdk.models.social import ScheduledPost, Comment, Reply
from src.sdk.models.support import HandoffLog
from src.sdk.events import Event
from src.sdk.llm.client import LLMClient

from src.domains.agents.analytics_insights.config import get_settings
from src.domains.agents.analytics_insights.metrics import seed_default_metrics

logger = logging.getLogger(__name__)


class AnalyticsInsightsHandler:
    """Computes cross-agent analytics and rolls up performance snapshots."""

    def __init__(self, db: AsyncSession, llm_client: Optional[LLMClient] = None):
        self.db = db
        self.settings = get_settings()
        self.llm = llm_client or LLMClient(api_key=self.settings.LLM_API_KEY)

    async def compute_metric(
        self,
        name: str,
        period_start: datetime,
        period_end: datetime,
        store_id: Optional[int] = None,
    ) -> float:
        """Compute a specific metric value for a given time period."""
        if name == "posts_published":
            q = select(func.count(ScheduledPost.id)).where(
                ScheduledPost.status == "published",
                ScheduledPost.published_at >= period_start,
                ScheduledPost.published_at <= period_end,
            )
            res = await self.db.execute(q)
            return float(res.scalar() or 0)

        elif name == "posts_per_week":
            # Total published divided by weeks in period (min 1 week)
            days = max(1, (period_end - period_start).days)
            weeks = max(1.0, days / 7.0)
            posts = await self.compute_metric("posts_published", period_start, period_end, store_id)
            return round(posts / weeks, 2)

        elif name == "replies_sent":
            q = select(func.count(Reply.id)).where(
                Reply.status == "posted",
                Reply.created_at >= period_start,
                Reply.created_at <= period_end,
            )
            res = await self.db.execute(q)
            return float(res.scalar() or 0)

        elif name == "reply_accuracy":
            tot_q = select(func.count(Comment.id)).where(
                Comment.created_at >= period_start,
                Comment.created_at <= period_end,
            )
            tot_comments = (await self.db.execute(tot_q)).scalar() or 0
            if tot_comments == 0:
                return 100.0
            replies = await self.compute_metric("replies_sent", period_start, period_end, store_id)
            return round(min(100.0, (replies / tot_comments) * 100.0), 2)

        elif name == "escalation_rate":
            tot_q = select(func.count(Comment.id)).where(
                Comment.created_at >= period_start,
                Comment.created_at <= period_end,
            )
            tot = (await self.db.execute(tot_q)).scalar() or 0
            if tot == 0:
                return 0.0
            esc_q = select(func.count(Comment.id)).where(
                Comment.is_escalated == True,
                Comment.created_at >= period_start,
                Comment.created_at <= period_end,
            )
            esc = (await self.db.execute(esc_q)).scalar() or 0
            return round((esc / tot) * 100.0, 2)

        elif name == "revenue_total":
            q = select(func.sum(Order.total_price)).where(
                Order.created_at >= period_start,
                Order.created_at <= period_end,
            )
            if store_id:
                q = q.where(Order.store_id == store_id)
            res = await self.db.execute(q)
            return float(res.scalar() or 0.0)

        elif name == "orders_count":
            q = select(func.count(Order.id)).where(
                Order.created_at >= period_start,
                Order.created_at <= period_end,
            )
            if store_id:
                q = q.where(Order.store_id == store_id)
            res = await self.db.execute(q)
            return float(res.scalar() or 0)

        elif name == "low_stock_open":
            q = select(func.count(LowStockAlert.id)).where(
                LowStockAlert.is_resolved == False,
            )
            res = await self.db.execute(q)
            return float(res.scalar() or 0)

        elif name == "handoffs_count":
            q = select(func.count(HandoffLog.id)).where(
                HandoffLog.created_at >= period_start,
                HandoffLog.created_at <= period_end,
            )
            res = await self.db.execute(q)
            return float(res.scalar() or 0)

        return 0.0

    async def run_rollup(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> dict:
        """Run rollup job: calculate metrics and persist ReportSnapshot records."""
        await seed_default_metrics(self.db)

        now = datetime.now(timezone.utc)
        p_end = period_end or now
        p_start = period_start or (p_end - timedelta(days=self.settings.AGGREGATION_WINDOW_DAYS))

        metrics_res = await self.db.execute(
            select(MetricDefinition).where(MetricDefinition.is_active == True)
        )
        metrics = metrics_res.scalars().all()

        snapshots_created = []
        for m in metrics:
            val = await self.compute_metric(m.name, p_start, p_end)
            snap = ReportSnapshot(
                metric_id=m.id,
                value=val,
                period_start=p_start,
                period_end=p_end,
            )
            self.db.add(snap)
            snapshots_created.append({"metric": m.name, "value": val})

        await self.db.flush()
        return {
            "status": "completed",
            "period_start": p_start,
            "period_end": p_end,
            "metrics_computed": len(snapshots_created),
            "snapshots": snapshots_created,
        }

    async def dashboard(
        self,
        store_id: Optional[int] = None,
        period_days: int = 30,
    ) -> dict:
        """Generate on-demand dashboard metrics with trend comparison."""
        now = datetime.now(timezone.utc)
        cur_start = now - timedelta(days=period_days)
        prior_start = cur_start - timedelta(days=period_days)
        prior_end = cur_start

        metric_names = [
            "posts_published", "replies_sent", "reply_accuracy",
            "revenue_total", "orders_count", "low_stock_open", "handoffs_count"
        ]

        metrics_data = {}
        for name in metric_names:
            cur_val = await self.compute_metric(name, cur_start, now, store_id)
            prior_val = await self.compute_metric(name, prior_start, prior_end, store_id)

            if cur_val > prior_val:
                trend = "up"
            elif cur_val < prior_val:
                trend = "down"
            else:
                trend = "stable"

            metrics_data[name] = {
                "current": cur_val,
                "prior": prior_val,
                "trend": trend,
            }

        return {
            "period_days": period_days,
            "window_start": cur_start,
            "window_end": now,
            "metrics": metrics_data,
        }

    async def generate_summary(self, store_id: Optional[int] = None, period_days: int = 30) -> str:
        """Generate executive summary using LLM with deterministic fallback."""
        dash = await self.dashboard(store_id, period_days)
        metrics = dash["metrics"]

        prompt = (
            f"Generate a 3-bullet executive summary of our e-commerce multi-agent system performance over the last {period_days} days:\n"
            f"- Revenue: ${metrics.get('revenue_total', {}).get('current', 0):.2f}\n"
            f"- Orders: {metrics.get('orders_count', {}).get('current', 0)}\n"
            f"- Social Posts Published: {metrics.get('posts_published', {}).get('current', 0)}\n"
            f"- Comments Replied: {metrics.get('replies_sent', {}).get('current', 0)}\n"
            f"- Customer Support Handoffs: {metrics.get('handoffs_count', {}).get('current', 0)}\n"
            f"- Open Low Stock Alerts: {metrics.get('low_stock_open', {}).get('current', 0)}"
        )

        try:
            return await self.llm.generate(prompt, system="You are an e-commerce analytics executive.")
        except NotImplementedError:
            rev = metrics.get('revenue_total', {}).get('current', 0)
            orders = int(metrics.get('orders_count', {}).get('current', 0))
            posts = int(metrics.get('posts_published', {}).get('current', 0))
            replies = int(metrics.get('replies_sent', {}).get('current', 0))
            handoffs = int(metrics.get('handoffs_count', {}).get('current', 0))

            return (
                f"• Generated **${rev:.2f}** in revenue across **{orders}** orders over the last {period_days} days.\n"
                f"• Social automation published **{posts}** posts and resolved **{replies}** customer comments.\n"
                f"• Customer support escalated **{handoffs}** conversations to human team members for resolution."
            )

    async def regenerate_kpi(self, name: str, target: float, store_id: Optional[int] = None) -> KPI:
        """Calculate metric and upsert a KPI record."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        cur_val = await self.compute_metric(name, start, now, store_id)

        trend = "up" if cur_val >= target else "down"

        res = await self.db.execute(select(KPI).where(KPI.name == name))
        kpi = res.scalar_one_or_none()
        if not kpi:
            kpi = KPI(name=name, current_value=cur_val, target_value=target, trend=trend)
            self.db.add(kpi)
        else:
            kpi.current_value = cur_val
            kpi.target_value = target
            kpi.trend = trend
            kpi.recorded_at = now

        await self.db.flush()
        return kpi

    async def list_metrics(self) -> list[MetricDefinition]:
        res = await self.db.execute(select(MetricDefinition))
        return list(res.scalars().all())

    async def list_snapshots(self, metric_id: Optional[int] = None, limit: int = 50) -> list[ReportSnapshot]:
        q = select(ReportSnapshot).order_by(ReportSnapshot.created_at.desc()).limit(limit)
        if metric_id:
            q = q.where(ReportSnapshot.metric_id == metric_id)
        res = await self.db.execute(q)
        return list(res.scalars().all())

    async def list_kpis(self) -> list[KPI]:
        res = await self.db.execute(select(KPI).order_by(KPI.name.asc()))
        return list(res.scalars().all())

    async def ingest_bus_event(self, event: Event) -> None:
        """Lightweight event hook for logging agent actions across the bus."""
        logger.info(f"Analytics event hook received: {event.event_type} from {event.source}")
