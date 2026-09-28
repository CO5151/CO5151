"""Agents module for LegalPilot-VN (Theme 9: Vietnamese Legal Agentic RAG).

Google ADK (Agent Development Kit) multi-agent implementation.

Exports:
- ADKAgent: Base class for ADK agents.
- ADKRunner: Multi-agent execution coordinator and tracer.
- ToolDefinition: Google ADK compliant tool specification.
- AgentResult: Result container for agent execution.
- LegalOrchestrator: Central coordinator managing multi-agent loop & recovery.
- LawGraphAgent: Statutory retrieval and legal knowledge graph traversal.
- ClaimAuditorAgent: Verification oracle detecting expired/revoked documents.
- DrafterAgent: Synthesizes structured compliance dossiers with disclaimers.
"""

from src.agents.base import ADKAgent, ADKRunner, AgentResult, ToolDefinition
from src.agents.claim_auditor import ClaimAuditorAgent
from src.agents.drafter import DrafterAgent
from src.agents.lawgraph import LawGraphAgent
from src.agents.orchestrator import LegalOrchestrator

__all__ = [
    "ADKAgent",
    "ADKRunner",
    "AgentResult",
    "ClaimAuditorAgent",
    "DrafterAgent",
    "LawGraphAgent",
    "LegalOrchestrator",
    "ToolDefinition",
]
