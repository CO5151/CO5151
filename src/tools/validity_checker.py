"""Statutory Validity Checker Tool for LegalPilot-VN (Google ADK compliant).

Provides functions and ADK tool wrappers to audit temporal status,
revocation chains, and amendment relations of legal instruments.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ToolDefinition


def check_statute_validity(doc_id: str) -> dict[str, Any]:
    """Verifies whether a statutory document is active, expired, or replaced.

    Args:
        doc_id: Identifier of the document (e.g. '52/2024/ND-CP', '101/2012/ND-CP').

    Returns:
        Dictionary with status ('active', 'expired'), revoking instrument, and dates.
    """
    from src.agents.lawgraph import LawGraphAgent

    catalog = LawGraphAgent.STATUTE_CATALOG
    doc_info = catalog.get(doc_id)
    if not doc_info:
        return {
            "doc_id": doc_id,
            "status": "unknown",
            "is_valid": False,
            "message": f"Văn bản {doc_id} không có trong cơ sở dữ liệu tra cứu.",
        }

    status = doc_info.get("status", "unknown")
    revoked_by = doc_info.get("revoked_by")
    return {
        "doc_id": doc_id,
        "title": doc_info.get("title"),
        "status": status,
        "is_valid": status == "active",
        "effective_date": doc_info.get("effective_date"),
        "revoked_by": revoked_by,
        "revoked_date": doc_info.get("revoked_date"),
        "supersedes": doc_info.get("supersedes", []),
    }


VALIDITY_CHECKER_TOOL = ToolDefinition(
    name="check_statute_validity",
    description="Kiểm tra trạng thái hiệu lực pháp lý của văn bản quy phạm pháp luật (còn hiệu lực hay đã bị bãi bỏ/thay thế).",
    func=check_statute_validity,
    parameters_schema={
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Số hiệu văn bản (ví dụ: '52/2024/ND-CP', '101/2012/ND-CP').",
            }
        },
        "required": ["doc_id"],
    },
)
