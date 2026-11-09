"""Tests cho cổng kiểm định trước khi ghi graph."""

from src.knowledge.validate import count_articles_in_raw, validate_document

RAW = (
    "Điều 1. Phạm vi điều chỉnh\n" + "nội dung " * 40 + "\n"
    "Điều 2. Đối tượng áp dụng\n" + "nội dung " * 40 + "\n"
    "Điều 3. Hiệu lực thi hành\n" + "nội dung " * 40 + "\n"
)

GOOD = {
    "doc_id": "52/2024/NĐ-CP",
    "title": "Quy định về thanh toán không dùng tiền mặt",
    "articles": [
        {"article_number": "1", "title": "Phạm vi điều chỉnh", "content": "a" * 300},
        {"article_number": "2", "title": "Đối tượng áp dụng", "content": "b" * 300},
        {"article_number": "3", "title": "Hiệu lực thi hành", "content": "c" * 300},
    ],
    "effective_date": "2024-07-01",
}


def _codes(rep) -> set[str]:
    return {i.code for i in rep.issues}


class TestValidateDocument:
    def test_good_document_passes(self) -> None:
        rep = validate_document(GOOD, raw_text=RAW)
        assert rep.passed
        assert rep.issues == []

    def test_duplicate_doc_is_blocked(self) -> None:
        rep = validate_document(GOOD, known_doc_ids={"52/2024/ND-CP"}, raw_text=RAW)
        assert not rep.passed
        assert "V2_DUPLICATE_DOC" in _codes(rep)

    def test_duplicate_allowed_when_replace(self) -> None:
        rep = validate_document(
            GOOD, known_doc_ids={"52/2024/ND-CP"}, raw_text=RAW, allow_replace=True
        )
        assert rep.passed

    def test_placeholder_titles_are_blocked(self) -> None:
        bad = {
            **GOOD,
            "articles": [
                {"article_number": "1", "title": "Quy định tại 52/2024/ND-CP", "content": "a" * 300},
                {"article_number": "2", "title": "Quy định tại 52/2024/ND-CP", "content": "b" * 300},
            ],
        }
        rep = validate_document(bad, raw_text=RAW)
        assert not rep.passed
        assert "V4_PLACEHOLDER_TITLE" in _codes(rep)

    def test_incomplete_structure_is_blocked(self) -> None:
        bad = {**GOOD, "articles": GOOD["articles"][:1]}   # 1/3 điều
        rep = validate_document(bad, raw_text=RAW)
        assert not rep.passed
        assert "V5_INCOMPLETE_STRUCTURE" in _codes(rep)

    def test_no_articles_is_blocked(self) -> None:
        rep = validate_document({**GOOD, "articles": []}, raw_text=RAW)
        assert not rep.passed
        assert "V3_NO_ARTICLES" in _codes(rep)

    def test_bad_doc_id_is_blocked(self) -> None:
        rep = validate_document({**GOOD, "doc_id": "không phải số hiệu"}, raw_text=RAW)
        assert not rep.passed
        assert "V1_BAD_DOC_ID" in _codes(rep)

    def test_short_content_is_only_warning(self) -> None:
        doc = {
            **GOOD,
            "articles": [
                {"article_number": str(i), "title": f"Điều {i}", "content": "ngắn"}
                for i in (1, 2, 3)
            ],
        }
        rep = validate_document(doc, raw_text=RAW)
        assert "V4_SHORT_CONTENT" in _codes(rep)
        # không có lỗi error nào -> vẫn cho qua
        assert all(i.severity == "warn" for i in rep.issues if i.code == "V4_SHORT_CONTENT")

    def test_dangling_cross_ref_is_warning(self) -> None:
        doc = {**GOOD, "cross_refs": [{"target_doc_id": "99/1999/ND-CP"}]}
        rep = validate_document(doc, known_doc_ids=set(), raw_text=RAW)
        assert "V6_DANGLING_CROSS_REF" in _codes(rep)
        assert rep.passed   # chỉ cảnh báo

    def test_duplicated_content_is_blocked(self) -> None:
        same = "nội dung giống hệt " * 30
        doc = {
            **GOOD,
            "articles": [
                {"article_number": str(i), "title": f"Điều {i}", "content": same}
                for i in (1, 2, 3)
            ],
        }
        rep = validate_document(doc, raw_text=RAW)
        assert "V4_DUPLICATED_CONTENT" in _codes(rep)
        assert not rep.passed

    def test_report_serialises(self) -> None:
        rep = validate_document(GOOD, raw_text=RAW).to_dict()
        assert set(rep) == {"doc_id", "passed", "issues", "stats"}
        assert rep["doc_id"] == "52/2024/ND-CP"

    def test_count_articles(self) -> None:
        assert count_articles_in_raw(RAW) == 3
        assert count_articles_in_raw("") == 0
