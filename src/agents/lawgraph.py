"""LawGraph Agent: Retrieves and traverses Vietnamese legal statutes and decrees.

Handles knowledge retrieval using statutory catalog and graph traversal logic,
resolving amendment chains and temporal validity bounds. Compliant with Google ADK.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ADKAgent
from src.core.logger import logger


class LawGraphAgent(ADKAgent):
    """Agent responsible for statutory retrieval and legal graph traversal."""

    # Built-in knowledge catalog for core Vietnamese business & administrative regulations
    STATUTE_CATALOG: dict[str, dict[str, Any]] = {
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

    def __init__(self, traversal_engine: Any | None = None) -> None:
        from src.tools.statutory_retriever import STATUTORY_RETRIEVER_TOOL

        super().__init__(
            name="LawGraphAgent",
            description="Truy vấn văn bản luật, nghị định, thông tư và duyệt đồ thị quan hệ sửa đổi/bổ sung.",
            role="retriever",
            tools=[STATUTORY_RETRIEVER_TOOL],
        )
        self.traversal_engine = traversal_engine

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes statutory retrieval via standard ADK interface."""
        if isinstance(input_data, dict):
            subgoals = input_data.get("subgoals", [])
            keywords = input_data.get("keywords", [])
        elif isinstance(input_data, str):
            subgoals = [input_data]
            keywords = [input_data]
        else:
            subgoals, keywords = [], []
        return self.retrieve_provisions(subgoals, keywords)

    def retrieve_provisions(self, subgoals: list[str], keywords: list[str]) -> list[dict[str, Any]]:
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

                # Match if any search term or subgoal keyword matches
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

        logger.info(f"LawGraphAgent: Found {len(results)} candidate provisions.")
        return results
