"""Prompts package for LegalPilot-VN.

Centralized prompt definitions organized by agent role and execution type:
- planner_prompts: Subgoal decomposition and keyword planning
- drafter_prompts: Legal advisory synthesis and administrative formatting
- auditor_prompts: Adversarial critique and validity auditing
- research_prompts: LawGraph retrieval reasoning and web finding evaluation
"""

from src.prompts.auditor_prompts import (
    ADVERSARIAL_CRITIC_INSTRUCTION,
    AUDIT_CRITIQUE_PROMPT,
)
from src.prompts.drafter_prompts import (
    DRAFTER_INSTRUCTION,
    DOSSIER_SYSTEM_PROMPT,
    LEGAL_DISCLAIMER,
    WEB_DRAFTER_INSTRUCTION,
)
from src.prompts.planner_prompts import (
    PLANNER_INSTRUCTION,
    SUBGOAL_PLANNING_PROMPT,
)
from src.prompts.research_prompts import (
    LAWGRAPH_RESEARCH_PROMPT,
    LIVE_GAZETTE_PROMPT,
)

__all__ = [
    "PLANNER_INSTRUCTION",
    "SUBGOAL_PLANNING_PROMPT",
    "DRAFTER_INSTRUCTION",
    "WEB_DRAFTER_INSTRUCTION",
    "DOSSIER_SYSTEM_PROMPT",
    "LEGAL_DISCLAIMER",
    "AUDIT_CRITIQUE_PROMPT",
    "ADVERSARIAL_CRITIC_INSTRUCTION",
    "LAWGRAPH_RESEARCH_PROMPT",
    "LIVE_GAZETTE_PROMPT",
]
