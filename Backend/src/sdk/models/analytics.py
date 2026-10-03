# ═══════════════════════════════════════════════════════════════
# fte_sdk / models / analytics.py
#
# PURPOSE: Analytics & KPI models — daily/weekly rollups,
#          metric definitions, trend tracking.
#
# USED BY: analytics_insights (aggregate, report)
# ═══════════════════════════════════════════════════════════════

from sqlalchemy import (
    Column, Integer, String, Numeric, Text, DateTime, Boolean,
    ForeignKey, func,
)

from src.sdk.database import Base


# ─── MetricDefinition ─────────────────────────────────────────
# Defines a calculable metric. name = human label,
# sql_query = how to compute it. agent_source = which agent
# owns this metric (inventory_sync, content, etc.)

class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    sql_query = Column(Text, default="")                   # SQL to compute this metric
    refresh_interval = Column(String(50), default="daily") # hourly | daily | weekly
    agent_source = Column(String(100), default="")         # which agent owns this
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── ReportSnapshot ───────────────────────────────────────────
# Captured value of a metric for a specific time period.
# Used for trend tracking and dashboards.

class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False, index=True)
    value = Column(Numeric(14, 4), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── KPI ──────────────────────────────────────────────────────
# Key Performance Indicator — tracks target vs actual.
# trend = "up" | "down" | "stable"

class KPI(Base):
    __tablename__ = "kpis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    current_value = Column(Numeric(14, 4), default=0)
    target_value = Column(Numeric(14, 4), default=0)
    trend = Column(String(50), default="stable")
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
