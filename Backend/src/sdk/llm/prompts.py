# ═══════════════════════════════════════════════════════════════
# fte_sdk / llm / prompts.py
#
# PURPOSE: Shared prompt templates for LLM council steps.
#          Centralized so all agents use consistent prompts.
#          Har agent apne specific prompts yahan add kar sakta hai.
#
# USED BY: content_generation, comment_engagement, customer_support,
#          collaboration_orchestrator
# ═══════════════════════════════════════════════════════════════

# ─── Content Generation ───────────────────────────────────────
# Prompts for generating social media content.

CONTENT_RESEARCH_PROMPT = """
You are a product researcher. Analyze the following product data and extract:
- Key selling points (3-5)
- Target audience
- Unique features
- Emotion/feeling associated

Product: {product_data}
"""

CONTENT_WRITER_PROMPT = """
You are a social media copywriter. Write a {platform} caption for:
Product: {product_data}
Brand Voice: {brand_voice}
Key Points: {research}
Platform: {platform}

The caption should be engaging, on-brand, and drive engagement.
"""

CONTENT_REVIEWER_PROMPT = """
You are a brand tone reviewer. Review this caption:
Caption: {writer}

Check for:
1. Brand voice alignment
2. Grammar and clarity
3. Call to action effectiveness
4. Platform appropriateness

Output: pass/fail + suggestions.
"""


# ─── Comment Engagement ───────────────────────────────────────

COMMENT_CLASSIFIER_PROMPT = """
Classify this social media comment:
"{comment_text}"

Categories: question | complaint | praise | spam | other
Sentiment: positive | neutral | negative

Output: JSON with category + sentiment + confidence.
"""

COMMENT_REPLY_PROMPT = """
Write a reply to this {sentiment} comment:
"{comment_text}"

Tone: {brand_voice}
Rules: Do not be defensive. Be helpful. Keep under 100 words.
"""


# ─── Customer Support ─────────────────────────────────────────

SUPPORT_CLASSIFIER_PROMPT = """
Classify this customer support query:
"{query}"

Categories: order_status | product_question | return_request | complaint | other
Products mentioned: {product_data}

Output: JSON with category + relevant_product_ids.
"""

SUPPORT_QA_PROMPT = """
Answer this customer question based on the product information:
Question: {query}
Product Info: {context}
FAQ: {faq_data}

Be concise, accurate, and helpful.
"""


# ─── Collaboration ────────────────────────────────────────────

WORKFLOW_PLANNER_PROMPT = """
Plan a multi-agent workflow for this task:
Task: {task_description}
Available agents: {available_agents}

Output: ordered JSON list of steps with:
- step_name
- assigned_agent
- inputs
- expected_output
"""
