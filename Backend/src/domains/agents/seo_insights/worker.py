# ═══════════════════════════════════════════════════════════════
# domains / agents / seo_insights / worker.py
#
# PURPOSE: SEO Insights agent background worker.
#          SEO analysis is on-demand (HTTP-triggered), so this
#          worker is a no-op. It exists only to satisfy the
#          _start_workers() convention in main.py.
# ═══════════════════════════════════════════════════════════════

import logging

logger = logging.getLogger(__name__)


class SEOInsightsWorker:
    """No-op worker — SEO analysis is served via HTTP only."""

    async def run(self) -> None:
        logger.info("SEO Insights worker started (no-op, on-demand only)")
        # Block forever — agent has no background loop
        import asyncio
        await asyncio.Event().wait()


worker = SEOInsightsWorker()
