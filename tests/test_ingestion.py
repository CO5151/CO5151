"""Unit and integration tests for Vietnamese legal ingestion pipeline."""

import contextlib
from pathlib import Path

import pytest

from src.knowledge.ingestion import (
    LegalIngestionPipeline,
    extract_cross_references,
    generate_legal_chunks,
    normalize_doc_id,
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
