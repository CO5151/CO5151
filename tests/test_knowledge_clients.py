"""Unit and integration tests for Neo4jClient and QdrantClientManager."""

import contextlib

import pytest

from src.core.exceptions import KnowledgeBaseError
from src.knowledge.neo4j_client import Neo4jClient
from src.knowledge.qdrant_client import QdrantClientManager


@pytest.fixture(scope="module")
def neo4j_client():
    """Provides a connected Neo4jClient with schema initialized."""
    client = Neo4jClient()
    if not client.verify_connectivity():
        pytest.skip("Neo4j instance is not reachable")
    client.init_schema()
    yield client
    client.close()


@pytest.fixture(scope="module")
def qdrant_manager():
    """Provides a connected QdrantClientManager using a test collection."""
    qm = QdrantClientManager(collection_name="test_knowledge_suite")
    if not qm.health_check():
        pytest.skip("Qdrant instance is not reachable")
    qm.init_collection(vector_size=4, recreate=True)
    yield qm
    with contextlib.suppress(Exception):
        qm.client.delete_collection("test_knowledge_suite")


def test_neo4j_upsert_and_retrieve(neo4j_client: Neo4jClient):
    """Tests document, article, and clause insertion and relationship creation."""
    doc_id = "TEST/152/2020/ND-CP"
    article_id = f"{doc_id}:Article_4"
    clause_id = f"{article_id}:Clause_1"

    # Upsert Document
    doc = neo4j_client.upsert_document(
        doc_id=doc_id,
        title="Nghị định về người lao động nước ngoài làm việc tại Việt Nam",
        doc_type="Nghị định",
        issuer="Chính phủ",
        issue_date="2020-12-30",
        effective_date="2021-02-15",
        status="in_force",
    )
    assert doc["doc_id"] == doc_id
    assert doc["issuer"] == "Chính phủ"

    # Upsert Article
    article = neo4j_client.upsert_article(
        article_id=article_id,
        doc_id=doc_id,
        article_number="4",
        title="Điều kiện cấp giấy phép lao động",
        content="Người lao động nước ngoài phải có đủ năng lực hành vi dân sự.",
    )
    assert article["article_id"] == article_id

    # Upsert Clause
    clause = neo4j_client.upsert_clause(
        clause_id=clause_id,
        article_id=article_id,
        clause_number="1",
        content="Đủ 18 tuổi trở lên và có đủ năng lực hành vi dân sự.",
    )
    assert clause["clause_id"] == clause_id

    # Verify hierarchy
    hierarchy = neo4j_client.get_document_by_id(doc_id)
    assert hierarchy is not None
    assert hierarchy["doc_id"] == doc_id
    assert len(hierarchy["articles"]) >= 1

    # Cleanup
    neo4j_client.execute_query(
        "MATCH (d:Document {doc_id: $doc_id}) "
        "OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article) "
        "OPTIONAL MATCH (a)-[:CONTAINS]->(c:Clause) "
        "DETACH DELETE d, a, c",
        {"doc_id": doc_id},
    )


def test_neo4j_amendment_relationship(neo4j_client: Neo4jClient):
    """Tests AMENDS relationship creation and querying."""
    doc_original = "TEST/ORIGINAL/2020"
    doc_amender = "TEST/AMENDER/2023"

    neo4j_client.upsert_document(
        doc_id=doc_original,
        title="Văn bản gốc",
        doc_type="Nghị định",
        issuer="Chính phủ",
        issue_date="2020-01-01",
        effective_date="2020-02-01",
    )
    neo4j_client.upsert_document(
        doc_id=doc_amender,
        title="Văn bản sửa đổi bổ sung",
        doc_type="Nghị định",
        issuer="Chính phủ",
        issue_date="2023-01-01",
        effective_date="2023-02-01",
    )

    # Create AMENDS relationship
    success = neo4j_client.create_relationship(
        from_label="Document",
        from_key="doc_id",
        from_val=doc_amender,
        to_label="Document",
        to_key="doc_id",
        to_val=doc_original,
        rel_type="AMENDS",
        properties={"scope": "Điều 4, Điều 8", "effective_date": "2023-02-01"},
    )
    assert success is True

    # Retrieve amendments
    amendments = neo4j_client.get_amendments(doc_original)
    assert len(amendments) == 1
    assert amendments[0]["doc_id"] == doc_amender
    assert amendments[0]["direction"] == "amending_this"

    # Cleanup
    neo4j_client.execute_query(
        "MATCH (d:Document) WHERE d.doc_id IN [$d1, $d2] DETACH DELETE d",
        {"d1": doc_original, "d2": doc_amender},
    )


def test_neo4j_invalid_relationship_type(neo4j_client: Neo4jClient):
    """Tests that invalid relationship types are rejected with KnowledgeBaseError."""
    with pytest.raises(KnowledgeBaseError, match="Invalid relationship type"):
        neo4j_client.create_relationship(
            from_label="Document",
            from_key="doc_id",
            from_val="D1",
            to_label="Document",
            to_key="doc_id",
            to_val="D2",
            rel_type="INVALID_RELATION",
        )


def test_qdrant_vector_lifecycle(qdrant_manager: QdrantClientManager):
    """Tests chunk upsert, search with filtering, and deletion."""
    test_chunks = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "vector": [1.0, 0.0, 0.0, 0.0],
            "payload": {
                "doc_id": "TEST/DOC/1",
                "article_id": "TEST/DOC/1:Article_1",
                "status": "in_force",
                "effective_date": "2021-01-01",
                "text": "Điều 1: Phạm vi điều chỉnh quy định về lao động.",
            },
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "vector": [0.0, 1.0, 0.0, 0.0],
            "payload": {
                "doc_id": "TEST/DOC/1",
                "article_id": "TEST/DOC/1:Article_2",
                "status": "expired",
                "effective_date": "2021-01-01",
                "text": "Điều 2: Quy định cũ đã hết hiệu lực thi hành.",
            },
        },
    ]

    # Upsert
    inserted = qdrant_manager.upsert_legal_chunks(test_chunks)
    assert inserted == 2

    # Search in-force only
    hits_in_force = qdrant_manager.search(
        query_vector=[1.0, 0.0, 0.0, 0.0],
        limit=2,
        status_filter="in_force",
    )
    assert len(hits_in_force) == 1
    assert hits_in_force[0]["payload"]["status"] == "in_force"

    # Search without filter
    hits_all = qdrant_manager.search(
        query_vector=[0.0, 1.0, 0.0, 0.0],
        limit=2,
        status_filter=None,
    )
    assert len(hits_all) >= 1

    # Delete by doc_id
    qdrant_manager.delete_by_doc_id("TEST/DOC/1")
    stats = qdrant_manager.get_collection_stats()
    assert stats["name"] == "test_knowledge_suite"
