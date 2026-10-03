# ═══════════════════════════════════════════════════════════════
# fte_sdk / llm / council.py
#
# PURPOSE: Reusable multi-LLM council pipeline. Research →
#          Generate → Review → Approve. Har agent apne steps
#          define karta hai, execution SDK handle karta hai.
#
# USED BY: content_generation, comment_engagement, customer_support,
#          collaboration_orchestrator
# ═══════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from typing import Any

from src.sdk.llm.client import LLMClient


# ─── CouncilStep ──────────────────────────────────────────────
# One step in the council pipeline.
# - name:        identifier for this step (e.g. "research")
# - llm_role:    what this step does (researcher, writer, reviewer, approver)
# - prompt_template: string with {placeholders} for context
# - schema:      optional JSON schema for structured output

class CouncilStep:
    """Defines one stage in the council pipeline."""
    def __init__(
        self,
        name: str,
        llm_role: str,
        prompt_template: str,
        schema: dict | None = None,
    ):
        self.name = name
        self.llm_role = llm_role
        self.prompt_template = prompt_template
        self.schema = schema


# ─── CouncilBase (Abstract) ───────────────────────────────────
# Override steps() to define the council pipeline.
# execute() runs all steps in order, passing context between.
#
# Example:
#   class PostCouncil(CouncilBase):
#       def steps(self):
#           return [
#               CouncilStep("research", "researcher", "Analyze: {product}"),
#               CouncilStep("writer", "writer", "Write caption for: {product}"),
#               CouncilStep("reviewer", "reviewer", "Review: {caption}"),
#           ]

class CouncilBase(ABC):
    """Override steps() to define the pipeline."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    @abstractmethod
    def steps(self) -> list[CouncilStep]:
        """Return ordered list of council pipeline steps."""
        pass

    # ─── execute() ───────────────────────────────────────────
    # Runs all steps sequentially. Each step's output is stored
    # in context[step.name]. Next step can reference previous
    # results via prompt_template placeholders.

    async def execute(self, context: dict) -> dict:
        """Run all steps sequentially, passing context between steps."""
        for step in self.steps():
            prompt = step.prompt_template.format(**context)
            if step.schema:
                result = await self.llm.generate_structured(prompt, step.schema)
            else:
                result = await self.llm.generate(prompt)
            context[step.name] = result
        return context
