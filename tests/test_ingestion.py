"""Unit and integration tests for Vietnamese legal ingestion pipeline."""

import contextlib
import json
from pathlib import Path

import pytest

from src.knowledge.ingestion import (
    LegalIngestionPipeline,
    apply_authoritative_metadata,
    extract_cross_references,
    generate_legal_chunks,
    llm_fallback_parse_document,
    load_sidecar_metadata,
    normalize_doc_id,
    parse_html_document,
    parse_legal_document,
)
from src.knowledge.neo4j_client import Neo4jClient
from src.knowledge.qdrant_client import QdrantClientManager

SAMPLE_TEXT = """CHÍNH PHỦ
Số: 999/2025/NĐ-CP

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
Hà Nội, ngày 15 tháng 03 năm 2025

NGHỊ ĐỊNH
Quy định chi tiết thi hành một số điều của Luật Đất đai

Căn cứ Luật Đất đai ngày 18 tháng 01 năm 2024;
Chính phủ ban hành Nghị định quy định chi tiết thi hành một số điều của Luật Đất đai.

Điều 1. Phạm vi điều chỉnh
1. Nghị định này quy định chi tiết thi hành một số điều của Luật Đất đai về bồi thường, hỗ trợ, tái định cư.
2. Việc bồi thường khi Nhà nước thu hồi đất thực hiện theo quy định pháp luật.

Điều 2. Đối tượng áp dụng
Cơ quan, tổ chức, cá nhân có liên quan đến việc bồi thường, hỗ trợ, tái định cư.
"""


def test_normalize_doc_id():
    """Tests normalization of Vietnamese legal document numbers."""
    assert normalize_doc_id("152/2020/NĐ-CP") == "152/2020/ND-CP"
    assert normalize_doc_id(" 70/2023/nđ-cp ") == "70/2023/ND-CP"
    assert normalize_doc_id("01/2024/TT-BKHĐT") == "01/2024/TT-BKHDT"


def test_parse_legal_document():
    """Tests parsing raw legal text into structured hierarchy."""
    doc = parse_legal_document(SAMPLE_TEXT)

    assert doc.doc_id == "999/2025/ND-CP"
    assert doc.issuer == "Chính Phủ"
    assert doc.doc_type == "Nghị Định"
    assert doc.issue_date == "2025-03-15"
    assert len(doc.articles) == 2

    art1 = doc.articles[0]
    assert art1.article_number == "1"
    assert art1.title == "Phạm vi điều chỉnh"
    assert len(art1.clauses) == 2
    assert art1.clauses[0].clause_number == "1"
    assert "bồi thường" in art1.clauses[0].content

    art2 = doc.articles[1]
    assert art2.article_number == "2"
    assert len(art2.clauses) == 1


def test_extract_cross_references():
    """Tests extraction of AMENDS and GUIDES relationships."""
    doc = parse_legal_document(SAMPLE_TEXT)
    refs = extract_cross_references(doc, SAMPLE_TEXT)

    assert len(refs) >= 1
    guides_ref = next((r for r in refs if r.rel_type == "GUIDES"), None)
    assert guides_ref is not None
    assert "Luật Đất đai" in guides_ref.target_doc_id


def test_generate_legal_chunks():
    """Tests chunk generation with rich legal context."""
    doc = parse_legal_document(SAMPLE_TEXT)
    chunks = generate_legal_chunks(doc, dummy_vector_dim=16)

    assert len(chunks) == 3  # 2 clauses in Art 1 + 1 clause in Art 2
    chunk = chunks[0]
    assert "999/2025/ND-CP" in chunk["text"]
    assert chunk["payload"]["doc_id"] == "999/2025/ND-CP"
    assert chunk["payload"]["article_number"] == "1"
    assert len(chunk["vector"]) == 16


