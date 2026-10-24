#!/usr/bin/env python3
"""Seed the Neo4j legal knowledge graph from the local processed exports.

Builds (:Document)-[:CONTAINS]->(:Article)-[:CONTAINS]->(:Clause) for the whole
ingested corpus, then applies validity truth (status / revoked_by) and
cross-reference edges (SUPERSEDES / AMENDS / GUIDES) from the graph export.

Sources
-------
* ``data/processed/qdrant_chunks_export.json`` -- 103 clauses / 29 documents
  (full corpus used by retrieval)
* ``data/processed/neo4j_graph_export.json``   -- 3 documents with real
  ``status`` / ``revoked_by`` / ``cross_references`` (used to override the
  "everything is in_force" default)

Usage::

    docker compose up -d neo4j          # require a running graph DB
    .venv/bin/python scripts/load_neo4j_from_export.py
    .venv/bin/python scripts/load_neo4j_from_export.py --wipe   # clean reload
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.knowledge.neo4j_client import Neo4jClient  # noqa: E402

CHUNK_EXPORT = WORKSPACE / "data/processed/qdrant_chunks_export.json"
GRAPH_EXPORT = WORKSPACE / "data/processed/neo4j_graph_export.json"


def article_number(raw: str) -> str:
    """'Điều 23' -> '23' (falls back to the raw string)."""
    match = re.search(r"(\d+[a-zA-Z]?)", str(raw))
    return match.group(1) if match else str(raw).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="delete existing graph first")
    args = parser.parse_args()

    chunks = json.loads(CHUNK_EXPORT.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH_EXPORT.read_text(encoding="utf-8"))

    client = Neo4jClient()
    if not client.verify_connectivity():
        raise SystemExit(
            "Neo4j is not reachable. Start it with `docker compose up -d neo4j` "
            "and check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env"
        )

    if args.wipe:
        client.execute_query("MATCH (n) DETACH DELETE n")
        print(">>> Wiped existing graph")

    client.init_schema()

    # ------------------------------------------------------------------
    # 1. Documents + Articles + Clauses from the chunk export
    # ------------------------------------------------------------------
    docs: dict[str, dict] = {}
    for chunk in chunks:
        payload = chunk.get("payload", {})
        doc_id = payload.get("doc_id")
        if not doc_id:
            continue
        docs.setdefault(
            doc_id,
            {
                "doc_id": doc_id,
                "title": payload.get("title", ""),
                "doc_type": payload.get("doc_type", ""),
                "issuer": payload.get("issuer", ""),
                "effective_date": payload.get("effective_date") or "",
                "expiration_date": payload.get("expiration_date"),
                "status": payload.get("status", "in_force"),
                "clauses": [],
            },
        )
        docs[doc_id]["clauses"].append(payload)

    n_docs = n_articles = n_clauses = 0
    for doc_id, doc in docs.items():
        client.upsert_document(
            doc_id=doc_id,
            title=doc["title"],
            doc_type=doc["doc_type"],
            issuer=doc["issuer"],
            issue_date="",
            effective_date=doc["effective_date"],
            expiration_date=doc["expiration_date"],
            status=doc["status"],
        )
        n_docs += 1

        by_article: dict[str, list[dict]] = {}
        for clause in doc["clauses"]:
            num = article_number(clause.get("article_number", ""))
            by_article.setdefault(num, []).append(clause)

        for num, clauses in by_article.items():
            article_id = f"{doc_id}:Article_{num}"
            joined = "\n".join(c.get("text", "") for c in clauses)
            client.upsert_article(
                article_id=article_id,
                doc_id=doc_id,
                article_number=num,
                title=clauses[0].get("title", ""),
                content=joined,
            )
            n_articles += 1
            for clause in clauses:
                client.upsert_clause(
                    clause_id=clause.get("clause_id") or f"{article_id}:Clause_?",
                    article_id=article_id,
                    clause_number=str(clause.get("clause_number", "")),
                    content=clause.get("text", ""),
                )
                n_clauses += 1

    print(f">>> Loaded {n_docs} documents / {n_articles} articles / {n_clauses} clauses")

    # ------------------------------------------------------------------
    # 2. Validity truth + cross-reference edges from the graph export
    # ------------------------------------------------------------------
    n_links = 0
    for doc_id, doc in graph.items():
        status = doc.get("status")
        if status and status != "in_force":
            client.execute_query(
                "MERGE (d:Document {doc_id: $doc_id}) "
                "SET d.status = $status, d.revoked_by = $revoked_by",
                {"doc_id": doc_id, "status": status, "revoked_by": doc.get("revoked_by")},
            )

        if doc_id not in docs and doc.get("articles"):
            client.upsert_document(
                doc_id=doc_id,
                title=doc.get("title", ""),
                doc_type=doc.get("doc_type", ""),
                issuer=doc.get("issuer", ""),
                issue_date=doc.get("issue_date", ""),
                effective_date=doc.get("effective_date", ""),
                status=status or "in_force",
            )
            for art in doc["articles"]:
                num = article_number(art.get("article", ""))
                article_id = f"{doc_id}:Article_{num}"
                client.upsert_article(
                    article_id=article_id,
                    doc_id=doc_id,
                    article_number=num,
                    title=art.get("title", ""),
                    content=art.get("content", ""),
                )
                for idx, clause in enumerate(art.get("clauses") or [], start=1):
                    client.upsert_clause(
                        clause_id=clause.get("clause_id", f"{article_id}:Clause_{idx}"),
                        article_id=article_id,
                        clause_number=str(clause.get("clause_number", idx)),
                        content=clause.get("content", clause.get("text", "")),
                    )

        for ref in doc.get("cross_references") or []:
            rel = ref.get("rel_type")
            if rel not in ("AMENDS", "SUPERSEDES", "GUIDES"):
                continue
            target = ref.get("target_doc_id")
            client.execute_query(
                "MERGE (t:Document {doc_id: $doc_id})", {"doc_id": target}
            )
            client.create_relationship(
                from_label="Document",
                from_key="doc_id",
                from_val=doc_id,
                to_label="Document",
                to_key="doc_id",
                to_val=target,
                rel_type=rel,
                properties={
                    "scope": ref.get("scope") or "",
                    "effective_date": ref.get("effective_date") or "",
                },
            )
            n_links += 1

            if rel == "SUPERSEDES":
                client.execute_query(
                    "MATCH (t:Document {doc_id: $target}) "
                    "SET t.status = 'expired', t.revoked_by = $source",
                    {"target": target, "source": doc_id},
                )

    print(f">>> Applied {n_links} cross-reference edges and validity overrides")

    counts = client.execute_query(
        "MATCH (d:Document) "
        "WHERE d.title IS NOT NULL "
        "RETURN count(d) AS docs"
    )
    clause_counts = client.execute_query("MATCH (c:Clause) RETURN count(c) AS clauses")
    print(
        ">>> Graph now holds "
        f"{counts[0]['docs'] if counts else 0} documents, "
        f"{clause_counts[0]['clauses'] if clause_counts else 0} clauses"
    )
    client.close()


if __name__ == "__main__":
    main()
