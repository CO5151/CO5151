"""Tests cho cổng kiểm chứng câu trả lời và chuẩn hoá mã văn bản."""

from src.core.doc_ids import canonical_doc_id, is_doc_code
from src.security.answer_gate import (
    ABSTAIN_MSG,
    allowed_from_clauses,
    extract_citations,
    gate_answer,
)


class TestCanonicalDocId:
    def test_unicode_variant_collapses(self) -> None:
        # Đây là lỗi thật: graph từng có cả hai node cho cùng một nghị định.
        assert canonical_doc_id("52/2024/NĐ-CP") == canonical_doc_id("52/2024/ND-CP")

    def test_is_idempotent(self) -> None:
        once = canonical_doc_id("52/2024/nđ-cp")
        assert canonical_doc_id(once) == once

    def test_strips_spaces_and_dashes(self) -> None:
        assert canonical_doc_id(" 152/2020/NĐ–CP ") == "152/2020/ND-CP"

    def test_empty_input(self) -> None:
        assert canonical_doc_id("") == ""
        assert canonical_doc_id(None) == ""

    def test_doc_code_vs_law_name(self) -> None:
        assert is_doc_code("52/2024/ND-CP")
        assert not is_doc_code("Luật Các tổ chức tín dụng")


class TestAnswerGate:
    def setup_method(self) -> None:
        self.allowed = allowed_from_clauses([{"doc_id": "52/2024/NĐ-CP", "article": "Điều 22"}])

    def test_citation_not_in_context_is_blocked(self) -> None:
        ok, reason, bad = gate_answer("Theo Điều 99 Nghị định 52/2024/ND-CP, ...", self.allowed)
        assert ok is False
        assert bad == [("99", "52/2024/ND-CP")]
        assert "52/2024" in reason

    def test_citation_in_context_passes(self) -> None:
        ok, _, bad = gate_answer("Theo Điều 22 Nghị định 52/2024/ND-CP, ...", self.allowed)
        assert ok is True
        assert bad == []

    def test_answer_without_citation_is_blocked(self) -> None:
        ok, reason, _ = gate_answer("Doanh nghiệp cần làm hồ sơ.", self.allowed)
        assert ok is False
        assert "không có dẫn chiếu" in reason

    def test_empty_answer_is_blocked(self) -> None:
        ok, _, _ = gate_answer("   ", self.allowed)
        assert ok is False

    def test_refuting_a_wrong_citation_is_allowed(self) -> None:
        # Nhắc điều sai ĐỂ BÁC nó không phải là khẳng định điều sai.
        ok, _, _ = gate_answer(
            "Tài liệu ghi là Điều 22 Nghị định 52/2024/ND-CP, "
            "không phải Điều 99 Nghị định 52/2024/ND-CP.",
            self.allowed,
        )
        assert ok is True

    def test_revoked_document_mention_is_allowed_with_valid_basis(self) -> None:
        ok, _, _ = gate_answer(
            "Theo Điều 22 Nghị định 52/2024/ND-CP; Điều 15 Nghị định 101/2012/ND-CP đã hết hiệu lực.",
            self.allowed,
        )
        assert ok is True

    def test_only_revoked_citations_is_blocked(self) -> None:
        ok, reason, _ = gate_answer(
            "Theo Điều 15 Nghị định 101/2012/ND-CP.", self.allowed
        )
        assert ok is False
        assert "101/2012/ND-CP" in reason

    def test_markdown_bold_citations_are_parsed(self) -> None:
        ok, _, _ = gate_answer("Căn cứ **Điều 22** Nghị định **52/2024/NĐ-CP**.", self.allowed)
        assert ok is True

    def test_extract_returns_pairs(self) -> None:
        assert extract_citations("Điều 22 Nghị định 52/2024/NĐ-CP") == {("22", "52/2024/ND-CP")}

    def test_abstain_message_is_vietnamese(self) -> None:
        assert "không đủ căn cứ" in ABSTAIN_MSG
