"""LawGraph Agent: Retrieves and traverses Vietnamese legal statutes and decrees.

Handles knowledge retrieval using statutory catalog and graph traversal logic,
resolving amendment chains and temporal validity bounds. Compliant with Google ADK.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, ClassVar, cast

from src.agents.base import ADKAgent
from src.core.logger import logger

# ---------------------------------------------------------------------------
# Retrieval backends:
#   1. Dense (default): live Qdrant collection, in-force provisions ranked first;
#      Neo4j lexical Cypher only when Qdrant returns nothing (BENCH_RETRIEVER
#      pins dense / neo4j / hybrid RRF for benchmarks)
#   2. Hand-written STATUTE_CATALOG (deterministic offline fallback)
#   3. Dense search over the exported chunk index
# The JSON exports are only used when the databases are unreachable, so a
# demo never breaks just because the containers are down.
# ---------------------------------------------------------------------------
_CHUNK_EXPORT = Path("data/processed/qdrant_chunks_export.json")
_GRAPH_EXPORT = Path("data/processed/neo4j_graph_export.json")
_EMBEDDER_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
_RRF_K = 60

_DENSE_INDEX: dict[str, tuple[Any, Any, list[dict[str, Any]]]] = {}
_GRAPH_STATUS: dict[str, dict[str, Any]] = {}
_NEO4J_HANDLE: dict[str, Any] = {}
_QDRANT_HANDLE: dict[str, Any] = {}
_EMBEDDER: dict[str, Any] = {}


def _get_embedder() -> Any | None:
    """Loads the Vietnamese bi-encoder once per process (None if unavailable)."""
    if "model" not in _EMBEDDER:
        try:
            from sentence_transformers import SentenceTransformer

            _EMBEDDER["model"] = SentenceTransformer(_EMBEDDER_NAME)
        except Exception as e:  # package missing (install the [embeddings] extra) or no model
            logger.warning("LawGraphAgent: embedder unavailable: %s", e)
            _EMBEDDER["model"] = None
    return _EMBEDDER["model"]


def _get_qdrant_manager() -> Any | None:
    """Returns a QdrantClientManager for a non-empty collection, or None.

    Probed once per process like the Neo4j handle.
    """
    if "manager" in _QDRANT_HANDLE:
        return _QDRANT_HANDLE["manager"]
    manager = None
    try:
        from src.knowledge.qdrant_client import QdrantClientManager

        candidate = QdrantClientManager()
        if candidate.health_check() and candidate.get_collection_stats().get("points_count"):
            manager = candidate
            logger.info("LawGraphAgent: Qdrant collection '%s' ready.", candidate.collection_name)
    except Exception as e:
        logger.warning("LawGraphAgent: Qdrant unavailable (%s).", e)
    _QDRANT_HANDLE["manager"] = manager
    return manager


def _item_key(item: dict[str, Any]) -> str:
    """Article-level identity; article_id keeps repeated numbers (Article_1_2) apart."""
    return str(item.get("article_id") or f"{item.get('doc_id')}:{item.get('article')}")


def _fuse_ranked(ranked_lists: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion, then a stable in-force-first ordering.

    Expired or not-yet-effective provisions are kept after the active ones so the
    Claim Auditor can still flag them when nothing better exists.
    """
    from src.core.statute_status import is_active_status

    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            key = _item_key(item)
            scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
            items.setdefault(key, item)
    ordered = sorted(scores, key=lambda k: -scores[k])
    ordered.sort(
        key=lambda k: not is_active_status(items[k].get("status"), items[k].get("revoked_by"))
    )
    return [{**items[k], "fused_score": round(scores[k], 5)} for k in ordered[:limit]]


def _get_neo4j_client() -> Any | None:
    """Returns a connected Neo4jClient, or None when the graph DB is unreachable.

    Probed once per process; the result (including failures) is cached so we do
    not retry on every retrieval call.
    """
    if "client" in _NEO4J_HANDLE:
        return _NEO4J_HANDLE["client"]
    client = None
    try:
        from src.knowledge.neo4j_client import Neo4jClient

        candidate = Neo4jClient()
        if candidate.verify_connectivity():
            client = candidate
            logger.info("LawGraphAgent: Neo4j graph connected at %s", candidate.uri)
        else:
            candidate.close()
    except Exception as e:  # driver missing, refused connection, bad auth...
        logger.warning("LawGraphAgent: Neo4j unavailable (%s).", e)
    if client is None:
        logger.warning(
            "LawGraphAgent: falling back to JSON exports. Start the graph with "
            "`docker compose up -d neo4j` and seed it with "
            "`scripts/load_neo4j_from_export.py`."
        )
    _NEO4J_HANDLE["client"] = client
    return client


