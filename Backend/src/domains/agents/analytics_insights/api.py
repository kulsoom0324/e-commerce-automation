# ═══════════════════════════════════════════════════════════════
# agents / analytics_insights / api.py
#
# PURPOSE: REST API endpoints for Analytics & Insights Agent.
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db
from src.sdk.models.base import Order

from src.domains.agents.analytics_insights.handler import AnalyticsInsightsHandler
from src.domains.auth.service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Insights"])


# ─── Schemas ──────────────────────────────────────────────────

class RollupRequest(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class KPIRegenerateRequest(BaseModel):
    name: str
    target: float
    store_id: Optional[int] = None


# ─── Endpoints ────────────────────────────────────────────────

@router.post("/rollup")
async def trigger_rollup(
    body: Optional[RollupRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Trigger manual metrics rollup."""
    handler = AnalyticsInsightsHandler(db)
    p_start = body.period_start if body else None
    p_end = body.period_end if body else None
    res = await handler.run_rollup(period_start=p_start, period_end=p_end)
    await db.commit()
    return res


@router.get("/dashboard")
async def get_dashboard(
    store_id: Optional[int] = Query(None),
    period_days: int = Query(30),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get live computed dashboard metrics and trends."""
    handler = AnalyticsInsightsHandler(db)
    return await handler.dashboard(store_id=store_id, period_days=period_days)


@router.get("/summary")
async def get_summary(
    store_id: Optional[int] = Query(None),
    period_days: int = Query(30),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get natural language executive summary."""
    handler = AnalyticsInsightsHandler(db)
    summary_text = await handler.generate_summary(store_id=store_id, period_days=period_days)
    return {"period_days": period_days, "summary": summary_text}


@router.get("/metrics")
async def list_metrics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List available metric definitions."""
    handler = AnalyticsInsightsHandler(db)
    metrics = await handler.list_metrics()
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "refresh_interval": m.refresh_interval,
            "agent_source": m.agent_source,
        }
        for m in metrics
    ]


@router.get("/snapshots")
async def list_snapshots(
    metric_id: Optional[int] = Query(None),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List captured historical snapshots."""
    handler = AnalyticsInsightsHandler(db)
    snapshots = await handler.list_snapshots(metric_id=metric_id, limit=limit)
    return [
        {
            "id": s.id,
            "metric_id": s.metric_id,
            "value": float(s.value),
            "period_start": s.period_start,
            "period_end": s.period_end,
            "created_at": s.created_at,
        }
        for s in snapshots
    ]


@router.get("/kpis")
async def list_kpis(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List current KPIs."""
    handler = AnalyticsInsightsHandler(db)
    kpis = await handler.list_kpis()
    return [
        {
            "id": k.id,
            "name": k.name,
            "current_value": float(k.current_value),
            "target_value": float(k.target_value),
            "trend": k.trend,
            "recorded_at": k.recorded_at,
        }
        for k in kpis
    ]


@router.post("/kpis")
async def create_or_update_kpi(
    body: KPIRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Regenerate or set target for a KPI."""
    handler = AnalyticsInsightsHandler(db)
    kpi = await handler.regenerate_kpi(body.name, body.target, body.store_id)
    await db.commit()
    return {
        "status": "updated",
        "name": kpi.name,
        "current_value": float(kpi.current_value),
        "target_value": float(kpi.target_value),
        "trend": kpi.trend,
    }


# ─── GET /api/v1/analytics/revenue ────────────────────────────
# Aggregate revenue by day for the chart on the dashboard.
# Returns: [{ date: "YYYY-MM-DD", revenue: float }]

@router.get("/revenue")
async def get_revenue_by_day(
    store_id: int = Query(..., description="Store ID"),
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return daily revenue totals for the last N days, oldest first."""
    if store_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid store_id")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Order.ordered_at).label("day"),
            func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
        )
        .where(Order.store_id == store_id)
        .where(Order.ordered_at >= since)
        .group_by(func.date(Order.ordered_at))
        .order_by(func.date(Order.ordered_at))
    )
    rows = result.all()

    points: List[dict] = [
        {"date": str(r.day), "revenue": float(r.revenue or 0)}
        for r in rows
    ]

    logger.info(
        "revenue_by_day: store_id=%d days=%d returned %d points",
        store_id, days, len(points),
    )
    return points
