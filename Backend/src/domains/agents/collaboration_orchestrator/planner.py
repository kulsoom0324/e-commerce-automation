# ═══════════════════════════════════════════════════════════════
# agents / collaboration_orchestrator / planner.py
#
# PURPOSE: Rule-based & LLM workflow planner for cross-agent execution.
# ═══════════════════════════════════════════════════════════════

from typing import Optional


def plan_rule_based(rule_name: str, context: dict) -> list[dict]:
    """Generate deterministic ordered step sequence for known business rules."""
    if rule_name == "overstock_promo":
        return [
            {
                "step_name": "inspect_catalog",
                "assigned_agent": "inventory_sync",
                "inputs": {"store_id": context.get("store_id")},
                "expected_output": "catalog_refreshed",
            },
            {
                "step_name": "generate_promotional_content",
                "assigned_agent": "content_generation",
                "inputs": {
                    "product_id": context.get("product_id"),
                    "platform": context.get("platform", "instagram"),
                    "brand_voice_id": context.get("brand_voice_id"),
                    "image_model": "gemini",
                    "auto_approve": True,
                },
                "expected_output": "post_generated",
            },
            {
                "step_name": "schedule_social_post",
                "assigned_agent": "content_scheduling",
                "inputs": {
                    "store_id": context.get("store_id"),
                    "platform": context.get("platform", "instagram"),
                    "product_id": context.get("product_id"),
                },
                "expected_output": "post_scheduled",
            },
            {
                "step_name": "notify_business_owner",
                "assigned_agent": "notification",
                "inputs": {
                    "message": f"Overstock promo created for product {context.get('product_id')} (Stock: {context.get('current_stock')})"
                },
                "expected_output": "notification_dispatched",
            },
        ]

    elif rule_name == "low_stock_clearance":
        return [
            {
                "step_name": "generate_clearance_post",
                "assigned_agent": "content_generation",
                "inputs": {
                    "product_id": context.get("product_id"),
                    "platform": context.get("platform", "instagram"),
                    "auto_approve": True,
                },
                "expected_output": "post_generated",
            },
            {
                "step_name": "notify_owner_low_stock",
                "assigned_agent": "notification",
                "inputs": {
                    "message": f"Low stock alert clearance post scheduled for product {context.get('product_id')}"
                },
                "expected_output": "notification_dispatched",
            },
        ]

    # Generic fallback plan
    return [
        {
            "step_name": "run_analytics_rollup",
            "assigned_agent": "analytics_insights",
            "inputs": {},
            "expected_output": "rollup_completed",
        }
    ]


def is_ambiguous_or_risky(rule_name: str, context: dict) -> bool:
    """Evaluate if an action sequence carries high risk and requires human approval."""
    # If product_id is missing or current stock is 0 or negative -> risky
    if not context.get("product_id"):
        return True

    current_stock = context.get("current_stock", 1)
    if current_stock <= 0:
        return True

    # High dollar price or ambiguous context
    if context.get("price", 0) > 1000.0:
        return True

    return False