def _search_terms(subgoals: list[str], keywords: list[str], limit: int = 24) -> list[str]:
    """Tokenises subgoals + keywords into lowercase CONTAINS terms."""
    raw = " ".join([*subgoals, *keywords]).lower()
    tokens = [t for t in re.findall(r"\w+", raw, flags=re.UNICODE) if len(t) >= 2]
    return list(dict.fromkeys(tokens))[:limit]


def _load_dense_index() -> tuple[Any, Any, list[dict[str, Any]]]:
    """Loads (embedder, normalized vectors, chunks) once per process."""
    if "index" in _DENSE_INDEX:
        return _DENSE_INDEX["index"]
    try:
        import json

        import numpy as np

        if not _CHUNK_EXPORT.exists():
            raise FileNotFoundError(str(_CHUNK_EXPORT))
        model = _get_embedder()
        if model is None:
            raise RuntimeError("embedder unavailable")
        chunks = json.loads(_CHUNK_EXPORT.read_text(encoding="utf-8"))
        matrix = np.asarray([c["vector"] for c in chunks], dtype="float32")
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
        _DENSE_INDEX["index"] = (model, matrix, chunks)
        logger.info("LawGraphAgent: dense chunk index ready (%d chunks).", len(chunks))
    except Exception as e:
        logger.warning("LawGraphAgent: dense chunk index unavailable: %s", e)
        _DENSE_INDEX["index"] = (None, None, [])
    return _DENSE_INDEX["index"]


def _load_graph_status() -> dict[str, dict[str, Any]]:
    """Document-level validity truth (status / revoked_by).

    Read from the live Neo4j graph first; the chunk payloads mark every document
    ``in_force``, so only the graph (or its export) can reveal a repeal.
    """
    if _GRAPH_STATUS:
        return _GRAPH_STATUS

    client = _get_neo4j_client()
    if client is not None:
        try:
            rows = client.execute_query(
                "MATCH (d:Document) "
                "WHERE d.title IS NOT NULL "
                "RETURN d.doc_id AS doc_id, d.title AS title, "
                "       d.status AS status, d.revoked_by AS revoked_by, "
                "       d.superseded_by AS superseded_by, "
                "       d.eff_status_code AS eff_status_code, d.eff_to AS eff_to"
            )
            for row in rows:
                _GRAPH_STATUS[row["doc_id"]] = {
                    "status": row.get("status"),
                    "revoked_by": row.get("revoked_by"),
                    "superseded_by": row.get("superseded_by"),
                    "eff_status_code": row.get("eff_status_code"),
                    "eff_to": row.get("eff_to"),
                    "title": row.get("title"),
                }
            if _GRAPH_STATUS:
                logger.info(
                    "LawGraphAgent: validity read from Neo4j (%d documents).",
                    len(_GRAPH_STATUS),
                )
                return _GRAPH_STATUS
        except Exception as e:
            logger.warning("LawGraphAgent: Neo4j status query failed: %s", e)

    try:
        import json

        if _GRAPH_EXPORT.exists():
            data = json.loads(_GRAPH_EXPORT.read_text(encoding="utf-8"))
            for doc_id, doc in data.items():
                _GRAPH_STATUS[doc_id] = {
                    "status": doc.get("status"),
                    "revoked_by": doc.get("revoked_by"),
                    "superseded_by": doc.get("superseded_by"),
                    "eff_status_code": doc.get("eff_status_code"),
                    "eff_to": doc.get("eff_to"),
                    "title": doc.get("title"),
                }
            logger.info(
                "LawGraphAgent: validity read from JSON export (%d documents).",
                len(_GRAPH_STATUS),
            )
    except Exception as e:
        logger.warning("LawGraphAgent: validity export unavailable: %s", e)
    return _GRAPH_STATUS


