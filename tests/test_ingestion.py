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
