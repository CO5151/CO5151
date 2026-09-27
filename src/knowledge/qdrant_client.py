"""Qdrant client module for LegalPilot-VN vector store.

Manages dense vector index lifecycle, payload indexing for Vietnamese legal clauses,
and filtered similarity search with temporal and statutory validity constraints.
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.config import settings
from src.core.exceptions import KnowledgeBaseError
from src.core.logger import get_logger

logger = get_logger(__name__)


class QdrantClientManager:
    """Enterprise client managing Qdrant vector collections and payload queries."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
        api_key: str | None = None,
    ):
        """Initializes connection parameters for Qdrant cluster/instance."""
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.api_key = api_key
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """Returns an active QdrantClient instance or creates a new connection."""
        if self._client is None:
            try:
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=self.api_key,
                    timeout=10,
                    check_compatibility=False,
                )
                logger.info("Connected to Qdrant at %s:%s", self.host, self.port)
            except Exception as e:
                logger.error("Failed to connect to Qdrant: %s", e)
                raise KnowledgeBaseError(
                    f"Failed to connect to Qdrant at {self.host}:{self.port}: {e}"
                ) from e
        return self._client

    def health_check(self) -> bool:
        """Verifies if the Qdrant service is reachable and responsive."""
        try:
            # Simple check via get_collections()
            self.client.get_collections()
            return True
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)
            return False

    def init_collection(
        self,
        vector_size: int = 768,
        distance: models.Distance = models.Distance.COSINE,
        recreate: bool = False,
    ) -> None:
        """Initializes or recreates the legal clause vector collection with HNSW indexing."""
        try:
            collections_resp = self.client.get_collections()
            existing = [c.name for c in collections_resp.collections]

            if self.collection_name in existing:
                if recreate:
                    logger.warning("Recreating Qdrant collection: %s", self.collection_name)
                    self.client.delete_collection(self.collection_name)
                else:
                    logger.info("Collection '%s' already exists", self.collection_name)
                    self.setup_payload_indexes()
                    return

            logger.info(
                "Creating collection '%s' (dim: %d, metric: %s)",
                self.collection_name,
                vector_size,
                distance.name,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=distance,
                    on_disk=True,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    on_disk=True,
                ),
            )
            self.setup_payload_indexes()
            logger.info("Collection '%s' successfully initialized", self.collection_name)
        except Exception as e:
            logger.error("Failed to initialize Qdrant collection: %s", e)
            raise KnowledgeBaseError(f"Qdrant collection initialization failed: {e}") from e

    def setup_payload_indexes(self) -> None:
        """Sets up payload field indexes for rapid filtered retrieval."""
        index_fields = [
            ("doc_id", models.PayloadSchemaType.KEYWORD),
            ("article_id", models.PayloadSchemaType.KEYWORD),
            ("clause_id", models.PayloadSchemaType.KEYWORD),
            ("doc_type", models.PayloadSchemaType.KEYWORD),
            ("issuer", models.PayloadSchemaType.KEYWORD),
            ("status", models.PayloadSchemaType.KEYWORD),
            ("effective_date", models.PayloadSchemaType.KEYWORD),
        ]

        for field_name, schema_type in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
                logger.debug("Created payload index on field '%s'", field_name)
            except UnexpectedResponse as e:
                # Often occurs if index already exists
                if "already exists" not in str(e).lower():
                    logger.warning("Error creating index on '%s': %s", field_name, e)
            except Exception as e:
                logger.debug("Index on '%s' may already exist: %s", field_name, e)

    def upsert_legal_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Upserts a batch of vectorized legal chunks into Qdrant.

        Expected chunk dict format:
        {
            "id": str (UUID or int, optional, generated if missing),
            "vector": list[float],
            "payload": {
                "doc_id": str,
                "article_id": str,
                "clause_id": str,
                "text": str,
                "title": str,
                "status": str ("in_force", "expired", etc.),
                "effective_date": str ("YYYY-MM-DD"),
                ...
            }
        }
        """
        if not chunks:
            return 0

        points: list[models.PointStruct] = []
        for chunk in chunks:
            point_id = chunk.get("id") or str(uuid.uuid4())
            vector = chunk["vector"]
            payload = chunk.get("payload", {})

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            logger.info("Upserted %d points into '%s'", len(points), self.collection_name)
            return len(points)
        except Exception as e:
            logger.error("Failed to upsert points into Qdrant: %s", e)
            raise KnowledgeBaseError(f"Qdrant upsert failed: {e}") from e

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float | None = None,
        doc_ids: list[str] | None = None,
        status_filter: str | None = "in_force",
    ) -> list[dict[str, Any]]:
        """Performs dense vector similarity search with optional metadata filtering.

        Args:
            query_vector: Dense embedding vector for query.
            limit: Maximum number of points to return.
            score_threshold: Minimum cosine similarity score.
            doc_ids: Optional list of document IDs to restrict search to.
            status_filter: Filter by statutory status (default "in_force", None for all).
        """
        filter_conditions: list[models.Condition] = []

        if status_filter:
            filter_conditions.append(
                models.FieldCondition(
                    key="status",
                    match=models.MatchValue(value=status_filter),
                )
            )

        if doc_ids:
            filter_conditions.append(
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchAny(any=doc_ids),
                )
            )

        query_filter = models.Filter(must=filter_conditions) if filter_conditions else None

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
            )

            hits = []
            for point in results.points:
                hits.append(
                    {
                        "id": point.id,
                        "score": point.score,
                        "payload": point.payload,
                    }
                )
            return hits
        except Exception as e:
            logger.error("Failed to execute vector search in Qdrant: %s", e)
            raise KnowledgeBaseError(f"Qdrant search failed: {e}") from e

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Deletes all vector points associated with a specific doc_id."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(value=doc_id),
                            )
                        ]
                    )
                ),
            )
            logger.info("Deleted vector points for doc_id '%s'", doc_id)
        except Exception as e:
            logger.error("Failed to delete points by doc_id: %s", e)
            raise KnowledgeBaseError(f"Failed to delete points for {doc_id}: {e}") from e

    def get_collection_stats(self) -> dict[str, Any]:
        """Retrieves point count and configuration of the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "status": info.status.name,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
            }
        except Exception as e:
            logger.error("Failed to get collection stats: %s", e)
            raise KnowledgeBaseError(f"Failed to get stats for {self.collection_name}: {e}") from e
