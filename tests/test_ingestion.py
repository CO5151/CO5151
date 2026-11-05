"""Unit and integration tests for Vietnamese legal ingestion pipeline."""

import contextlib
from pathlib import Path

import pytest

from src.knowledge.ingestion import (
    LegalIngestionPipeline,
    extract_cross_references,
    generate_legal_chunks,
    llm_fallback_parse_document,
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
