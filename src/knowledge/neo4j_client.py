"""Neo4j client module for LegalPilot-VN knowledge graph.

Manages connection lifecycle, schema initialization, hierarchical legal entities
(Document, Article, Clause, Organization), and legal relationship traversal
(AMENDS, GUIDES, SUPERSEDES, REFERS_TO, CONTAINS).
"""

from __future__ import annotations

from typing import Any

from neo4j import Driver, GraphDatabase
from neo4j import exceptions as neo4j_exceptions

from src.core.config import settings
from src.core.exceptions import KnowledgeBaseError
from src.core.logger import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    """Enterprise client for interacting with the Neo4j Legal Knowledge Graph."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
    ):
        """Initializes the Neo4j driver with connection pooling and authentication."""
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        """Returns active driver instance or creates a new connection."""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    max_connection_lifetime=3600,
                    max_connection_pool_size=50,
                    connection_acquisition_timeout=15.0,
                )
                logger.info("Connected to Neo4j at %s", self.uri)
            except Exception as e:
                logger.error("Failed to initialize Neo4j driver: %s", e)
                raise KnowledgeBaseError(f"Failed to connect to Neo4j at {self.uri}: {e}") from e
        return self._driver

    def verify_connectivity(self) -> bool:
        """Verifies driver connectivity to Neo4j cluster/instance."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", e)
            return False

    def close(self) -> None:
        """Closes the active Neo4j driver and releases connection pools."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j driver connection")

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Executes a Cypher query inside a managed read/write transaction."""
        parameters = parameters or {}
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters)
                return [record.data() for record in result]
        except neo4j_exceptions.Neo4jError as e:
            logger.error("Neo4j query error: %s | Query: %s", e, query)
            raise KnowledgeBaseError(f"Cypher execution failed: {e}") from e

    def init_schema(self) -> None:
        """Initializes constraints and indexes for legal entities and relationships.

        Constraints enforce uniqueness on identifiers.
        Indexes optimize selective traversal and temporal filtering.
        """
        constraints = [
            (
                "document_doc_id_unique",
                "CREATE CONSTRAINT document_doc_id_unique IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            ),
            (
                "article_article_id_unique",
                "CREATE CONSTRAINT article_article_id_unique IF NOT EXISTS "
                "FOR (a:Article) REQUIRE a.article_id IS UNIQUE",
            ),
            (
                "clause_clause_id_unique",
                "CREATE CONSTRAINT clause_clause_id_unique IF NOT EXISTS "
                "FOR (c:Clause) REQUIRE c.clause_id IS UNIQUE",
            ),
            (
                "organization_name_unique",
                "CREATE CONSTRAINT organization_name_unique IF NOT EXISTS "
                "FOR (o:Organization) REQUIRE o.name IS UNIQUE",
            ),
        ]

        indexes = [
            (
                "document_status_idx",
                "CREATE INDEX document_status_idx IF NOT EXISTS FOR (d:Document) ON (d.status)",
            ),
            (
                "document_effective_date_idx",
                "CREATE INDEX document_effective_date_idx IF NOT EXISTS "
                "FOR (d:Document) ON (d.effective_date)",
            ),
            (
                "document_doc_type_idx",
                "CREATE INDEX document_doc_type_idx IF NOT EXISTS FOR (d:Document) ON (d.doc_type)",
            ),
            (
                "article_article_number_idx",
                "CREATE INDEX article_article_number_idx IF NOT EXISTS "
                "FOR (a:Article) ON (a.article_number)",
            ),
        ]

        for name, cypher in constraints:
            logger.debug("Applying constraint: %s", name)
            self.execute_query(cypher)

        for name, cypher in indexes:
            logger.debug("Applying index: %s", name)
            self.execute_query(cypher)

        logger.info("Successfully initialized Neo4j schema constraints and indexes")

    def upsert_document(
        self,
        doc_id: str,
        title: str,
        doc_type: str,
        issuer: str,
        issue_date: str,
        effective_date: str,
        expiration_date: str | None = None,
        status: str = "in_force",
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Upserts a legal Document node and links it to its issuing Organization."""
        query = """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.title = $title,
            d.doc_type = $doc_type,
            d.issuer = $issuer,
            d.issue_date = $issue_date,
            d.effective_date = $effective_date,
            d.expiration_date = $expiration_date,
            d.status = $status,
            d.source_url = $source_url,
            d.updated_at = datetime()
        MERGE (o:Organization {name: $issuer})
        MERGE (d)-[:ISSUED_BY]->(o)
        RETURN d
        """
        params = {
            "doc_id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "issuer": issuer,
            "issue_date": issue_date,
            "effective_date": effective_date,
            "expiration_date": expiration_date,
            "status": status,
            "source_url": source_url,
        }
        res = self.execute_query(query, params)
        return dict(res[0]["d"]) if res else {}

    def upsert_article(
        self,
        article_id: str,
        doc_id: str,
        article_number: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        """Upserts an Article node and connects it to its parent Document via CONTAINS."""
        query = """
        MATCH (d:Document {doc_id: $doc_id})
        MERGE (a:Article {article_id: $article_id})
        SET a.article_number = $article_number,
            a.title = $title,
            a.content = $content,
            a.doc_id = $doc_id,
            a.updated_at = datetime()
        MERGE (d)-[:CONTAINS]->(a)
        RETURN a
        """
        params = {
            "article_id": article_id,
            "doc_id": doc_id,
            "article_number": article_number,
            "title": title,
            "content": content,
        }
        res = self.execute_query(query, params)
        return dict(res[0]["a"]) if res else {}

    def upsert_clause(
        self,
        clause_id: str,
        article_id: str,
        clause_number: str,
        content: str,
    ) -> dict[str, Any]:
        """Upserts a Clause node and connects it to its parent Article via CONTAINS."""
        query = """
        MATCH (a:Article {article_id: $article_id})
        MERGE (c:Clause {clause_id: $clause_id})
        SET c.clause_number = $clause_number,
            c.content = $content,
            c.article_id = $article_id,
            c.updated_at = datetime()
        MERGE (a)-[:CONTAINS]->(c)
        RETURN c
        """
        params = {
            "clause_id": clause_id,
            "article_id": article_id,
            "clause_number": clause_number,
            "content": content,
        }
        res = self.execute_query(query, params)
        return dict(res[0]["c"]) if res else {}

    def create_relationship(
        self,
        from_label: str,
        from_key: str,
        from_val: Any,
        to_label: str,
        to_key: str,
        to_val: Any,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Creates a directional typed relationship between two nodes.

        Allowed relationship types: AMENDS, GUIDES, SUPERSEDES, REFERS_TO, CONTAINS.
        """
        valid_rels = {"AMENDS", "GUIDES", "SUPERSEDES", "REFERS_TO", "CONTAINS", "ISSUED_BY"}
        if rel_type not in valid_rels:
            raise KnowledgeBaseError(
                f"Invalid relationship type '{rel_type}'. Allowed: {valid_rels}"
            )

        # Note: Cypher doesn't allow parameters for relationship types or labels directly
        props = properties or {}
        query = f"""
        MATCH (from:{from_label} {{{from_key}: $from_val}})
        MATCH (to:{to_label} {{{to_key}: $to_val}})
        MERGE (from)-[r:{rel_type}]->(to)
        SET r += $props
        RETURN count(r) as created_count
        """
        params = {
            "from_val": from_val,
            "to_val": to_val,
            "props": props,
        }
        res = self.execute_query(query, params)
        return bool(res and res[0]["created_count"] > 0)

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieves a Document and its associated Articles and metadata."""
        query = """
        MATCH (d:Document {doc_id: $doc_id})
        OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article)
        RETURN d, collect(a) as articles
        """
        res = self.execute_query(query, {"doc_id": doc_id})
        if not res:
            return None
        doc_data: dict[str, Any] = dict(res[0]["d"])
        doc_data["articles"] = res[0]["articles"]
        return doc_data

    def get_amendments(self, doc_id: str) -> list[dict[str, Any]]:
        """Retrieves all documents that amend or are amended by the specified doc_id."""
        query = """
        MATCH (target:Document {doc_id: $doc_id})
        OPTIONAL MATCH (amender:Document)-[r_in:AMENDS]->(target)
        OPTIONAL MATCH (target)-[r_out:AMENDS]->(amended:Document)
        RETURN
            collect(DISTINCT {
                direction: "amending_this",
                doc_id: amender.doc_id,
                title: amender.title,
                effective_date: amender.effective_date,
                scope: r_in.scope
            }) as amenders,
            collect(DISTINCT {
                direction: "amended_by_this",
                doc_id: amended.doc_id,
                title: amended.title,
                effective_date: amended.effective_date,
                scope: r_out.scope
            }) as amended_docs
        """
        res = self.execute_query(query, {"doc_id": doc_id})
        if not res:
            return []
        record = res[0]
        amenders = [dict(a) for a in record.get("amenders", []) if a.get("doc_id")]
        amended = [dict(a) for a in record.get("amended_docs", []) if a.get("doc_id")]
        return amenders + amended

    def clear_database(self, confirm: bool = False) -> None:
        """Purges all nodes and relationships. ONLY for testing or dev environments."""
        if not confirm:
            raise ValueError("Must set confirm=True to clear database")
        query = "MATCH (n) DETACH DELETE n"
        self.execute_query(query)
        logger.warning("Purged all nodes and relationships from Neo4j database")
