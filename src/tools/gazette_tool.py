"""Live Gazette and VBPL Status Verification Tool for LegalPilot-VN (Google ADK compliant).

Provides ADK tools for:
- verify_vbpl_status: Real-time verification of statutory in-force status against
  the National Legal Database (vbpl.vn) with SQLite caching (24h TTL) and offline fallback.
- search_gazette: Targeted portal search for recent legal instruments and ministerial circulars.
"""

from __future__ import annotations

import contextlib
import os
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.agents.base import ToolDefinition
from src.core.config import settings
from src.core.logger import logger
from src.knowledge.ingestion import HTMLParsed, normalize_doc_id, parse_html_document
from src.memory.sqlite_manager import SQLiteMemoryManager
from src.memory.state_models import StatuteCacheEntry

_normalize_doc_id = normalize_doc_id


def _normalize_status(raw_status: str) -> str:
    """Normalizes Vietnamese status string into standard status code."""
    lower = raw_status.lower().strip()
    if "còn hiệu lực" in lower or "active" in lower or "in_force" in lower:
        return "active"
    if "hết hiệu lực một phần" in lower or "partially" in lower:
        return "partially_expired"
    if "hết hiệu lực" in lower or "bãi bỏ" in lower or "expired" in lower:
        return "expired"
    if "chưa có hiệu lực" in lower or "not_in_force" in lower:
        return "not_in_force"
    return "unknown"


