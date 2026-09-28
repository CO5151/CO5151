"""Statutory Retriever Tool for LegalPilot-VN (Google ADK compliant).

Provides functions and ADK tool wrappers for statutory lookups over
Vietnamese legal documents, decrees, and circulars.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ToolDefinition


def retrieve_statutory_provisions(keywords: list[str]) -> list[dict[str, Any]]:
    """Retrieves statutory articles matching given legal keywords.

    Args:
        keywords: List of keyword tokens to search in statute catalog.

    Returns:
        List of matching legal articles and metadata.
    """
    from src.agents.lawgraph import LawGraphAgent

    agent = LawGraphAgent()
    return agent.retrieve_provisions(subgoals=["Tra cứu theo từ khoá"], keywords=keywords)


STATUTORY_RETRIEVER_TOOL = ToolDefinition(
    name="retrieve_statutory_provisions",
    description="Tra cứu các điều khoản luật, nghị định, thông tư Việt Nam theo từ khoá quy phạm pháp luật.",
    func=retrieve_statutory_provisions,
    parameters_schema={
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Danh sách các từ khoá pháp lý cần tra cứu.",
            }
        },
        "required": ["keywords"],
    },
)
