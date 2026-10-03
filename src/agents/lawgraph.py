"""LawGraph Agent: Retrieves and traverses Vietnamese legal statutes and decrees.

Handles knowledge retrieval using statutory catalog and graph traversal logic,
resolving amendment chains and temporal validity bounds. Compliant with Google ADK.
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.agents.base import ADKAgent
from src.core.logger import logger


class LawGraphAgent(ADKAgent):
    """Agent responsible for statutory retrieval and legal graph traversal."""

    # Built-in knowledge catalog for core Vietnamese business & administrative regulations
    STATUTE_CATALOG: ClassVar[dict[str, dict[str, Any]]] = {
        "52/2024/ND-CP": {
            "doc_id": "52/2024/ND-CP",
            "title": "Nghị định 52/2024/NĐ-CP về thanh toán không dùng tiền mặt",
            "issue_date": "2024-05-15",
            "effective_date": "2024-07-01",
            "status": "active",
            "supersedes": ["101/2012/ND-CP", "80/2016/ND-CP"],
            "articles": [
                {
                    "article": "Điều 22",
                    "title": "Điều kiện cung ứng dịch vụ trung gian thanh toán (Ví điện tử)",
                    "content": (
                        "Tổ chức không phải là ngân hàng muốn cung ứng dịch vụ ví điện tử phải đáp ứng: "
                        "1. Có vốn điều lệ tối thiểu 50.000.000.000 VNĐ (50 tỷ đồng); "
                        "2. Có đề án cung ứng dịch vụ phù hợp; "
                        "3. Người đại diện theo pháp luật, Tổng giám đốc phải có trình độ chuyên môn hoặc kinh nghiệm quản lý."
                    ),
                    "capital_vnd": 50_000_000_000,
                },
                {
                    "article": "Điều 23",
                    "title": "Tỷ lệ tham gia của nhà đầu tư nước ngoài",
                    "content": (
                        "Tổ chức cung ứng dịch vụ trung gian thanh toán có vốn đầu tư nước ngoài "
                        "phải tuân thủ tỷ lệ sở hữu tối đa và điều kiện tiếp cận thị trường theo cam kết WTO và pháp luật đầu tư."
                    ),
                    "foreign_ownership_cap": 0.49,
                },
            ],
        },
        "101/2012/ND-CP": {
            "doc_id": "101/2012/ND-CP",
            "title": "Nghị định 101/2012/NĐ-CP về thanh toán không dùng tiền mặt (CŨ)",
            "issue_date": "2012-11-22",
            "effective_date": "2013-03-01",
            "status": "expired",
            "revoked_by": "52/2024/ND-CP",
            "revoked_date": "2024-07-01",
            "articles": [
                {
                    "article": "Điều 15",
                    "title": "Điều kiện cấp Giấy phép (ĐÃ BÃI BỎ)",
                    "content": "Vốn điều lệ tối thiểu 50 tỷ đồng. (Quy định cũ theo NĐ 101/2012/NĐ-CP đã hết hiệu lực từ 01/07/2024).",
                }
            ],
        },
        "70/2023/ND-CP": {
            "doc_id": "70/2023/ND-CP",
            "title": "Nghị định 70/2023/NĐ-CP sửa đổi Nghị định 152/2020/NĐ-CP về lao động nước ngoài",
            "issue_date": "2023-09-18",
            "effective_date": "2023-09-18",
            "status": "active",
            "amends": "152/2020/ND-CP",
            "articles": [
                {
                    "article": "Điều 1 Khoản 5",
                    "title": "Điều kiện cấp Giấy phép lao động cho Chuyên gia nước ngoài",
                    "content": (
                        "Có bằng đại học trở lên hoặc tương đương và có ít nhất 3 năm kinh nghiệm làm việc "
                        "phù hợp với vị trí công việc mà người lao động nước ngoài dự kiến làm việc tại Việt Nam."
                    ),
                }
            ],
        },
        "168/2024/ND-CP": {
            "doc_id": "168/2024/ND-CP",
            "title": "Nghị định 168/2024/NĐ-CP xử phạt vi phạm hành chính trật tự ATGT đường bộ",
            "issue_date": "2024-12-26",
            "effective_date": "2025-01-01",
            "status": "active",
            "supersedes": ["100/2019/ND-CP", "123/2021/ND-CP"],
            "articles": [
                {
                    "article": "Điều 6 Khoản 4",
                    "title": "Xử phạt người điều khiển xe mô tô, xe gắn máy vượt đèn đỏ",
                    "content": "Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng đối với người điều khiển xe mô tô, xe gắn máy không chấp hành hiệu lệnh của đèn tín hiệu giao thông (vượt đèn đỏ). Tước GPLX từ 01 đến 03 tháng.",
                    "sanction_range": "4.000.000 - 6.000.000 VNĐ",
                }
            ],
        },
        "100/2019/ND-CP": {
            "doc_id": "100/2019/ND-CP",
            "title": "Nghị định 100/2019/NĐ-CP xử phạt vi phạm giao thông đường bộ (CŨ)",
            "issue_date": "2019-12-30",
            "effective_date": "2020-01-01",
            "status": "expired",
            "revoked_by": "168/2024/ND-CP",
            "revoked_date": "2025-01-01",
            "articles": [
                {
                    "article": "Điều 6 Khoản 4 Điểm e",
                    "title": "Vượt đèn đỏ xe máy (CŨ)",
                    "content": "Phạt tiền từ 800.000 đồng đến 1.000.000 đồng đối với hành vi vượt đèn đỏ (đã bị bãi bỏ bởi Nghị định 168/2024/NĐ-CP từ 01/01/2025).",
                    "sanction_range": "800.000 - 1.000.000 VNĐ",
                }
            ],
        },
    }

    def __init__(
        self,
        traversal_engine: Any | None = None,
        qdrant_manager: Any | None = None,
        use_live_db: bool = False,
    ) -> None:
        import json
        from pathlib import Path
        from src.tools.lawgraph_tool import QUERY_LAWGRAPH_TOOL, TRACE_SELECTIVE_EDGE_TOOL
        from src.tools.statutory_retriever import STATUTORY_RETRIEVER_TOOL
        from src.tools.validity_checker import VALIDITY_CHECKER_TOOL

        super().__init__(
            name="LawGraphAgent",
            description="Truy vấn văn bản luật, nghị định, thông tư và duyệt đồ thị quan hệ sửa đổi/bổ sung.",
            role="retriever",
            tools=[
                STATUTORY_RETRIEVER_TOOL,
                VALIDITY_CHECKER_TOOL,
                TRACE_SELECTIVE_EDGE_TOOL,
                QUERY_LAWGRAPH_TOOL,
            ],
        )
        self.traversal_engine = traversal_engine
        self.qdrant_manager = qdrant_manager
        self.use_live_db = use_live_db

        # Dynamically load documents ingested into local processed graph export
        export_file = Path("data/processed/neo4j_graph_export.json")
        if export_file.exists():
            try:
                exported_data = json.loads(export_file.read_text(encoding="utf-8"))
                for doc_id, doc in exported_data.items():
                    if doc_id not in self.STATUTE_CATALOG:
                        self.STATUTE_CATALOG[doc_id] = doc
            except Exception as e:
                logger.warning("Could not load neo4j_graph_export.json: %s", e)

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes statutory retrieval via standard ADK interface."""
        if isinstance(input_data, dict):
            subgoals = input_data.get("subgoals", [])
            keywords = input_data.get("keywords", [])
            reference_date = input_data.get("reference_date", "")
        elif isinstance(input_data, str):
            subgoals = [input_data]
            keywords = [input_data]
            reference_date = ""
        else:
            subgoals, keywords = [], []
            reference_date = ""
        return self.retrieve_provisions(subgoals, keywords, reference_date=reference_date)

    def trace_selective_edge(
        self,
        seed_doc_id: str,
        reference_date: str = "",
    ) -> dict[str, Any]:
        """Traces selective edges for a seed document using selective edge traversal."""
        from src.tools.lawgraph_tool import trace_selective_edge

        return trace_selective_edge(seed_doc_id=seed_doc_id, reference_date=reference_date)

    def _retrieve_from_live_graph(
        self,
        subgoals: list[str],
        keywords: list[str],
        reference_date: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieves provisions by traversing Neo4j knowledge graph with temporal pruning."""
        try:
            import re

            from src.knowledge.selective_traversal import SelectiveTraversalEngine, TraversalContext

            engine = self.traversal_engine or SelectiveTraversalEngine()
            context = (
                TraversalContext(reference_date=reference_date)
                if reference_date
                else TraversalContext()
            )

            doc_candidates: set[str] = set()
            pattern = re.compile(r"\b\d+/\d{4}/[A-Za-z0-9Đđ/-]+\b", re.IGNORECASE)

            full_text = " ".join(subgoals + keywords)
            for m in pattern.finditer(full_text):
                clean_id = m.group(0).upper().replace("Đ", "D").replace("đ", "d")
                doc_candidates.add(clean_id)

            if not doc_candidates and hasattr(engine, "client"):
                for kw in keywords:
                    if len(kw) < 4:
                        continue
                    try:
                        records = engine.client.execute_query(
                            "MATCH (d:Document) WHERE d.title CONTAINS $kw RETURN d.doc_id as doc_id LIMIT 3",
                            {"kw": kw},
                        )
                        for r in records:
                            if r.get("doc_id"):
                                doc_candidates.add(str(r["doc_id"]))
                    except Exception:
                        pass

            live_provisions: list[dict[str, Any]] = []
            for doc_id in doc_candidates:
                try:
                    res = engine.traverse(doc_id, context)
                    for art in res.active_articles:
                        live_provisions.append(
                            {
                                "doc_id": art.get("governing_doc_id", doc_id),
                                "title": f"Văn bản {art.get('governing_doc_id', doc_id)}",
                                "status": "active",
                                "effective_date": res.reference_date,
                                "article": f"Điều {art.get('article_number', '')}",
                                "article_title": art.get("title", ""),
                                "content": art.get("content", ""),
                                "amended_by": art.get("amended_by"),
                                "supersedes": [
                                    r.get("repealer_doc_id") for r in res.repealed_provisions
                                ],
                                "revoked_by": None,
                            }
                        )
                except Exception as ex:
                    logger.debug("Selective traversal skipped for %s: %s", doc_id, ex)

            return live_provisions
        except Exception as e:
            logger.debug("Live graph retrieval unavailable: %s", e)
            return []

    def retrieve_provisions(
        self,
        subgoals: list[str],
        keywords: list[str],
        reference_date: str = "",
        force_live_db: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieves relevant legal articles based on subgoals and keyword matches."""
        logger.info(f"LawGraphAgent: Retrieving provisions for subgoals: {subgoals}")
        results: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        search_terms = [k.lower() for k in keywords]

        for doc_id, doc in self.STATUTE_CATALOG.items():
            doc_text = f"{doc['title']} {doc['doc_id']}".lower()

            for article in doc["articles"]:
                art_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
                combined = f"{doc_text} {art_text}"

                is_match = any(term in combined for term in search_terms) or not search_terms
                if is_match:
                    item_key = f"{doc_id}:{article.get('article', '')}"
                    if item_key not in seen_keys:
                        seen_keys.add(item_key)
                        results.append(
                            {
                                "doc_id": doc["doc_id"],
                                "title": doc["title"],
                                "status": doc["status"],
                                "effective_date": doc["effective_date"],
                                "article": article["article"],
                                "article_title": article["title"],
                                "content": article["content"],
                                "supersedes": doc.get("supersedes", []),
                                "revoked_by": doc.get("revoked_by"),
                            }
                        )

        # If live database is requested or catalog had no results, attempt dynamic graph retrieval
        if (self.use_live_db or force_live_db) or not results:
            live_results = self._retrieve_from_live_graph(subgoals, keywords, reference_date)
            for item in live_results:
                item_key = f"{item['doc_id']}:{item['article']}"
                if item_key not in seen_keys:
                    seen_keys.add(item_key)
                    results.append(item)

        logger.info(f"LawGraphAgent: Found {len(results)} candidate provisions.")
        return results
