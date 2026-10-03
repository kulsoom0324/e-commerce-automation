# ═══════════════════════════════════════════════════════════════
# domains / agents / customers / api.py
#
# PURPOSE: Customer aggregation API.
#          Groups Order rows by customer_email to build a unique
#          customer list with order count, total spent, and last
#          order date. Sorted by total_spent DESC.
#
# USED BY: frontend dashboard (Customers tab)
# ═══════════════════════════════════════════════════════════════

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.domains.auth.service import get_current_user
from src.sdk.models.base import Order

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Customers"])


# ─── GET /api/v1/customers ────────────────────────────────────
# Aggregate customers from the Order table.
# Returns: [{ email, name, orders, total_spent, last_order }]

@router.get("/customers")
async def list_customers(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return unique customers for the store, ranked by total spend."""
    if store_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid store_id")

    result = await db.execute(
        select(
            Order.customer_email,
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total_price), 0).label("total_spent"),
            func.max(Order.ordered_at).label("last_order"),
        )
        .where(Order.store_id == store_id)
        .where(Order.customer_email.isnot(None))
        .group_by(Order.customer_email)
        .order_by(func.sum(Order.total_price).desc())
    )
    rows = result.all()

    customers: List[dict] = []
    for r in rows:
        email = r.customer_email
        # Derive display name from email local-part
        name = email.split("@")[0].replace(".", " ").replace("_", " ").title() if email else "Unknown"
        customers.append({
            "email": email,
            "name": name,
            "orders": r.orders,
            "total_spent": float(r.total_spent or 0),
            "last_order": r.last_order.isoformat() if r.last_order else None,
        })

    logger.info("list_customers: store_id=%d returned %d customers", store_id, len(customers))
    return customers