@pytest.mark.live
def test_pipeline_ingestion_end_to_end():
    """Tests ingesting sample raw documents into Neo4j and Qdrant."""
    neo4j_client = Neo4jClient()
    if not neo4j_client.verify_connectivity():
        pytest.skip("Neo4j not reachable")

    qdrant_manager = QdrantClientManager(collection_name="test_ingest_suite")
    if not qdrant_manager.health_check():
        pytest.skip("Qdrant not reachable")

    pipeline = LegalIngestionPipeline(
        neo4j_client=neo4j_client,
        qdrant_manager=qdrant_manager,
    )

    raw_path = Path("data/raw/152_2020_ND-CP.txt")
    if not raw_path.exists():
        pytest.skip("Sample raw data missing")

    res = pipeline.ingest_file(raw_path, sync_qdrant=True, sync_neo4j=True, vector_dim=8)
    assert res["doc_id"] == "152/2020/ND-CP"
    assert res["articles_count"] > 0
    assert res["chunks_count"] > 0

    # Clean up test collection
    with contextlib.suppress(Exception):
        qdrant_manager.client.delete_collection("test_ingest_suite")
    neo4j_client.close()


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Nghị định 100/2024/NĐ-CP</title></head>
<body>
<div class="vbTitle">NGHỊ ĐỊNH VỀ QUẢN LÝ LAO ĐỘNG</div>
<p>CHÍNH PHỦ</p>
<p>Số: 100/2024/NĐ-CP</p>
<p>Hà Nội, ngày 20 tháng 05 năm 2024</p>
<p>Điều 1. Phạm vi áp dụng</p>
<p>1. Nghị định này quy định việc quản lý người lao động nước ngoài.</p>
<p>2. Áp dụng đối với doanh nghiệp có vốn đầu tư nước ngoài.</p>
<p>Điều 2. Văn bản dẫn chiếu</p>
<p>Thực hiện theo quy định tại <a href="http://vbpl.vn/152-2020">152/2020/NĐ-CP</a> và sửa đổi bổ sung.</p>
</body>
</html>
"""


def test_parse_html_document():
    """Tests parsing HTML legal markup with hyperlinks and semantic tags."""
    doc, refs = parse_html_document(SAMPLE_HTML)

    assert doc.doc_id == "100/2024/ND-CP"
    assert doc.issuer == "Chính Phủ"
    assert doc.issue_date == "2024-05-20"
    assert len(doc.articles) == 2

    art1 = doc.articles[0]
    assert art1.article_number == "1"
    assert len(art1.clauses) == 2
    assert "quản lý người lao động nước ngoài" in art1.clauses[0].content

    # Check extracted hyperlink cross-reference
    assert any(ref.target_doc_id == "152/2020/ND-CP" for ref in refs)


def test_llm_fallback_graceful_offline(monkeypatch):
    """Tests LLM fallback parser handles missing or invalid API keys gracefully."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    doc = llm_fallback_parse_document("Văn bản bất thường không có cấu trúc chuẩn")
    assert doc is None


def test_cli_ingestion_help():
    """Tests CLI entrypoint loads without error."""
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "-m", "src.knowledge.ingestion", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "--file" in res.stdout
    assert "--dir" in res.stdout


def test_extract_article_cross_references_decree_70():
    """Tests fine-grained Article AMENDS and SUPERSEDES extraction from Decree 70/2023."""
    txt_70 = Path("data/raw/70_2023_ND-CP.txt").read_text(encoding="utf-8")
    doc_70 = parse_legal_document(txt_70)
    refs = extract_cross_references(doc_70, txt_70)

    # 1. Verify Document-level AMENDS
    doc_amends = [r for r in refs if r.rel_type == "AMENDS" and r.target_article_id is None]
    assert len(doc_amends) == 1
    assert doc_amends[0].target_doc_id == "152/2020/ND-CP"

    # 2. Verify Article-level AMENDS (Articles 3, 4, 8)
    art_amends = [r for r in refs if r.rel_type == "AMENDS" and r.target_article_id is not None]
    assert len(art_amends) == 3
    amended_target_articles = {r.target_article_id for r in art_amends}
    assert amended_target_articles == {
        "152/2020/ND-CP:Article_3",
        "152/2020/ND-CP:Article_4",
        "152/2020/ND-CP:Article_8",
    }
    for r in art_amends:
        assert r.source_article_id == "70/2023/ND-CP:Article_1"

    # 3. Verify Article-level SUPERSEDES (Article 4 Clause 2)
    repeals = [r for r in refs if r.rel_type == "SUPERSEDES"]
    assert len(repeals) >= 1
    art4_repeal = next(
        (r for r in repeals if r.target_article_id == "152/2020/ND-CP:Article_4"),
        None,
    )
    assert art4_repeal is not None
    assert art4_repeal.source_article_id == "70/2023/ND-CP:Article_2"
    assert "khoản 2 Điều 4" in str(art4_repeal.scope)


