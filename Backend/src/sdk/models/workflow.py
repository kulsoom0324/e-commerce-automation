# ═══════════════════════════════════════════════════════════════
# fte_sdk / models / workflow.py
#
# PURPOSE: Multi-agent workflow orchestration — tracks what
#          each agent does in a cross-agent pipeline.
#
# USED BY: collaboration_orchestrator (plan, execute, log)
# ═══════════════════════════════════════════════════════════════

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import relationship

from src.sdk.database import Base


# ─── Workflow ─────────────────────────────────────────────────
# A multi-step, multi-agent workflow definition.
# steps_json = ordered list of steps (agent + task per step).

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    steps_json = Column(Text, default="[]")                  # JSON — ordered step list
    status = Column(String(50), default="pending")           # pending | running | completed | failed
    created_by_agent = Column(String(100), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    logs = relationship("WorkflowLog", back_populates="workflow", cascade="all, delete-orphan")


# ─── WorkflowLog ──────────────────────────────────────────────
# Log entry for each workflow step execution.
# Records which agent ran, result, duration.

class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    agent_name = Column(String(100), nullable=False)
    result = Column(Text, default="")
    duration_ms = Column(Float, default=0)
    status = Column(String(50), default="completed")        # completed | failed | skipped
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("Workflow", back_populates="logs")


# ─── AgentTask ────────────────────────────────────────────────
# Individual task assigned to an agent within a workflow.
# payload = input data, result = output data.

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), nullable=False, unique=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True, index=True)
    assigned_agent = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")          # pending | running | completed | failed
    payload = Column(Text, default="{}")                    # JSON
    result = Column(Text, default="")                       # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
