# ═══════════════════════════════════════════════════════════════
# domains / agents / customers / worker.py
#
# PURPOSE: Customers aggregation agent — no background worker.
#          Customer list is computed on-demand from the Order
#          table via the HTTP API.
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging

logger = logging.getLogger(__name__)


class CustomersWorker:
    """No-op worker — customers are aggregated on-demand via HTTP."""

    async def run(self) -> None:
        logger.info("Customers worker started (no-op, on-demand only)")
        await asyncio.Event().wait()


worker = CustomersWorker()
