"""Knowledge module: Neo4j client, Qdrant client, and ingestion pipeline."""

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

__all__ = [
    "LegalCrossReference",
    "LegalIngestionPipeline",
    "Neo4jClient",
    "ParsedArticle",
    "ParsedClause",
    "ParsedDocument",
    "QdrantClientManager",
    "extract_cross_references",
    "generate_legal_chunks",
    "parse_legal_document",
]
