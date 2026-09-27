"""Unit and integration tests for Selective Edge Traversal Engine."""

import pytest

from src.core.exceptions import KnowledgeBaseError
from src.knowledge.ingestion import LegalIngestionPipeline
from src.knowledge.neo4j_client import Neo4jClient
from src.knowledge.selective_traversal import (
    SelectiveTraversalEngine,
    TraversalContext,
    TraversalResult,
)


@pytest.fixture(scope="module")
def setup_legal_graph():
    """Initializes and seeds graph with Decree 152/2020 and Decree 70/2023."""
    neo4j_client = Neo4jClient()
    if not neo4j_client.verify_connectivity():
        pytest.skip("Neo4j is not reachable")

    pipeline = LegalIngestionPipeline(neo4j_client=neo4j_client)
    pipeline.ingest_file("data/raw/152_2020_ND-CP.txt", sync_qdrant=False, sync_neo4j=True)
    pipeline.ingest_file("data/raw/70_2023_ND-CP.txt", sync_qdrant=False, sync_neo4j=True)

    yield neo4j_client
    neo4j_client.close()


def test_temporal_pruning_future_amendment(setup_legal_graph: Neo4jClient):
    """Tests that amendments effective after the reference date are pruned."""
    engine = SelectiveTraversalEngine(neo4j_client=setup_legal_graph)

    # Reference date is 2022-01-01 (Decree 70 took effect in 2023-09-18)
    ctx = TraversalContext(reference_date="2022-01-01")
    res = engine.traverse("152/2020/ND-CP", ctx)

    assert res.seed_doc_id == "152/2020/ND-CP"
    assert res.reference_date == "2022-01-01"
    # Decree 70 should not be active
    assert len(res.amendment_chains) == 0
    # Pruned nodes should include Decree 70
    assert res.pruned_nodes_count >= 1
    assert res.noise_reduction_ratio > 0.0


def test_temporal_amendment_resolution(setup_legal_graph: Neo4jClient):
    """Tests that active amendments override original statutory articles."""
    engine = SelectiveTraversalEngine(neo4j_client=setup_legal_graph)

    # Reference date is 2024-01-01 (Decree 70 is active)
    ctx = TraversalContext(reference_date="2024-01-01")
    res = engine.traverse("152/2020/ND-CP", ctx)

    assert res.seed_doc_id == "152/2020/ND-CP"
    assert len(res.amendment_chains) >= 1

    # Check that Article 4 or Article 3 is amended by 70/2023/ND-CP
    amended_articles = [art for art in res.active_articles if art["is_amended"]]
    assert len(amended_articles) >= 1
    assert any(art["amended_by"] == "70/2023/ND-CP" for art in amended_articles)


def test_markdown_synthesis(setup_legal_graph: Neo4jClient):
    """Tests that synthesized context contains headers, amendment notes, and articles."""
    engine = SelectiveTraversalEngine(neo4j_client=setup_legal_graph)
    ctx = TraversalContext(reference_date="2024-01-01")
    res = engine.traverse("152/2020/ND-CP", ctx)

    md = engine.synthesize_active_context(res)
    assert "# Active Statutory Context: 152/2020/ND-CP" in md
    assert "**Reference Date**: 2024-01-01" in md
    assert "Active Amendment Overrides" in md
    assert "Governing Articles" in md


def test_missing_seed_document_raises(setup_legal_graph: Neo4jClient):
    """Tests that non-existent seed documents raise KnowledgeBaseError."""
    engine = SelectiveTraversalEngine(neo4j_client=setup_legal_graph)
    with pytest.raises(KnowledgeBaseError, match="Seed document not found in graph"):
        engine.traverse("NON_EXISTENT/DOC/ID")


def test_noise_reduction_ratio_edge_cases():
    """Tests TraversalResult noise reduction calculation."""
    res_empty = TraversalResult(seed_doc_id="D1", reference_date="2026-01-01")
    assert res_empty.noise_reduction_ratio == 0.0

    res_pruned = TraversalResult(
        seed_doc_id="D1",
        reference_date="2026-01-01",
        traversed_nodes_count=3,
        pruned_nodes_count=2,
    )
    assert res_pruned.noise_reduction_ratio == 0.4  # 2 / (3 + 2) = 0.4
