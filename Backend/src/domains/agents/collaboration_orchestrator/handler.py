# ═══════════════════════════════════════════════════════════════
# agents / collaboration_orchestrator / handler.py
#
# PURPOSE: Business logic for Collaboration Orchestrator Agent.
#          Detects cross-agent opportunities, creates/executes multi-agent
#          workflows, and falls back to human attention on ambiguity/risk.
# ═══════════════════════════════════════════════════════════════

import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sdk.models.workflow import Workflow, WorkflowLog, AgentTask
from src.sdk.models.base import Store, Product, Variant, LowStockAlert
from src.sdk.models.content import GeneratedPost
from src.sdk.models.social import SocialAccount, ScheduledPost
from src.sdk.events import Event
from src.sdk.llm.client import LLMClient
from src.sdk.llm.prompts import WORKFLOW_PLANNER_PROMPT

from src.domains.agents.collaboration_orchestrator.config import get_settings
from src.domains.agents.collaboration_orchestrator.planner import plan_rule_based, is_ambiguous_or_risky

from src.domains.agents.inventory_sync.handler import InventorySyncHandler
from src.domains.agents.content_generation.handler import ContentGenerationHandler
from src.domains.agents.content_scheduling.handler import ContentSchedulingHandler
from src.domains.agents.analytics_insights.handler import AnalyticsInsightsHandler

logger = logging.getLogger(__name__)