def test_extract_article_statutory_citations():
    """Tests extraction of statutory citations (CITES) including cross-statute and intra-statute."""
    citation_text = """CHÍNH PHỦ
Số: 888/2025/NĐ-CP
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
Hà Nội, ngày 01 tháng 01 năm 2025

NGHỊ ĐỊNH
Quy định về thủ tục cấp phép kinh doanh

Điều 1. Phạm vi áp dụng
1. Hồ sơ cấp phép thực hiện theo quy định tại Điều 13 Nghị định số 52/2024/NĐ-CP.
2. Tiêu chuẩn nhân sự kỹ thuật căn cứ theo Điều 5 của Nghị định số 152/2020/NĐ-CP.

Điều 2. Quy trình kiểm tra
1. Trình tự thanh tra đối chiếu với quy định tại Điều 1 của Nghị định này.
2. Các biện pháp bảo đảm thực hiện theo quy định tại Thông tư số 12/2022/TT-NHNN.
"""
    doc = parse_legal_document(citation_text)
    refs = extract_cross_references(doc, citation_text)

    cites = [r for r in refs if r.rel_type == "CITES"]
    assert len(cites) >= 4

    # Cross-statute Article citations
    cite_52 = next((r for r in cites if r.target_article_id == "52/2024/ND-CP:Article_13"), None)
    assert cite_52 is not None
    assert cite_52.source_article_id == "888/2025/ND-CP:Article_1"

    cite_152 = next((r for r in cites if r.target_article_id == "152/2020/ND-CP:Article_5"), None)
    assert cite_152 is not None
    assert cite_152.source_article_id == "888/2025/ND-CP:Article_1"

    # Intra-statute Article citation (Article 2 citing Article 1 of same decree)
    cite_intra = next((r for r in cites if r.target_article_id == "888/2025/ND-CP:Article_1"), None)
    assert cite_intra is not None
    assert cite_intra.source_article_id == "888/2025/ND-CP:Article_2"

    # Cross-statute document-level citation (citing 12/2022/TT-NHNN)
    cite_doc = next((r for r in cites if r.target_doc_id == "12/2022/TT-NHNN"), None)
    assert cite_doc is not None
    assert cite_doc.target_article_id is None


LEGACY_HTML = """<html><body>
<p>NGÂN HÀNG NHÀ NƯỚC VIỆT NAM</p>
<p>Số: 22/QĐ-NH1</p>
<p>Hà Nội, ngày 21 tháng 02 năm 1994</p>
<p>QUYẾT ĐỊNH</p>
<p>Điều 1. Ban hành kèm theo Quyết định này Thể lệ thanh toán không dùng tiền mặt.</p>
<p>Điều 2. Hiệu lực</p>
<p>1. Quyết định này có hiệu lực từ ngày 01 tháng 4 năm 1994.</p>
<p>2. Các quy định tại Điều 1 Quyết định này áp dụng cho các ngân hàng.</p>
</body></html>
"""


