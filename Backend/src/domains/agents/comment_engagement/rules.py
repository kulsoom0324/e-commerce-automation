# ═══════════════════════════════════════════════════════════════
# agents / comment_engagement / rules.py
#
# PURPOSE: Rule-based classification — decides what to do with an
#          incoming comment BEFORE any LLM call is made.
#
#          Per the architecture doc's own recommendation:
#          "Ship the rule-based version first and validate it in
#          production before turning on full AI-generated replies."
#
#          Three outcomes:
#            1. PRICE_QUERY  → auto-reply with real price (no LLM)
#            2. ESCALATE     → never auto-reply, flag for a human
#            3. NEEDS_LLM    → not a simple case, needs an AI reply
#
# USED BY: handler.py
# ═══════════════════════════════════════════════════════════════

from enum import Enum


class CommentAction(str, Enum):
    PRICE_QUERY = "price_query"
    ESCALATE = "escalate"
    NEEDS_LLM = "needs_llm"


def classify_comment(text: str, price_keywords: list[str], escalation_keywords: list[str]) -> CommentAction:
    """Classify a comment into an action, checking escalation first.

    Escalation always wins — a comment mentioning "refund" AND "price"
    still gets escalated, never auto-replied. Safety over cleverness.
    """
    lowered = text.lower()

    if any(kw in lowered for kw in escalation_keywords):
        return CommentAction.ESCALATE

    if any(kw in lowered for kw in price_keywords):
        return CommentAction.PRICE_QUERY

    return CommentAction.NEEDS_LLM


def format_price_reply(product_title: str, price: float, currency: str = "USD") -> str:
    """Template for the price-query auto-reply. No LLM needed."""
    return f"Hi! {product_title} is priced at {currency} {price:.2f}. Let us know if you'd like to order! 🙌"
