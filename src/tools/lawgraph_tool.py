"""LawGraph Traversal and Retrieval Tools for LegalPilot-VN (Google ADK compliant).

Provides ADK tools for:
- trace_selective_edge: Targeted Cypher traversal over AMENDS/SUPERSEDES edges
  with temporal pruning to resolve active legal amendments.
- query_lawgraph: Hybrid retrieval combining statutory knowledge catalog and graph lookup.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ToolDefinition
from src.core.logger import logger


def trace_selective_edge(
    seed_doc_id: str,
    reference_date: str = "",
) -> dict[str, Any]:
    """Traces selective edges for a legal document to resolve amendments and active provisions.

    Traverses AMENDS and SUPERSEDES relationships, pruning provisions that are
    expired, superseded, or not yet in force at the reference date.

    Args:
        seed_doc_id: The identifier of the document to inspect (e.g. '152/2020/ND-CP').
        reference_date: The date against which to check validity (YYYY-MM-DD). Defaults to today.

    Returns:
        Structured dictionary containing active articles, amendment chains,
        repealed provisions, and pruning metrics.
    """
    from src.knowledge.selective_traversal import SelectiveTraversalEngine, TraversalContext

    logger.info("Executing trace_selective_edge tool for doc: %s", seed_doc_id)
    try:
        engine = SelectiveTraversalEngine()
        context = (
            TraversalContext(reference_date=reference_date)
            if reference_date
            else TraversalContext()
        )
        result = engine.traverse(seed_doc_id=seed_doc_id, context=context)
        return {
            "seed_doc_id": result.seed_doc_id,
            "reference_date": result.reference_date,
            "active_articles": result.active_articles,
            "amendment_chains": result.amendment_chains,
            "repealed_provisions": result.repealed_provisions,
            "traversed_nodes_count": result.traversed_nodes_count,
            "pruned_nodes_count": result.pruned_nodes_count,
            "noise_reduction_ratio": result.noise_reduction_ratio,
        }
    except Exception as e:
        logger.warning(
            "Live Neo4j traversal failed for %s (%s). Falling back to catalog.",
            seed_doc_id,
            e,
        )
        from src.agents.lawgraph import LawGraphAgent

        doc = LawGraphAgent.STATUTE_CATALOG.get(seed_doc_id)
        if doc:
            return {
                "seed_doc_id": seed_doc_id,
                "reference_date": reference_date or doc.get("effective_date", ""),
                "active_articles": doc.get("articles", []),
                "amendment_chains": [],
                "repealed_provisions": [{"doc_id": doc.get("revoked_by")}]
                if doc.get("revoked_by")
                else [],
                "traversed_nodes_count": 1,
                "pruned_nodes_count": 0,
                "noise_reduction_ratio": 0.0,
            }
        return {
            "seed_doc_id": seed_doc_id,
            "error": str(e),
            "active_articles": [],
            "amendment_chains": [],
            "repealed_provisions": [],
            "noise_reduction_ratio": 0.0,
        }


def query_lawgraph(
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Performs statutory retrieval across LawGraph using keywords and subgoals.

    Args:
        query: Legal question or statutory keyword string.
        top_k: Maximum number of provisions to retrieve.

    Returns:
        List of matching legal articles and active provisions.
    """
    from src.agents.lawgraph import LawGraphAgent

    agent = LawGraphAgent()
    keywords = [w for w in query.split() if len(w) > 2]
    provisions = agent.retrieve_provisions(subgoals=[query], keywords=keywords)
    return provisions[:top_k]


TRACE_SELECTIVE_EDGE_TOOL = ToolDefinition(
    name="trace_selective_edge",
    description="Duyệt đồ thị pháp lý có chọn lọc (Selective Edge Traversal) qua các quan hệ AMENDS và SUPERSEDES, cắt tỉa điều khoản hết hiệu lực.",
    func=trace_selective_edge,
    parameters_schema={
        "type": "object",
        "properties": {
            "seed_doc_id": {
                "type": "string",
                "description": "Số hiệu văn bản gốc cần duyệt (ví dụ: '152/2020/ND-CP').",
            },
            "reference_date": {
                "type": "string",
                "description": "Mốc ngày đánh giá hiệu lực định dạng YYYY-MM-DD (để trống sẽ lấy ngày hiện tại).",
            },
        },
        "required": ["seed_doc_id"],
    },
)

QUERY_LAWGRAPH_TOOL = ToolDefinition(
    name="query_lawgraph",
    description="Truy vấn tri thức pháp điển LawGraph kết hợp giữa đồ thị quan hệ và danh mục văn bản quy phạm pháp luật.",
    func=query_lawgraph,
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Nội dung truy vấn hoặc từ khoá pháp lý.",
            },
            "top_k": {
                "type": "integer",
                "description": "Số lượng điều khoản tối đa cần lấy về (mặc định: 5).",
            },
        },
        "required": ["query"],
    },
)