def test_apply_authoritative_metadata_rekeys_legacy_ids():
    """A year-less legacy number parses as UNKNOWN/DOC; the MoJ record must re-key it."""
    doc, refs = parse_html_document(LEGACY_HTML)
    assert doc.doc_id == "UNKNOWN/DOC"

    meta = {
        "doc_id": "22/QD-NH1",
        "title": "Quyết định 22/QĐ-NH1 ban hành Thể lệ thanh toán không dùng tiền mặt",
        "doc_type": "Quyết định",
        "issuer": "Ngân hàng Nhà nước Việt Nam",
        "issue_date": "1994-02-21",
        "effective_date": "1994-04-01",
        "expiration_date": "2003-01-01",
        "status": "expired",
        "eff_status_code": "HHL",
        "moj_id": "12345",
    }
    doc, refs = apply_authoritative_metadata(doc, refs, meta)

    assert doc.doc_id == "22/QD-NH1"
    assert doc.status == "expired"
    assert doc.expiration_date == "2003-01-01"
    assert doc.issuer == "Ngân hàng Nhà nước Việt Nam"
    assert doc.metadata == {"eff_status_code": "HHL", "moj_id": "12345"}
    assert all(a.article_id.startswith("22/QD-NH1:Article_") for a in doc.articles)
    assert all(
        c.clause_id.startswith("22/QD-NH1:Article_") for a in doc.articles for c in a.clauses
    )
    assert not any("UNKNOWN/DOC" in (r.source_doc_id + (r.target_article_id or "")) for r in refs)
    assert not any(r.target_doc_id == doc.doc_id and not r.target_article_id for r in refs)


def test_ingest_file_uses_sidecar_metadata(tmp_path):
    """``<stem>.meta.json`` next to a raw file overrides the regex-derived metadata."""
    raw = tmp_path / "22_QD-NH1.html"
    raw.write_text(LEGACY_HTML, encoding="utf-8")
    (tmp_path / "22_QD-NH1.meta.json").write_text(
        json.dumps({"doc_id": "22/QD-NH1", "status": "expired", "moj_id": "12345"}),
        encoding="utf-8",
    )

    assert load_sidecar_metadata(raw) == {
        "doc_id": "22/QD-NH1",
        "status": "expired",
        "moj_id": "12345",
    }
    pipeline = LegalIngestionPipeline()
    res = pipeline.ingest_file(raw, sync_qdrant=False, sync_neo4j=False, vector_dim=8)
    assert res["doc_id"] == "22/QD-NH1"
    assert res["articles_count"] == 2


def test_ingest_directory_continues_after_failure(tmp_path, monkeypatch):
    """One malformed file is reported with an error instead of aborting the batch."""
    (tmp_path / "a_bad.html").write_text("<p>x</p>", encoding="utf-8")
    (tmp_path / "b_good.txt").write_text(SAMPLE_TEXT, encoding="utf-8")
    pipeline = LegalIngestionPipeline()
    real_ingest = pipeline.ingest_file

    def flaky_ingest(file_path, **kwargs):
        if Path(file_path).name == "a_bad.html":
            raise ValueError("boom")
        return real_ingest(file_path, vector_dim=8, **kwargs)

    monkeypatch.setattr(pipeline, "ingest_file", flaky_ingest)
    results = pipeline.ingest_directory(
        tmp_path, sync_qdrant=False, sync_neo4j=False, enable_llm_fallback=False
    )

    assert results[0] == {"file": "a_bad.html", "error": "ValueError: boom"}
    assert results[1]["doc_id"] == "999/2025/ND-CP"


ROMAN_TEXT = """NGÂN HÀNG NHÀ NƯỚC
Số: 01/2005/TT-NHNN
Hà Nội, ngày 10 tháng 3 năm 2005
THÔNG TƯ
Hướng dẫn thi hành Nghị định số 202/2004/NĐ-CP
I. QUY ĐỊNH CHUNG
1. Tình tiết giảm nhẹ
1.1. Người có thẩm quyền xử phạt xem xét tình tiết.
1.2. Vi phạm nhiều lần trong cùng lĩnh vực.
2. Thẩm quyền xử phạt
Chỉ những người có thẩm quyền mới được xử phạt.
II. THỦ TỤC XỬ PHẠT
Người có thẩm quyền phải thực hiện đúng thủ tục.
"""


def test_parse_roman_section_circular():
    """Legacy circulars without Điều are split by Roman sections; 1.1. stays inside 1."""
    doc = parse_legal_document(ROMAN_TEXT)

    assert [a.article_number for a in doc.articles] == ["I", "II"]
    first = doc.articles[0]
    assert first.article_id == "01/2005/TT-NHNN:Article_I"
    assert [c.clause_number for c in first.clauses] == ["1", "2"]
    assert "1.2. Vi phạm nhiều lần" in first.clauses[0].content
    assert doc.articles[1].clauses[0].clause_id == "01/2005/TT-NHNN:Article_II:Clause_1"