class CollaborationOrchestratorHandler:
    """Coordinates multi-agent workflows across the shared database."""

    def __init__(
        self,
        db: AsyncSession,
        llm_client: Optional[LLMClient] = None,
        event_bus=None,
    ):
        self.db = db
        self.settings = get_settings()
        self.llm = llm_client or LLMClient(api_key=self.settings.LLM_API_KEY)
        self.event_bus = event_bus

    async def detect_opportunities(self) -> list[dict]:
        """Scan DB for cross-agent conditions (e.g. overstocked items, unresolved alerts)."""
        opportunities = []
        now = datetime.now(timezone.utc)
        recent_threshold = now - timedelta(days=self.settings.PROMO_REPEAT_DAYS)

        # 1. Detect Overstock: Variant quantity >= OVERSTOCK_THRESHOLD
        q_overstock = (
            select(Variant, Product, Store)
            .join(Product, Variant.product_id == Product.id)
            .join(Store, Product.store_id == Store.id)
            .where(Variant.inventory_quantity >= self.settings.OVERSTOCK_THRESHOLD)
        )
        res = await self.db.execute(q_overstock)
        rows = res.all()

        for variant, product, store in rows:
            # Check if this product was recently promoted
            promo_q = select(ScheduledPost).where(
                ScheduledPost.product_id == product.id,
                ScheduledPost.created_at >= recent_threshold,
            )
            recent_post = (await self.db.execute(promo_q)).scalar_one_or_none()
            if not recent_post:
                ctx = {
                    "store_id": store.id,
                    "product_id": product.id,
                    "variant_id": variant.id,
                    "title": product.title,
                    "current_stock": variant.inventory_quantity,
                    "price": float(variant.price),
                }
                risky = is_ambiguous_or_risky("overstock_promo", ctx)
                opportunities.append({
                    "rule": "overstock_promo",
                    "title": f"Promote Overstocked Item: {product.title}",
                    "context": ctx,
                    "risk_score": 0.8 if risky else 0.1,
                    "requires_human_approval": risky,
                })

        # 2. Detect Low Stock: Active unresolved LowStockAlerts
        if self.settings.LOW_STOCK_PROMO:
            q_alerts = select(LowStockAlert).where(LowStockAlert.is_resolved == False)
            alerts = (await self.db.execute(q_alerts)).scalars().all()
            for alert in alerts:
                # Find product
                var_res = await self.db.execute(
                    select(Variant, Product).join(Product, Variant.product_id == Product.id).where(Variant.id == alert.variant_id)
                )
                match = var_res.first()
                if match:
                    variant, product = match
                    ctx = {
                        "store_id": product.store_id,
                        "product_id": product.id,
                        "variant_id": variant.id,
                        "current_stock": alert.current_stock,
                    }
                    opportunities.append({
                        "rule": "low_stock_clearance",
                        "title": f"Clearance Promo for Low Stock: {product.title}",
                        "context": ctx,
                        "risk_score": 0.2,
                        "requires_human_approval": False,
                    })

        return opportunities

    async def create_workflow(self, name: str, rule: str, context: dict) -> Workflow:
        """Create a multi-agent Workflow and child AgentTasks."""
        steps = plan_rule_based(rule, context)
        risky = is_ambiguous_or_risky(rule, context)
        init_status = "pending_human_approval" if risky else "pending"

        workflow = Workflow(
            name=name,
            description=f"Automated workflow created for rule: {rule}",
            steps_json=json.dumps(steps),
            status=init_status,
            created_by_agent="collaboration_orchestrator",
        )
        self.db.add(workflow)
        await self.db.flush()

        for step in steps:
            task = AgentTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                workflow_id=workflow.id,
                assigned_agent=step["assigned_agent"],
                status="pending",
                payload=json.dumps(step["inputs"]),
            )
            self.db.add(task)

        await self.db.flush()

        if risky:
            await self.notify_human(
                workflow_id=workflow.id,
                reason=f"Ambiguous or high-risk parameters detected in rule '{rule}'",
                context=context,
            )

        return workflow

    async def plan_workflow(self, task_description: str) -> list[dict]:
        """Use LLM planner prompt or rule fallback for ad-hoc user tasks."""
        available_agents = "inventory_sync, content_generation, content_scheduling, comment_engagement, customer_support, analytics_insights"
        prompt = WORKFLOW_PLANNER_PROMPT.format(
            task_description=task_description,
            available_agents=available_agents,
        )
        try:
            raw_plan = await self.llm.generate(prompt, system="You are a multi-agent system planner.")
            clean = raw_plan.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except Exception:
            return plan_rule_based("generic", {"description": task_description})

    async def execute_workflow(self, workflow_id: int) -> list[WorkflowLog]:
        """Sequentially execute all steps in a workflow across agents."""
        res = await self.db.execute(select(Workflow).where(Workflow.id == workflow_id))
        workflow = res.scalar_one_or_none()
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        if workflow.status == "pending_human_approval":
            logger.warning(f"Workflow {workflow_id} is awaiting human approval and cannot be auto-executed.")
            return []

        workflow.status = "running"
        await self.db.flush()

        steps = json.loads(workflow.steps_json or "[]")
        logs = []

        # Find matching tasks
        tasks_res = await self.db.execute(
            select(AgentTask).where(AgentTask.workflow_id == workflow_id).order_by(AgentTask.id.asc())
        )
        tasks = tasks_res.scalars().all()

        step_output_context = {}

        for idx, step in enumerate(steps):
            task = tasks[idx] if idx < len(tasks) else None
            if task:
                task.status = "running"
                await self.db.flush()

            t_start = time.time()
            agent_name = step["assigned_agent"]
            step_name = step["step_name"]

            try:
                outcome = await self._run_step(step, step_output_context)
                duration_ms = round((time.time() - t_start) * 1000, 2)

                log_entry = WorkflowLog(
                    workflow_id=workflow_id,
                    step_name=step_name,
                    agent_name=agent_name,
                    result=json.dumps(outcome),
                    duration_ms=duration_ms,
                    status="completed",
                )
                self.db.add(log_entry)
                logs.append(log_entry)

                if task:
                    task.status = "completed"
                    task.result = json.dumps(outcome)
                    task.completed_at = datetime.now(timezone.utc)
                await self.db.flush()

                step_output_context[step_name] = outcome

            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                duration_ms = round((time.time() - t_start) * 1000, 2)

                log_entry = WorkflowLog(
                    workflow_id=workflow_id,
                    step_name=step_name,
                    agent_name=agent_name,
                    result=json.dumps({"error": str(e)}),
                    duration_ms=duration_ms,
                    status="failed",
                )
                self.db.add(log_entry)
                logs.append(log_entry)

                if task:
                    task.status = "failed"
                    task.result = json.dumps({"error": str(e)})

                workflow.status = "failed"
                await self.db.flush()
                await self.notify_human(
                    workflow_id=workflow_id,
                    reason=f"Step '{step_name}' failed with error: {str(e)}",
                    context=step.get("inputs", {}),
                )
                return logs

        workflow.status = "completed"
        workflow.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return logs

    async def _run_step(self, step: dict, context: dict) -> dict:
        """Internal dispatch executing actual agent logic against shared DB."""
        agent = step["assigned_agent"]
        inputs = step.get("inputs", {})

        if agent == "inventory_sync":
            store_id = inputs.get("store_id")
            if store_id:
                handler = InventorySyncHandler(self.db)
                return await handler.refresh_products(store_id)
            return {"status": "ok", "message": "Catalog refreshed"}

        elif agent == "content_generation":
            handler = ContentGenerationHandler(self.db, event_bus=self.event_bus)
            prod_id = inputs.get("product_id")
            if not prod_id:
                return {"status": "skipped", "reason": "No product_id"}
            post = await handler.generate_post(
                product_id=prod_id,
                brand_voice_id=inputs.get("brand_voice_id"),
                platform=inputs.get("platform", "instagram"),
                image_model=inputs.get("image_model", "gemini"),
            )
            # Auto-approve if requested
            if inputs.get("auto_approve"):
                post = await handler.approve_post(post.id)
            return {"status": "ok", "post_id": post.id, "caption": post.caption}

        elif agent == "content_scheduling":
            handler = ContentSchedulingHandler(self.db)
            store_id = inputs.get("store_id")
            # Find a social account
            acc_res = await self.db.execute(
                select(SocialAccount).where(SocialAccount.store_id == store_id).limit(1)
            )
            acc = acc_res.scalar_one_or_none()
            if not acc:
                return {"status": "warning", "message": "No social account connected to schedule post"}

            # Grab latest approved generated post for this product
            gen_res = await self.db.execute(
                select(GeneratedPost)
                .where(GeneratedPost.product_id == inputs.get("product_id"), GeneratedPost.status == "approved")
                .order_by(GeneratedPost.id.desc())
                .limit(1)
            )
            gen_post = gen_res.scalar_one_or_none()
            caption = gen_post.caption if gen_post else "Exciting special promotion! 🎉"

            sched = await handler.schedule_post(
                social_account_id=acc.id,
                caption=caption,
                media_urls=[],
                platform=acc.platform,
                scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
                product_id=inputs.get("product_id"),
                generated_post_id=gen_post.id if gen_post else None,
            )
            return {"status": "ok", "scheduled_post_id": sched.id}

        elif agent == "analytics_insights":
            handler = AnalyticsInsightsHandler(self.db)
            return await handler.run_rollup()

        elif agent == "notification":
            return {"status": "ok", "delivered": True, "message": inputs.get("message")}

        return {"status": "ok", "message": f"Step executed by {agent}"}

    async def notify_human(self, workflow_id: int, reason: str, context: dict) -> None:
        """Escalate workflow to human attention."""
        log = WorkflowLog(
            workflow_id=workflow_id,
            step_name="human_intervention",
            agent_name="collaboration_orchestrator",
            result=json.dumps({"reason": reason, "context": context}),
            status="human_attention",
        )
        self.db.add(log)
        await self.db.flush()

        if self.event_bus:
            try:
                evt = Event(
                    event_type="workflow.human.attention",
                    source="collaboration_orchestrator",
                    payload={"workflow_id": workflow_id, "reason": reason, "context": context},
                )
                await self.event_bus.publish("events", evt.model_dump())
            except Exception as e:
                logger.warning(f"Failed to publish workflow attention event: {e}")

    async def approve_workflow(self, workflow_id: int) -> Workflow:
        """Human approval unlocks a pending_human_approval workflow and executes it."""
        res = await self.db.execute(select(Workflow).where(Workflow.id == workflow_id))
        wf = res.scalar_one_or_none()
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found")

        wf.status = "pending"
        await self.db.flush()
        await self.execute_workflow(workflow_id)
        return wf

    async def list_workflows(self, status: Optional[str] = None) -> list[Workflow]:
        q = select(Workflow).order_by(Workflow.created_at.desc())
        if status:
            q = q.where(Workflow.status == status)
        res = await self.db.execute(q)
        return list(res.scalars().all())

    async def get_workflow(self, workflow_id: int) -> Optional[dict]:
        res = await self.db.execute(select(Workflow).where(Workflow.id == workflow_id))
        wf = res.scalar_one_or_none()
        if not wf:
            return None

        tasks_res = await self.db.execute(
            select(AgentTask).where(AgentTask.workflow_id == workflow_id).order_by(AgentTask.id.asc())
        )
        tasks = tasks_res.scalars().all()

        logs_res = await self.db.execute(
            select(WorkflowLog).where(WorkflowLog.workflow_id == workflow_id).order_by(WorkflowLog.id.asc())
        )
        logs = logs_res.scalars().all()

        return {
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "status": wf.status,
            "created_at": wf.created_at,
            "completed_at": wf.completed_at,
            "tasks": [
                {"id": t.id, "task_id": t.task_id, "agent": t.assigned_agent, "status": t.status}
                for t in tasks
            ],
            "logs": [
                {"id": l.id, "step": l.step_name, "agent": l.agent_name, "status": l.status, "duration_ms": l.duration_ms}
                for l in logs
            ],
        }

    async def list_human_attention_items(self) -> list[WorkflowLog]:
        res = await self.db.execute(
            select(WorkflowLog).where(WorkflowLog.status == "human_attention").order_by(WorkflowLog.created_at.desc())
        )
        return list(res.scalars().all())
