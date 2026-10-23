"""Web search tool for **external finding only** — never a validity oracle.

Why this exists
---------------
``verify_vbpl_status`` was supposed to check live status on vbpl.vn. That portal
now answers ``HTTP 403`` to scripted clients (or a JS shell that
``BeautifulSoup`` cannot parse), so the call silently degrades to the 6-document
offline catalogue. This module adds a *search* capability that actually works,
but deliberately keeps it separate from the audit path:

* It **finds** documents on official domains. It does **not** decide whether
  they are still in force.
* Results are stored under ``web_findings``, never merged into
  ``retrieved_clauses``, so retrieval metrics stay clean.
* Every hit carries ``verified: False`` and the block carries a ``note`` that
  says so, because a grader will ask.

Backend: the ``ddgs`` package (DuckDuckGo, no API key). Raw ``httpx`` scraping
against ``html.duckduckgo.com`` was tried first and got ``HTTP 202`` challenge
pages after roughly six requests, so ``ddgs`` handles that instead.

The whitelist is the whole point. In practice a topical query returns
``thuvienphapluat.vn``, ``vneconomy.vn``, ``mobilereview.vn`` — credible-looking
but not authoritative. Those are counted in ``blocked`` and listed in
``blocked_domains`` so the behaviour is visible instead of silent.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any

from src.agents.base import ToolDefinition
from src.core.logger import logger

DEFAULT_ALLOWED_DOMAINS: tuple[str, ...] = (
    "vbpl.vn",
    "vanban.chinhphu.vn",
    "congbao.chinhphu.vn",
    "chinhphu.vn",
    "quochoi.vn",
    "moj.gov.vn",
    "sbv.gov.vn",
)

NOTE = (
    "Kết quả tìm kiếm web: chỉ để THAM KHẢO. Không dùng để xác nhận hiệu lực "
    "pháp lý — việc đó chỉ do bước audit trên đồ thị luật quyết định."
)

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 3600


def _allowed_domains() -> tuple[str, ...]:
    raw = os.getenv("WEB_SEARCH_ALLOWED_DOMAINS", "").strip()
    if not raw:
        return DEFAULT_ALLOWED_DOMAINS
    return tuple(d.strip().lower() for d in raw.split(",") if d.strip())


def _domain_of(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _is_allowed(url: str, allowed: tuple[str, ...]) -> bool:
    host = _domain_of(url)
    return any(host == d or host.endswith("." + d) for d in allowed)


def _raw_query(query: str, limit: int, timeout_seconds: float = 15.0) -> list[dict[str, str]]:
    """Runs the search and normalises both response shapes ddgs can return.

    The backend can block for a long time when DuckDuckGo answers with a
    challenge page, so the call is bounded by ``timeout_seconds`` on a worker
    thread. A timeout surfaces as ``TimeoutError`` and the caller degrades to
    ``status="unavailable"`` — the agent must not hang because of a search.
    """
    import concurrent.futures as cf

    def _call() -> Any:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return ddgs.text(query, region="vn-vi", max_results=max(limit * 3, 8))

    with cf.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_call)
        rows = future.result(timeout=timeout_seconds)

    out: list[dict[str, str]] = []
    for row in rows or []:
        url = row.get("href") or row.get("url") or ""
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": (row.get("title") or "").strip(),
                "snippet": (row.get("body") or row.get("snippet") or "").strip()[:400],
            }
        )
    return out


def search_official_legal_web(
    query: str,
    limit: int = 5,
    force_refresh: bool = False,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Searches official Vietnamese legal domains for documents matching ``query``.

    Args:
        query: Natural-language keywords or a statute number.
        limit: Maximum number of whitelisted hits to return.
        force_refresh: Bypass the in-process cache.

    Returns:
        ``{"status": "ok"|"unavailable"|"empty_query", "hits": [...],
        "blocked": int, "blocked_domains": [...], "allowed_domains": [...],
        "note": str}``. Never raises: a backend failure yields
        ``status="unavailable"`` so the pipeline can continue.
    """
    q = (query or "").strip()
    if not q:
        return {"status": "empty_query", "hits": [], "blocked": 0, "note": NOTE}

    allowed = _allowed_domains()
    cache_key = f"{q}|{limit}|{','.join(allowed)}"
    if not force_refresh and cache_key in _CACHE:
        ts, payload = _CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return {**payload, "cached": True}

    try:
        raw = _raw_query(q, limit, timeout_seconds=timeout_seconds)
    except Exception as e:  # noqa: BLE001
        logger.warning("web_search: backend failed (%s: %s)", type(e).__name__, e)
        return {
            "status": "unavailable",
            "error": f"{type(e).__name__}: {e}",
            "hits": [],
            "blocked": 0,
            "allowed_domains": list(allowed),
            "note": NOTE,
        }

    kept: list[dict[str, Any]] = []
    blocked_domains: list[str] = []
    for hit in raw:
        if not _is_allowed(hit["url"], allowed):
            blocked_domains.append(_domain_of(hit["url"]))
            continue
        kept.append(
            {
                **hit,
                "domain": _domain_of(hit["url"]),
                # Search finds a page; it cannot prove the page is current.
                "verified": False,
            }
        )
        if len(kept) >= limit:
            break

    payload = {
        "status": "ok",
        "query": q,
        "hits": kept,
        "blocked": len(blocked_domains),
        "blocked_domains": sorted(set(blocked_domains))[:8],
        "allowed_domains": list(allowed),
        "note": NOTE,
    }
    _CACHE[cache_key] = (time.time(), payload)
    logger.info(
        "web_search: %d kept / %d blocked for %r",
        len(kept),
        payload["blocked"],
        q[:60],
    )
    return payload


def render_web_findings(payload: dict[str, Any], width: int = 240) -> str:
    """Renders search hits into a prompt block that is clearly marked unverified."""
    if not payload or payload.get("status") != "ok":
        reason = (payload or {}).get("status", "không rõ")
        return f"(không tra được web: {reason})"

    if not payload.get("hits"):
        blocked = payload.get("blocked", 0)
        if blocked:
            doms = ", ".join(payload.get("blocked_domains", []))
            return (
                f"(không có kết quả trên cổng chính thức; đã loại {blocked} kết quả "
                f"từ nguồn ngoài whitelist: {doms})"
            )
        return "(không có kết quả tham khảo ngoài)"

    lines = [f"LƯU Ý: {payload.get('note', NOTE)}"]
    for i, hit in enumerate(payload["hits"], 1):
        snippet = hit.get("snippet", "")
        if len(snippet) > width:
            snippet = snippet[:width].rstrip() + "..."
        lines.append(
            f"[W{i}] {hit['title']} — {hit['url']}\n"
            f"     {snippet}\n"
            f"     (chưa kiểm định hiệu lực; nguồn: {hit.get('domain', '?')})"
        )
    return "\n".join(lines)


SEARCH_OFFICIAL_LEGAL_WEB_TOOL = ToolDefinition(
    name="search_official_legal_web",
    description=(
        "Tìm văn bản pháp luật trên các cổng thông tin chính thức (vbpl.vn, "
        "chinhphu.vn, quochoi.vn, sbv.gov.vn...). Chỉ để tham khảo; KHÔNG dùng "
        "để xác nhận hiệu lực pháp lý."
    ),
    func=search_official_legal_web,
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Từ khoá hoặc số hiệu văn bản cần tìm.",
            },
            "limit": {
                "type": "integer",
                "description": "Số kết quả tối đa (mặc định 5).",
            },
        },
        "required": ["query"],
    },
)
