# ═══════════════════════════════════════════════════════════════
# domains / agents / seo_insights / api.py
#
# PURPOSE: SEO Insights HTTP API.
#          Analyzes product titles/descriptions to extract
#          keywords, suggest improvements, and surface gaps
#          (missing descriptions, weak titles, etc.).
#
# USED BY: frontend dashboard (SEO modal)
# ═══════════════════════════════════════════════════════════════

import logging
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.domains.auth.service import get_current_user
from src.sdk.models.base import Product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/seo", tags=["SEO Insights"])


# ─── Keyword extraction helper ────────────────────────────────
# Pull English words 4+ chars from titles; lowercase; count.

def _extract_keywords(titles: List[str], min_length: int = 4) -> dict:
    """Tokenize product titles into a {keyword: count} dict."""
    pattern = re.compile(rf"\b[a-zA-Z]{{{min_length},}}\b")
    keywords: dict = {}
    for title in titles or []:
        if not title:
            continue
        for token in pattern.findall(title.lower()):
            keywords[token] = keywords.get(token, 0) + 1
    return keywords


# ─── GET /api/v1/seo/analysis ─────────────────────────────────
# Pull all products for the given store, compute:
#   - top 20 keywords by frequency
#   - average title length
#   - missing descriptions
#   - actionable suggestions (top 5)

@router.get("/analysis")
async def get_seo_analysis(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return SEO health summary for the given store."""
    if store_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid store_id")

    # Fetch all products for the store
    result = await db.execute(
        select(Product).where(Product.store_id == store_id)
    )
    products = result.scalars().all()

    if not products:
        return {
            "store_id": store_id,
            "total_products": 0,
            "total_keywords": 0,
            "top_keywords": [],
            "avg_title_length": 0,
            "missing_descriptions": 0,
            "suggestions": [
                "Sync your store first to import products, then run SEO analysis."
            ],
        }

    # Keyword extraction
    titles = [p.title for p in products]
    keywords = _extract_keywords(titles)
    top_keywords = sorted(keywords.items(), key=lambda x: -x[1])[:20]

    # Stats
    total = len(products)
    avg_title_len = sum(len(t or "") for t in titles) / total
    missing_desc = sum(1 for p in products if not (p.description or "").strip())

    # Suggestions
    suggestions: List[str] = []
    for p in products:
        if not (p.description or "").strip():
            suggestions.append(f"Add description to: {p.title}")
            if len(suggestions) >= 5:
                break
    if avg_title_len < 30 and not suggestions:
        suggestions.append("Product titles are too short — aim for 30-60 characters.")
    if missing_desc == 0 and not suggestions:
        suggestions.append("SEO looks healthy! Consider adding more keywords to descriptions.")

    logger.info(
        "SEO analysis for store_id=%d: %d products, %d keywords, %d missing descriptions",
        store_id, total, len(keywords), missing_desc,
    )

    return {
        "store_id": store_id,
        "total_products": total,
        "total_keywords": len(keywords),
        "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
        "avg_title_length": round(avg_title_len, 1),
        "missing_descriptions": missing_desc,
        "suggestions": suggestions,
    }