def _load_statute_catalog() -> dict[str, dict[str, Any]]:
    """Loads statute documents dynamically from local exported knowledge graph.

    Legal documents are persisted in data/processed/neo4j_graph_export.json or Neo4j,
    never hardcoded inside agent source code.
    """
    import json

    if _GRAPH_EXPORT.exists():
        try:
            data = json.loads(_GRAPH_EXPORT.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return cast("dict[str, dict[str, Any]]", data)
        except Exception as e:
            logger.warning("Could not load %s: %s", _GRAPH_EXPORT, e)
    return {}


class LawGraphAgent(ADKAgent):
    """Agent responsible for statutory retrieval and legal graph traversal."""

    # Dynamic knowledge catalog loaded from persistent graph export (0 hardcoded statutes)
    STATUTE_CATALOG: ClassVar[dict[str, dict[str, Any]]] = _load_statute_catalog()

    def __init__(
        self,
        traversal_engine: Any | None = None,
        qdrant_manager: Any | None = None,
        use_live_db: bool = False,
    ) -> None:
        import json
        from pathlib import Path

        from src.tools.lawgraph_tool import QUERY_LAWGRAPH_TOOL, TRACE_SELECTIVE_EDGE_TOOL
        from src.tools.statutory_retriever import STATUTORY_RETRIEVER_TOOL
        from src.tools.validity_checker import VALIDITY_CHECKER_TOOL

        super().__init__(
            name="LawGraphAgent",
            description="Truy vấn văn bản luật, nghị định, thông tư và duyệt đồ thị quan hệ sửa đổi/bổ sung.",
            role="retriever",
            tools=[
                STATUTORY_RETRIEVER_TOOL,
                VALIDITY_CHECKER_TOOL,
                TRACE_SELECTIVE_EDGE_TOOL,
                QUERY_LAWGRAPH_TOOL,
            ],
        )
        self.traversal_engine = traversal_engine
        self.qdrant_manager = qdrant_manager
        self.use_live_db = use_live_db

        # Dynamically load documents ingested into local processed graph export
        export_file = Path("data/processed/neo4j_graph_export.json")
        if export_file.exists():
            try:
                exported_data = json.loads(export_file.read_text(encoding="utf-8"))
                for doc_id, doc in exported_data.items():
                    if doc_id not in self.STATUTE_CATALOG:
                        self.STATUTE_CATALOG[doc_id] = doc
            except Exception as e:
                logger.warning("Could not load neo4j_graph_export.json: %s", e)

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes statutory retrieval via standard ADK interface."""
        if isinstance(input_data, dict):
            subgoals = input_data.get("subgoals", [])
            keywords = input_data.get("keywords", [])
            reference_date = input_data.get("reference_date", "")
            query = input_data.get("query", "")
        elif isinstance(input_data, str):
            subgoals = [input_data]
            keywords = [input_data]
            reference_date = ""
            query = input_data
        else:
            subgoals, keywords = [], []
            reference_date = ""
            query = ""
        return self.retrieve_provisions(
            subgoals, keywords, reference_date=reference_date, query=query
        )

    def trace_selective_edge(
        self,
        seed_doc_id: str,
        reference_date: str = "",
    ) -> dict[str, Any]:
        """Traces selective edges for a seed document using selective edge traversal."""
        from src.tools.lawgraph_tool import trace_selective_edge

        return trace_selective_edge(seed_doc_id=seed_doc_id, reference_date=reference_date)

    def _retrieve_from_live_graph(
        self,
        subgoals: list[str],
        keywords: list[str],
        reference_date: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieves provisions by traversing Neo4j knowledge graph with temporal pruning."""
        try:
            import re

            from src.knowledge.selective_traversal import SelectiveTraversalEngine, TraversalContext

            engine = self.traversal_engine or SelectiveTraversalEngine()
            context = (
                TraversalContext(reference_date=reference_date)
                if reference_date
                else TraversalContext()
            )

            doc_candidates: set[str] = set()
            pattern = re.compile(r"\b\d+/\d{4}/[A-Za-z0-9Đđ/-]+\b", re.IGNORECASE)

            full_text = " ".join(subgoals + keywords)
            for m in pattern.finditer(full_text):
                clean_id = m.group(0).upper().replace("Đ", "D").replace("đ", "d")
                doc_candidates.add(clean_id)

            if not doc_candidates and hasattr(engine, "client"):
                for kw in keywords:
                    if len(kw) < 4:
                        continue
                    try:
                        records = engine.client.execute_query(
                            "MATCH (d:Document) WHERE d.title CONTAINS $kw RETURN d.doc_id as doc_id LIMIT 3",
                            {"kw": kw},
                        )
                        for r in records:
                            if r.get("doc_id"):
                                doc_candidates.add(str(r["doc_id"]))
                    except Exception:
                        pass

            live_provisions: list[dict[str, Any]] = []
            for doc_id in doc_candidates:
                try:
                    res = engine.traverse(doc_id, context)
                    for art in res.active_articles:
                        live_provisions.append(
                            {
                                "doc_id": art.get("governing_doc_id", doc_id),
                                "title": f"Văn bản {art.get('governing_doc_id', doc_id)}",
                                "status": "active",
                                "effective_date": res.reference_date,
                                "article": f"Điều {art.get('article_number', '')}",
                                "article_title": art.get("title", ""),
                                "content": art.get("content", ""),
                                "amended_by": art.get("amended_by"),
                                "supersedes": [
                                    r.get("repealer_doc_id") for r in res.repealed_provisions
                                ],
                                "revoked_by": None,
                            }
                        )
                except Exception as ex:
                    logger.debug("Selective traversal skipped for %s: %s", doc_id, ex)

            return live_provisions
        except Exception as e:
            logger.debug("Live graph retrieval unavailable: %s", e)
            return []

    def neo4j_retrieve(
        self, subgoals: list[str], keywords: list[str], top_k: int = 6
    ) -> list[dict[str, Any]]:
        """Retrieves clauses straight from the Neo4j legal graph via Cypher.

        Matches Article/Clause text against the query terms, joins the parent
        Document for validity metadata, and ranks by the number of term hits.
        Returns [] when the graph DB is not reachable so callers can fall back.
        """
        client = _get_neo4j_client()
        if client is None:
            return []
        terms = _search_terms(subgoals, keywords)
        if not terms:
            return []
        queries = [s.strip() for s in subgoals if s.strip()]

        cypher = """
        MATCH (d:Document)-[:CONTAINS]->(a:Article)
        WITH d, a, toLower(coalesce(d.title, '') + ' ' + coalesce(a.title, '') + ' ' + coalesce(a.content, '')) AS hay
        WITH d, a,
             reduce(s = 0, t IN $terms | s + size(split(hay, t)) - 1) AS term_freq,
             size([t IN $terms WHERE size(split(hay, t)) > 1]) AS distinct_matches,
             size([q IN $queries WHERE hay CONTAINS toLower(q)]) AS phrase_matches
        WITH d, a, (distinct_matches * 10) + term_freq + (phrase_matches * 25) AS score
        WHERE score > 0
        RETURN d.doc_id AS doc_id,
               a.article_id AS article_id,
               coalesce(d.title, '') AS title,
               coalesce(d.status, 'unknown') AS status,
               coalesce(d.effective_date, '') AS effective_date,
               d.revoked_by AS revoked_by,
               'Điều ' + coalesce(a.article_number, '') AS article,
               coalesce(a.title, '') AS article_title,
               substring(coalesce(a.content, ""), 0, 1200) AS content,
               score
        ORDER BY score DESC, d.doc_id ASC, a.article_number ASC
        LIMIT $limit
        """

        try:
            rows = client.execute_query(
                cypher, {"terms": terms, "queries": queries, "limit": top_k}
            )
        except Exception as e:
            logger.warning("LawGraphAgent: Neo4j retrieval failed: %s", e)
            return []

        hits: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = row.get("article_id") or f"{row.get('doc_id')}:{row.get('article')}"
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "doc_id": row.get("doc_id", "UNKNOWN"),
                    "article_id": row.get("article_id"),
                    "title": row.get("title", ""),
                    "status": row.get("status", "unknown"),
                    "effective_date": row.get("effective_date", ""),
                    "article": row.get("article", ""),
                    "article_title": row.get("article_title", ""),
                    "content": row.get("content", ""),
                    "supersedes": [],
                    "revoked_by": row.get("revoked_by"),
                    "score": int(row.get("score", 0)),
                }
            )
            if len(hits) >= top_k:
                break
        logger.info("LawGraphAgent: Neo4j returned %d clause hits.", len(hits))
        return hits

    def qdrant_retrieve(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        """Embedding search over the live Qdrant collection, one hit per article.

        Clauses of the same article are collapsed onto the best-scoring one, so
        the collection is over-fetched before de-duplication. Returns [] when
        Qdrant or the embedder is unavailable so callers can fall back.
        """
        manager = _get_qdrant_manager()
        model = _get_embedder() if manager is not None else None
        if manager is None or model is None or not query.strip():
            return []
        try:
            vector = [float(x) for x in model.encode(query, normalize_embeddings=True)]
            rows = manager.search(vector, limit=max(1, top_k) * 4, status_filter=None)
        except Exception as e:
            logger.warning("LawGraphAgent: Qdrant search failed: %s", e)
            return []

        status_map = _load_graph_status()
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            payload = row.get("payload") or {}
            doc_id = payload.get("doc_id", "UNKNOWN")
            article_number = str(payload.get("article_number", "")).strip()
            article_id = payload.get("article_id") or f"{doc_id}:Article_{article_number}"
            if article_id in seen:
                continue
            seen.add(article_id)
            truth = status_map.get(doc_id, {})
            hits.append(
                {
                    "doc_id": doc_id,
                    "article_id": article_id,
                    "title": payload.get("title") or truth.get("title") or "",
                    "status": truth.get("status") or payload.get("status", "unknown"),
                    "effective_date": payload.get("effective_date", ""),
                    "article": f"Điều {article_number}" if article_number else "",
                    "article_title": payload.get("title", ""),
                    "content": payload.get("text", ""),
                    "supersedes": [],
                    "revoked_by": truth.get("revoked_by"),
                    "superseded_by": truth.get("superseded_by"),
                    "eff_status_code": truth.get("eff_status_code"),
                    "eff_to": truth.get("eff_to"),
                    "score": round(float(row.get("score", 0.0)), 4),
                }
            )
            if len(hits) >= top_k:
                break
        logger.info("LawGraphAgent: Qdrant returned %d article hits.", len(hits))
        return hits

    def dense_retrieve(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        """Embedding search: live Qdrant first, else the exported chunk index.

        Returns clause dicts in the same shape as the static catalog so the
        Claim Auditor and Drafter can consume them unchanged.
        """
        if not query.strip():
            return []
        live_hits = self.qdrant_retrieve(query, top_k=top_k)
        if live_hits:
            return live_hits
        model, matrix, chunks = _load_dense_index()
        if model is None or matrix is None or not chunks:
            return []

        import numpy as np

        q_vec = np.asarray(model.encode(query, normalize_embeddings=True), dtype="float32")
        sims = matrix @ q_vec
        order = np.argsort(-sims)[: max(1, top_k)]
        status_map = _load_graph_status()

        hits: list[dict[str, Any]] = []
        for idx in order:
            payload = chunks[int(idx)].get("payload", {})
            doc_id = payload.get("doc_id", "UNKNOWN")
            article_number = str(payload.get("article_number", "")).strip()
            truth = status_map.get(doc_id, {})
            hits.append(
                {
                    "doc_id": doc_id,
                    "title": payload.get("title") or truth.get("title") or "",
                    # Chunk payloads say in_force for every doc; trust the graph.
                    "status": truth.get("status") or payload.get("status", "unknown"),
                    "effective_date": payload.get("effective_date", ""),
                    "article": f"Điều {article_number}" if article_number else "",
                    "article_title": payload.get("title", ""),
                    "content": payload.get("text", ""),
                    "supersedes": [],
                    "revoked_by": truth.get("revoked_by"),
                    "superseded_by": truth.get("superseded_by"),
                    "eff_status_code": truth.get("eff_status_code"),
                    "eff_to": truth.get("eff_to"),
                    "score": round(float(sims[int(idx)]), 4),
                }
            )
        return hits

    def retrieve_provisions(
        self,
        subgoals: list[str],
        keywords: list[str],
        reference_date: str = "",
        force_live_db: bool = False,
        use_neo4j: bool = True,
        use_dense: bool = True,
        dense_top_k: int = 10,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieves relevant legal articles based on subgoals + keyword matches."""
        # BENCH_RETRIEVER lets a benchmark pin the retriever across architectures:
        #   (unset)  -> live Qdrant dense; Neo4j lexical only if Qdrant gives nothing
        #   dense    -> bi-encoder vector search only (Qdrant, else export)
        #   neo4j    -> Cypher lexical search over the graph only
        #   hybrid   -> both, Reciprocal Rank Fusion
        # Without this the ADK arm uses a different retriever than the LangGraph
        # harness, so any metric gap mixes architecture with retrieval.
        # On the 1,627-document SBV corpus (scripts/eval_retrieval_hit.py), dense
        # reached 93% doc Hit@10 in ~30 ms with the 90 leaked testset chunks
        # excluded; lexical scored 0% (unbounded term frequency favours long
        # articles) and only lowered hybrid.
        forced = os.getenv("BENCH_RETRIEVER", "").lower()
        use_vector = use_dense and forced in ("", "dense", "hybrid")
        use_lexical = use_neo4j and forced in ("", "neo4j", "hybrid")
        logger.info(f"LawGraphAgent: Retrieving provisions for subgoals: {subgoals}")
        results: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        search_terms = [k.lower() for k in keywords]
        # The raw question carries the discriminative wording; planner subgoals
        # are paraphrases and lose it.
        retrieval_texts = ([query] if query else []) + list(subgoals)

        # Pass 1 (primary): live Qdrant dense and/or Neo4j lexical, in-force first.
        # Dense is over-fetched 2x so in-force ordering can push repealed earlier
        # versions (semantically near-identical) out of the top-k.
        ranked: list[list[dict[str, Any]]] = []
        if use_vector:
            dense_text = query or " ".join(subgoals)
            ranked.append(self.qdrant_retrieve(dense_text, top_k=dense_top_k * 2))
        if use_lexical and (forced in ("neo4j", "hybrid") or not any(ranked)):
            ranked.append(self.neo4j_retrieve(retrieval_texts, keywords, top_k=dense_top_k))
        for item in _fuse_ranked([r for r in ranked if r], dense_top_k):
            seen_keys.add(_item_key(item))
            results.append(item)

        # Pass 2 (fallback): hand-written catalog, only when the graph gave nothing.
        # Skipped when a benchmark pins the retriever, otherwise the 6-document
        # catalog would shadow the dense pass and masquerade as dense retrieval.
        if not results and forced != "dense":
            for doc_id, doc in self.STATUTE_CATALOG.items():
                doc_text = f"{doc['title']} {doc['doc_id']}".lower()

                for article in doc["articles"]:
                    art_text = f"{article.get('title', '')} {article.get('content', '')}".lower()
                    combined = f"{doc_text} {art_text}"

                    is_match = any(term in combined for term in search_terms) or not search_terms
                    if is_match:
                        item_key = f"{doc_id}:{article.get('article', '')}"
                        if item_key not in seen_keys:
                            seen_keys.add(item_key)
                            results.append(
                                {
                                    "doc_id": doc["doc_id"],
                                    "title": doc["title"],
                                    "status": doc["status"],
                                    "effective_date": doc["effective_date"],
                                    "article": article["article"],
                                    "article_title": article["title"],
                                    "content": article["content"],
                                    "supersedes": doc.get("supersedes", []),
                                    "revoked_by": doc.get("revoked_by"),
                                }
                            )

        # Pass 3 (fallback): dense search over the exported chunk index.
        if use_dense and not results:
            query_text = " ".join(retrieval_texts + keywords).strip() or " ".join(subgoals)
            for item in self.dense_retrieve(query_text, top_k=dense_top_k):
                item_key = _item_key(item)
                if item_key not in seen_keys:
                    seen_keys.add(item_key)
                    results.append(item)

        # If live database is requested or catalog had no results, attempt dynamic graph retrieval
        if (self.use_live_db or force_live_db) or not results:
            live_results = self._retrieve_from_live_graph(subgoals, keywords, reference_date)
            for item in live_results:
                item_key = _item_key(item)
                if item_key not in seen_keys:
                    seen_keys.add(item_key)
                    results.append(item)

        logger.info(f"LawGraphAgent: Found {len(results)} candidate provisions.")
        return results