DECISION_WITH_REGULATION = """NGÂN HÀNG NHÀ NƯỚC VIỆT NAM
Số: 01/2008/QĐ-NHNN
Hà Nội, ngày 03 tháng 01 năm 2008
QUYẾT ĐỊNH
Ban hành Quy chế cho vay
Điều 1. Ban hành kèm theo Quyết định này Quy chế cho vay.
Điều 2. Quyết định này có hiệu lực sau 15 ngày kể từ ngày đăng Công báo.
QUY CHẾ CHO VAY
Điều 1. Phạm vi điều chỉnh
1. Quy chế này quy định việc cho vay.
2. Đối tượng là tổ chức tín dụng.
Điều 2. Giải thích từ ngữ
Trong Quy chế này các từ ngữ được hiểu như sau.
"""


def test_repeated_article_numbers_get_unique_ids():
    """Decision + attached Regulation restart at Điều 1; ids must not collide."""
    doc = parse_legal_document(DECISION_WITH_REGULATION)

    ids = [a.article_id for a in doc.articles]
    assert ids == [
        "01/2008/QD-NHNN:Article_1",
        "01/2008/QD-NHNN:Article_2",
        "01/2008/QD-NHNN:Article_1_2",
        "01/2008/QD-NHNN:Article_2_2",
    ]
    assert doc.articles[2].article_number == "1"
    assert doc.articles[2].clauses[1].clause_id == "01/2008/QD-NHNN:Article_1_2:Clause_2"
    all_clause_ids = [c.clause_id for a in doc.articles for c in a.clauses]
    assert len(all_clause_ids) == len(set(all_clause_ids))


def test_parse_slash_sections_and_item_only_circulars():
    """``I/`` and ``1/`` numbering parse like ``I.``; item-only texts become article 0."""
    slash = "Số: 01/2001/TT-NHNN\nTHÔNG TƯ\nI/ ĐỐI TƯỢNG ÁP DỤNG\n1/ Doanh nghiệp.\n2/ Ngoại trừ.\nII.\nMỞ TÀI KHOẢN\n3/ Mở tài khoản.\n"
    doc = parse_legal_document(slash)
    assert [(a.article_number, a.title) for a in doc.articles] == [
        ("I", "ĐỐI TƯỢNG ÁP DỤNG"),
        ("II", "MỞ TÀI KHOẢN"),
    ]
    assert [c.clause_number for c in doc.articles[0].clauses] == ["1", "2"]

    items = "Số: 01/2007/TT-NHNN\nTHÔNG TƯ\nCăn cứ Luật.\n1. Mức phí giao dịch.\n2. Hiệu lực thi hành.\n"
    doc = parse_legal_document(items)
    assert [a.article_number for a in doc.articles] == ["0"]
    assert [c.clause_number for c in doc.articles[0].clauses] == ["1", "2"]
    assert "Căn cứ" not in doc.articles[0].content


def test_inbound_relations_become_supersedes_edges():
    """MoJ "Bị thay thế bởi X" on a document yields X -> doc, not a metadata property."""
    doc, refs = parse_html_document(LEGACY_HTML)
    meta = {
        "doc_id": "22/QD-NH1",
        "status": "expired",
        "revoked_by": "01/2014/ND-CP",
        "revoked_date": "2014-02-20",
        "inbound_relations": [
            {"source_doc_id": "01/2014/ND-CP", "rel_type": "SUPERSEDES", "scope": "bị thay thế"},
            {"source_doc_id": "22/QD-NH1", "rel_type": "SUPERSEDES"},
        ],
    }
    doc, refs = apply_authoritative_metadata(doc, refs, meta)

    assert "inbound_relations" not in doc.metadata
    assert doc.metadata["revoked_by"] == "01/2014/ND-CP"
    inbound = [r for r in refs if r.target_doc_id == "22/QD-NH1" and r.rel_type == "SUPERSEDES"]
    assert len(inbound) == 1  # the self-reference is dropped
    assert inbound[0].source_doc_id == "01/2014/ND-CP"
    assert inbound[0].target_article_id is None
    assert inbound[0].effective_date == "2014-02-20"
