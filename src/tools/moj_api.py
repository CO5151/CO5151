"""Official lookup against the Ministry of Justice VBPL gateway.

Discovered endpoint (verified live):

    GET https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}
        -> 200, public, no auth. Returns docNum, title, docType, effFrom,
           effTo, effStatus {name, code}, agencyName, organization,
           provisionTree, references.

    GET/POST .../qtdc/public/search
        -> 401 "Unauthorized: Token expired or invalid".
           The search endpoint exists but is not open, so ids are resolved via
           the whitelisted web search instead (vbpl.vn detail URLs end with
           `--<id>`).

This matters because it is the *only* authoritative source the project can
reach. `verify_vbpl_status()` scrapes the vbpl.vn web page, which answers 403;
this gateway answers 200 with structured data.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from src.core.logger import logger
from src.tools.base import ToolDefinition

MOJ_BASE = "https://vbpl-bientap-gateway.moj.gov.vn/api"
MOJ_DOC_PATH = "/qtdc/public/doc/"
USER_AGENT = "LegalPilot-VN/1.0 (Educational Academic Agentic RAG; HCMUT)"


def _date(value: Any) -> str | None:
    """Gateway returns ISO datetimes with a midnight time part; keep the date."""
    if not value:
        return None
    return str(value)[:10]


def get_official_document(doc_id: str, timeout_seconds: float = 20.0) -> dict[str, Any]:
    """Fetches one document record from the MoJ gateway by its internal id."""
    doc_id = str(doc_id or "").strip()
    if not doc_id:
        return {"found": False, "error": "empty_id"}

    try:
        resp = httpx.get(
            f"{MOJ_BASE}{MOJ_DOC_PATH}{doc_id}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout_seconds,
            follow_redirects=True,
        )
    except Exception as e:
        logger.warning("moj_api: request failed (%s: %s)", type(e).__name__, e)
        return {"found": False, "error": f"{type(e).__name__}: {e}"}

    if resp.status_code != 200:
        return {"found": False, "status_code": resp.status_code, "error": resp.text[:200]}

    payload = resp.json() or {}
    data = payload.get("data") or {}
    if not data:
        return {"found": False, "error": "empty_data"}

    eff = data.get("effStatus") or {}
    return {
        "found": True,
        "source": "vbpl-bientap-gateway.moj.gov.vn",
        "doc_id": data.get("id"),
        "doc_num": data.get("docNum"),
        "title": data.get("title"),
        "doc_type": (data.get("docType") or {}).get("name"),
        "eff_status": eff.get("name"),
        "eff_status_code": eff.get("code"),
        "eff_from": _date(data.get("effFrom")),
        "eff_to": _date(data.get("effTo")),
        "issue_date": _date(data.get("issueDate")),
        "agency": data.get("agencyName"),
        "organization": (data.get("organization") or {}).get("shortName"),
        "reviewed": data.get("reviewed"),
        "review_status": data.get("reviewStatus"),
        "has_clause_relation": data.get("hasClauseRelation"),
    }


def extract_doc_id_from_url(url: str) -> str | None:
    """vbpl.vn detail URLs look like `.../chi-tiet/<slug>--<numeric id>`."""
    m = re.search(r"--(\d{1,8})(?:$|[/?#])", url or "")
    return m.group(1) if m else None


def resolve_document_id(query: str, limit: int = 5) -> str | None:
    """Finds a vbpl.vn document id by searching official domains."""
    from src.tools.web_search import search_official_legal_web

    payload = search_official_legal_web(query, limit=limit)
    for hit in payload.get("hits", []):
        if "vbpl.vn" not in hit.get("url", ""):
            continue
        doc_id = extract_doc_id_from_url(hit["url"])
        if doc_id:
            return doc_id
    return None


def check_document_status(query_or_id: str) -> dict[str, Any]:
    """Resolves a document number to an official MoJ record.

    Accepts either a numeric gateway id or a free-text statute number
    ("101/2012/NĐ-CP"). Returns the normalised record plus how it was resolved.
    """
    value = str(query_or_id or "").strip()
    if not value:
        return {"found": False, "error": "empty_query"}

    if value.isdigit():
        record = get_official_document(value)
        record["resolved_by"] = "direct_id"
        return record

    doc_id = resolve_document_id(value)
    if not doc_id:
        return {
            "found": False,
            "error": "no vbpl.vn document id found for this query",
            "resolved_by": "search",
        }
    record = get_official_document(doc_id)
    record["resolved_by"] = "search"
    return record


LOOKUP_OFFICIAL_DOCUMENT_TOOL = ToolDefinition(
    name="lookup_official_document",
    description=(
        "Tra cứu bản ghi chính thức của một văn bản trên cổng dữ liệu Bộ Tư pháp "
        "(vbpl-bientap-gateway.moj.gov.vn): số hiệu, tên, hiệu lực từ/đến, "
        "trạng thái hiệu lực (effStatus)."
    ),
    func=check_document_status,
    parameters_schema={
        "type": "object",
        "properties": {
            "query_or_id": {
                "type": "string",
                "description": "Số hiệu văn bản (vd '101/2012/NĐ-CP') hoặc id nội bộ của cổng.",
            }
        },
        "required": ["query_or_id"],
    },
)