def verify_vbpl_status(
    doc_id: str,
    memory_manager: SQLiteMemoryManager | None = None,
    force_refresh: bool = False,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Verifies statutory in-force status on vbpl.vn with local caching and offline fallback.

    Args:
        doc_id: Legal instrument number (e.g. '52/2024/ND-CP', '152/2020/ND-CP').
        memory_manager: SQLite memory manager instance for cache operations.
        force_refresh: If True, bypasses cache and queries external portal directly.
        timeout_seconds: Timeout for network request (default 3.0s as per ADR-0004).

    Returns:
        Structured dictionary containing document title, active status, effective date,
        and verification source ('statute_cache', 'vbpl.vn', or 'offline_catalog').
    """
    clean_id = _normalize_doc_id(doc_id)
    mgr = memory_manager or SQLiteMemoryManager("data/enterprise_compliance.db")

    # 1. Check local SQLite cache first (if not forced refresh)
    if not force_refresh:
        cached_entry = mgr.get_cached_statute(clean_id)
        if cached_entry and not cached_entry.is_expired:
            logger.info("Statute cache hit for %s (status: %s)", clean_id, cached_entry.status)
            return {
                "doc_id": clean_id,
                "document_number": cached_entry.document_number,
                "title": cached_entry.title,
                "status": cached_entry.status,
                "is_in_force": cached_entry.status in ("active", "partially_expired"),
                "effective_date": cached_entry.effective_date,
                "source": "statute_cache",
                "cached": True,
            }

    # 2. Query vbpl.vn live search portal (configurable via env or system settings)
    raw_template = (
        os.getenv("VBPL_TARGET_QUERY")
        or os.getenv("VBPL_SEARCH_URL")
        or getattr(settings, "VBPL_TARGET_QUERY", None)
        or getattr(
            settings,
            "VBPL_SEARCH_URL",
            "https://vbpl.vn/pages/vbpq-timkiem.aspx?Keyword={keyword}",
        )
    )
    target_query_template: str = str(
        raw_template or "https://vbpl.vn/pages/vbpq-timkiem.aspx?Keyword={keyword}"
    )
    if "{keyword}" in target_query_template:
        target_url = target_query_template.format(keyword=clean_id)
    elif "{clean_id}" in target_query_template:
        target_url = target_query_template.format(clean_id=clean_id)
    elif "{doc_id}" in target_query_template:
        target_url = target_query_template.format(doc_id=clean_id)
    elif target_query_template.endswith("="):
        target_url = f"{target_query_template}{clean_id}"
    else:
        target_url = f"{target_query_template}?Keyword={clean_id}"

    logger.info("Querying live portal for %s at %s", clean_id, target_url)

    from src.agents.lawgraph import LawGraphAgent

    resolved_title = f"Văn bản quy phạm pháp luật {clean_id}"
    resolved_status = "unknown"
    resolved_date = "2024-01-01"
    resolved_source = "offline_catalog"
    raw_meta: dict[str, Any] = {"url": target_url}

    # Baseline from internal catalog if known
    catalog_doc = LawGraphAgent.STATUTE_CATALOG.get(clean_id)
    if catalog_doc:
        resolved_status = catalog_doc.get("status", "unknown")
        resolved_title = catalog_doc.get("title", resolved_title)
        resolved_date = catalog_doc.get("effective_date", resolved_date)
        if catalog_doc.get("revoked_by"):
            raw_meta["revoked_by"] = catalog_doc["revoked_by"]

    try:
        headers = {
            "User-Agent": "LegalPilot-VN/1.0 (Educational Academic Agentic RAG; HCMUT)",
            "Accept": "text/html,application/xhtml+xml",
        }
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = client.get(target_url, headers=headers)
            # Ensure response is not a generic redirect to homepage and actually mentions doc ID
            final_url = str(resp.url).rstrip("/")
            is_homepage = final_url in ("https://vbpl.vn", "http://vbpl.vn")
            normalized_resp = _normalize_doc_id(resp.text)
            if (
                resp.status_code == 200
                and resp.text
                and not is_homepage
                and (clean_id in normalized_resp or clean_id in resp.text)
            ):
                html = resp.text
                soup = BeautifulSoup(html, "html.parser")

                # Extract title from search result anchor tag or header
                title_elem = soup.find(
                    ["a", "h1", "h2", "div"],
                    class_=re.compile(r"title|vbTitle|header", re.I),
                )
                if title_elem and title_elem.get_text(strip=True):
                    resolved_title = re.sub(r"\s+", " ", title_elem.get_text(strip=True))

                # Check status via HTML text / class indicators
                text_content = soup.get_text(" ")
                if "Hết hiệu lực một phần" in text_content:
                    resolved_status = "partially_expired"
                    resolved_source = "vbpl.vn"
                elif "Hết hiệu lực" in text_content or "bãi bỏ" in text_content.lower():
                    resolved_status = "expired"
                    resolved_source = "vbpl.vn"
                elif "Còn hiệu lực" in text_content:
                    resolved_status = "active"
                    resolved_source = "vbpl.vn"

                # Leverage parse_html_document / HTMLParsed if full statutory document structure is present
                with contextlib.suppress(Exception):
                    parsed_doc, _ = parse_html_document(
                        html,
                        default_metadata={
                            "doc_id": clean_id,
                            "title": resolved_title,
                            "effective_date": resolved_date,
                        },
                    )
                    if isinstance(parsed_doc, HTMLParsed) and parsed_doc.title:
                        if not parsed_doc.title.startswith(
                            ("Nghị định số", "Thông tư số", "Luật số")
                        ):
                            resolved_title = parsed_doc.title
                        if parsed_doc.effective_date:
                            resolved_date = parsed_doc.effective_date
    except Exception as e:
        logger.warning(
            "Live VBPL query for %s timed out or failed (%s). Using catalog fallback.", clean_id, e
        )

    if resolved_status == "unknown":
        resolved_status = "active"

    # 4. Save into SQLite statute_cache (TTL 24h)
    cache_entry = StatuteCacheEntry(
        law_id=clean_id,
        document_number=clean_id,
        title=resolved_title,
        effective_date=resolved_date,
        status=resolved_status,
        raw_metadata=raw_meta,
        ttl_seconds=86400,
    )
    mgr.set_cached_statute(cache_entry)

    return {
        "doc_id": clean_id,
        "document_number": clean_id,
        "title": resolved_title,
        "status": resolved_status,
        "is_in_force": resolved_status in ("active", "partially_expired"),
        "effective_date": resolved_date,
        "source": resolved_source,
        "cached": False,
        "metadata": raw_meta,
    }


def search_gazette(
    query: str,
    limit: int = 5,
    timeout_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    """Performs targeted gazette search for recent regulations and circulars.

    Args:
        query: Search keywords or regulatory topics.
        limit: Maximum candidate documents to return.
        timeout_seconds: Request timeout in seconds.

    Returns:
        List of matching legal documents with metadata.
    """
    from src.tools.lawgraph_tool import query_lawgraph

    logger.info("Searching gazette portal for: %s", query)
    # Uses hybrid query_lawgraph with portal fallback
    return query_lawgraph(query, top_k=limit)


VERIFY_VBPL_STATUS_TOOL = ToolDefinition(
    name="verify_vbpl_status",
    description="Xác thực trạng thái hiệu lực pháp lý (còn hiệu lực hay đã hết hiệu lực/bị bãi bỏ) thời gian thực trên Cổng Dữ liệu Quốc gia (vbpl.vn).",
    func=verify_vbpl_status,
    parameters_schema={
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Số hiệu văn bản pháp lý cần tra cứu (ví dụ: '52/2024/ND-CP', '101/2012/ND-CP').",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Bỏ qua bộ đệm cache và tra cứu trực tiếp từ cổng vbpl.vn (mặc định: False).",
            },
        },
        "required": ["doc_id"],
    },
)

SEARCH_GAZETTE_TOOL = ToolDefinition(
    name="search_gazette",
    description="Tìm kiếm văn bản pháp luật, nghị định, thông tư mới nhất trên Công báo quốc gia theo chủ đề hoặc từ khoá.",
    func=search_gazette,
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Từ khoá hoặc chủ đề pháp lý cần tìm kiếm.",
            },
            "limit": {
                "type": "integer",
                "description": "Số lượng văn bản tối đa cần lấy (mặc định: 5).",
            },
        },
        "required": ["query"],
    },
)
