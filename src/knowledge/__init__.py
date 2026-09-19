"""Knowledge module: Neo4j client, Qdrant client, ingestion pipeline, and selective traversal."""

from src.knowledge.ingestion import (
    LegalCrossReference,
    LegalIngestionPipeline,
    ParsedArticle,
    ParsedClause,
    ParsedDocument,
    extract_cross_references,
    generate_legal_chunks,
    parse_legal_document,
)
from src.knowledge.neo4j_client import Neo4jClient
from src.knowledge.qdrant_client import QdrantClientManager
from src.knowledge.selective_traversal import (
    SelectiveTraversalEngine,
    TraversalContext,
    TraversalResult,
)

__all__ = [
    "LegalCrossReference",
    "LegalIngestionPipeline",
    "Neo4jClient",
    "ParsedArticle",
    "ParsedClause",
    "ParsedDocument",
    "QdrantClientManager",
    "SelectiveTraversalEngine",
    "TraversalContext",
    "TraversalResult",
    "extract_cross_references",
    "generate_legal_chunks",
    "parse_legal_document",
]
