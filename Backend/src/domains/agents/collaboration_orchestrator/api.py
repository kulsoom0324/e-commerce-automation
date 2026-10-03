# ═══════════════════════════════════════════════════════════════
# agents / collaboration_orchestrator / api.py
#
# PURPOSE: REST API endpoints for Collaboration Orchestrator.
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.database import get_db

from src.domains.agents.collaboration_orchestrator.handler import CollaborationOrchestratorHandler
from src.domains.auth.service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/orchestrator", tags=["Collaboration Orchestrator"])


# ─── Schemas ──────────────────────────────────────────────────

class CreateWorkflowRequest(BaseModel):
    name: str
    rule: str
    context: dict = {}


class PlanWorkflowRequest(BaseModel):
    task_description: str


# ─── Endpoints ────────────────────────────────────────────────

@router.post("/detect")
async def detect_cross_agent_opportunities(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Scan store & agent state to detect actionable cross-agent opportunities."""
    handler = CollaborationOrchestratorHandler(db)
    return await handler.detect_opportunities()


@router.post("/workflows")
async def create_workflow(
    body: CreateWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new multi-agent workflow from a rule."""
    handler = CollaborationOrchestratorHandler(db)
    wf = await handler.create_workflow(name=body.name, rule=body.rule, context=body.context)
    await db.commit()
    return {
        "status": "created",
        "workflow_id": wf.id,
        "name": wf.name,
        "workflow_status": wf.status,
    }


@router.post("/workflows/plan")
async def plan_adhoc_workflow(
    body: PlanWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Use AI to plan a multi-step sequence for custom natural language instruction."""
    handler = CollaborationOrchestratorHandler(db)
    plan = await handler.plan_workflow(body.task_description)
    return {"task_description": body.task_description, "plan": plan}


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Execute all pending tasks within a workflow sequentially."""
    handler = CollaborationOrchestratorHandler(db)
    try:
        logs = await handler.execute_workflow(workflow_id)
        await db.commit()
        return {
            "status": "executed",
            "workflow_id": workflow_id,
            "steps_executed": len(logs),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/workflows/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Approve and trigger an ambiguous/high-risk workflow that was held for human review."""
    handler = CollaborationOrchestratorHandler(db)
    try:
        wf = await handler.approve_workflow(workflow_id)
        await db.commit()
        return {"status": "approved_and_executed", "workflow_id": wf.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/workflows")
async def list_workflows(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List workflows."""
    handler = CollaborationOrchestratorHandler(db)
    wfs = await handler.list_workflows(status)
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "status": w.status,
            "created_at": w.created_at,
            "completed_at": w.completed_at,
        }
        for w in wfs
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow_details(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get full workflow with tasks and step execution logs."""
    handler = CollaborationOrchestratorHandler(db)
    data = await handler.get_workflow(workflow_id)
    if not data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return data


@router.get("/attention")
async def list_human_attention_items(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List workflow logs flagged for human review or intervention."""
    handler = CollaborationOrchestratorHandler(db)
    items = await handler.list_human_attention_items()
    return [
        {
            "id": i.id,
            "workflow_id": i.workflow_id,
            "step_name": i.step_name,
            "agent_name": i.agent_name,
            "result": i.result,
            "created_at": i.created_at,
        }
        for i in items
    ]
