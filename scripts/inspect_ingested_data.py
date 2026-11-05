#!/usr/bin/env python3
"""Read-only inspection of what ingestion wrote to the live Neo4j and Qdrant stores.

Subcommands:
    summary                    node / relation / point counts and status breakdown
    doc DOC_ID [--article N]   one document: graph node, articles, relations, vectors
    search "QUERY"             raw Qdrant hits next to the final LawGraphAgent ranking
    check                      consistency checks against data/raw/sbv/manifest.json

Examples:
    python scripts/inspect_ingested_data.py summary
    python scripts/inspect_ingested_data.py doc 40/2024/TT-NHNN --article 8
    HF_HUB_OFFLINE=1 python scripts/inspect_ingested_data.py search "ví điện tử"
    python scripts/inspect_ingested_data.py check      # exit code 1 if a check fails

Nothing here writes to either store. Start them first: docker compose up -d neo4j qdrant
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from qdrant_client import models  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.statute_status import is_active_status  # noqa: E402
from src.knowledge.ingestion import normalize_doc_id  # noqa: E402
from src.knowledge.neo4j_client import Neo4jClient  # noqa: E402
from src.knowledge.qdrant_client import QdrantClientManager  # noqa: E402

MANIFEST_FILE = WORKSPACE / "data/raw/sbv/manifest.json"
TESTSET_FILE = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
# Payload tag of chunks built from benchmark answers (scripts/ingest_real_embeddings.py).
LEAK_SOURCE = "sbv_testset_tvpl"
COLLECTION = settings.QDRANT_COLLECTION_NAME
SCROLL_PAGE = 2000


# --------------------------------------------------------------------------- helpers


def _connect() -> tuple[Neo4jClient, QdrantClientManager]:
    neo4j = Neo4jClient()
    qdrant = QdrantClientManager()
    problems = []
    if not neo4j.verify_connectivity():
        problems.append(f"Neo4j unreachable at {settings.NEO4J_URI}")
    if not qdrant.health_check():
        problems.append(f"Qdrant unreachable at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    if problems:
        sys.exit("\n".join(problems) + "\nStart them with: docker compose up -d neo4j qdrant")
    return neo4j, qdrant


def _header(title: str) -> None:
    print(f"\n== {title} " + "=" * max(0, 70 - len(title)))


def _table(rows: list[dict[str, Any]], columns: list[str], width: int = 60) -> None:
    if not rows:
        print("  (none)")
        return
    cells = [[_cell(row.get(c), width) for c in columns] for row in rows]
    sizes = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    print("  " + "  ".join(c.ljust(s) for c, s in zip(columns, sizes, strict=True)))
    print("  " + "  ".join("-" * s for s in sizes))
    for r in cells:
        print("  " + "  ".join(v.ljust(s) for v, s in zip(r, sizes, strict=True)))


def _cell(value: Any, width: int) -> str:
    text = "" if value is None else re.sub(r"\s+", " ", str(value))
    return text if len(text) <= width else text[: width - 3] + "..."


def _natural(value: Any) -> list[Any]:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", str(value))]


def _scroll(
    qdrant: QdrantClientManager,
    fields: list[str],
    flt: models.Filter | None = None,
    with_vectors: bool = False,
    max_points: int | None = None,
) -> list[Any]:
    """Pages through the collection, returning records with only ``fields`` in the payload."""
    points: list[Any] = []
    offset = None
    while True:
        page, offset = qdrant.client.scroll(
            collection_name=COLLECTION,
            scroll_filter=flt,
            limit=SCROLL_PAGE,
            offset=offset,
            with_payload=fields,
            with_vectors=with_vectors,
        )
        points.extend(page)
        if offset is None or (max_points is not None and len(points) >= max_points):
            return points[:max_points] if max_points else points


def _doc_filter(doc_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
    )


def _point_id(clause_id: str) -> str:
    """Point id that ingestion (generate_legal_chunks) assigns to a clause."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, clause_id))


def _is_zero(vector: Any) -> bool:
    return not vector or not any(vector)


def _leaked_clauses(neo4j: Neo4jClient) -> list[str]:
    """Clause nodes whose text starts with a benchmark reference answer."""
    if not TESTSET_FILE.exists():
        return []
    testset = json.loads(TESTSET_FILE.read_text(encoding="utf-8"))
    prefixes = {
        re.sub(r"\s+", " ", t["reference_answer"])[:80].strip()
        for t in testset
        if t.get("reference_answer")
    }
    rows = neo4j.execute_query(
        "MATCH (c:Clause) WHERE c.content STARTS WITH '[' "
        "RETURN c.clause_id AS clause_id, c.content AS content"
    )
    leaked = []
    for row in rows:
        body = re.sub(r"\s+", " ", (row["content"] or "").split("]: ", 1)[-1])
        if body[:80].strip() in prefixes:
            leaked.append(row["clause_id"])
    return leaked


def _load_manifest_doc_ids() -> list[str]:
    if not MANIFEST_FILE.exists():
        return []
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return [m["doc_id"] for m in manifest if m.get("kept") and m.get("doc_id")]


# --------------------------------------------------------------------------- summary


def cmd_summary(_: argparse.Namespace) -> int:
    neo4j, qdrant = _connect()
    q = neo4j.execute_query

    _header("Neo4j nodes")
    _table(
        q("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC"),
        ["label", "count"],
    )

    _header("Neo4j relationships")
    _table(
        q("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"),
        ["type", "count"],
    )

    _header("Documents by status (stubs = referenced only, no title)")
    _table(
        q(
            "MATCH (d:Document) "
            "RETURN CASE WHEN d.title IS NULL THEN '(stub)' ELSE coalesce(d.status, '(none)') END "
            "       AS status, coalesce(d.status_source, '') AS status_source, count(*) AS count "
            "ORDER BY count DESC"
        ),
        ["status", "status_source", "count"],
    )

    _header("Documents by type (non-stub)")
    _table(
        q(
            "MATCH (d:Document) WHERE d.title IS NOT NULL "
            "RETURN d.doc_type AS doc_type, count(*) AS count ORDER BY count DESC"
        ),
        ["doc_type", "count"],
    )

    _header(f"Qdrant collection '{COLLECTION}'")
    stats = qdrant.get_collection_stats()
    info = qdrant.client.get_collection(COLLECTION)
    vectors = info.config.params.vectors
    stats["vector_size"] = getattr(vectors, "size", None)
    stats["distance"] = getattr(getattr(vectors, "distance", None), "value", None)
    for key, value in stats.items():
        print(f"  {key:<22}: {value}")

    _header("Qdrant points by payload status")
    rows = []
    for status in ("in_force", "expired", "not_in_force", "active", "unknown"):
        flt = models.Filter(
            must=[models.FieldCondition(key="status", match=models.MatchValue(value=status))]
        )
        count = qdrant.client.count(COLLECTION, count_filter=flt, exact=True).count
        if count:
            rows.append({"status": status, "points": count})
    _table(rows, ["status", "points"])
    print("  (payload status is a snapshot at ingest time; retrieval trusts the graph status)")
    return 0


# --------------------------------------------------------------------------- doc


def cmd_doc(args: argparse.Namespace) -> int:
    neo4j, qdrant = _connect()
    q = neo4j.execute_query
    doc_id = normalize_doc_id(args.doc_id)

    rows = q("MATCH (d:Document {doc_id: $id}) RETURN properties(d) AS props", {"id": doc_id})
    if not rows:
        like = q(
            "MATCH (d:Document) WHERE toUpper(d.doc_id) CONTAINS toUpper($s) "
            "RETURN d.doc_id AS doc_id, d.title AS title LIMIT 10",
            {"s": args.doc_id.split("/")[0] + "/"},
        )
        print(f"Document '{doc_id}' not found in Neo4j. Similar ids:")
        _table(like, ["doc_id", "title"])
        return 1

    _header(f"Document {doc_id}")
    props = rows[0]["props"]
    for key in sorted(props):
        print(f"  {key:<20}: {_cell(props[key], 100)}")
    active = is_active_status(props.get("status"), props.get("revoked_by"))
    print(f"  {'=> in force?':<20}: {active}")

    articles = q(
        "MATCH (d:Document {doc_id: $id})-[:CONTAINS]->(a:Article) "
        "OPTIONAL MATCH (a)-[:CONTAINS]->(c:Clause) "
        "RETURN a.article_id AS article_id, a.article_number AS number, a.title AS title, "
        "       count(c) AS clauses",
        {"id": doc_id},
    )
    articles.sort(key=lambda r: _natural(r["article_id"]))
    graph_clauses = sum(r["clauses"] for r in articles)
    _header(f"Articles ({len(articles)}, {graph_clauses} clauses)")
    _table(articles[: args.limit], ["number", "clauses", "title", "article_id"])
    if len(articles) > args.limit:
        print(f"  ... {len(articles) - args.limit} more (raise --limit)")

    for direction, pattern in (
        ("Outgoing", "(n)-[r]->(x)"),
        ("Incoming", "(x)-[r]->(n)"),
    ):
        rels = q(
            "MATCH (d:Document {doc_id: $id}) OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article) "
            "WITH d, collect(a) AS arts UNWIND [d] + arts AS n "
            f"MATCH {pattern} WHERE NOT type(r) IN ['CONTAINS', 'ISSUED_BY'] "
            "RETURN type(r) AS rel, coalesce(n.article_id, n.doc_id) AS here, "
            "       coalesce(x.article_id, x.doc_id) AS other, r.scope AS scope",
            {"id": doc_id},
        )
        counts = collections.Counter(r["rel"] for r in rels)
        _header(f"{direction} relations {dict(counts) or ''}")
        _table(rels[: args.limit], ["rel", "here", "other", "scope"], width=50)

    points = _scroll(
        qdrant,
        ["clause_id", "article_id", "status", "title", "source"],
        flt=_doc_filter(doc_id),
        with_vectors=True,
    )
    zero = sum(_is_zero(p.vector) for p in points)
    statuses = collections.Counter((p.payload or {}).get("status") for p in points)
    _header("Qdrant points")
    print(f"  points               : {len(points)}  (graph clauses: {graph_clauses})")
    print(f"  payload status       : {dict(statuses)}")
    print(f"  zero vectors         : {zero}")
    leaked = sum((p.payload or {}).get("source") == LEAK_SOURCE for p in points)
    if leaked:
        print(f"  built from testset   : {leaked}  (benchmark leakage, see `check`)")
    if points and points[0].vector:
        print(f"  vector size          : {len(points[0].vector)}")

    if args.article:
        _show_article(neo4j, qdrant, doc_id, args.article)
    return 0


def _show_article(
    neo4j: Neo4jClient, qdrant: QdrantClientManager, doc_id: str, number: str
) -> None:
    rows = neo4j.execute_query(
        "MATCH (:Document {doc_id: $id})-[:CONTAINS]->(a:Article) "
        "WHERE a.article_number = $n OR a.article_id ENDS WITH $suffix "
        "OPTIONAL MATCH (a)-[:CONTAINS]->(c:Clause) "
        "RETURN a.article_id AS article_id, a.title AS title, "
        "       c.clause_id AS clause_id, c.clause_number AS clause, c.content AS content",
        {"id": doc_id, "n": str(number), "suffix": f"Article_{number}"},
    )
    _header(f"Article {number}")
    if not rows:
        print("  (not found)")
        return
    print(f"  {rows[0]['article_id']}: {rows[0]['title']}")
    clause_ids = [r["clause_id"] for r in rows if r["clause_id"]]
    point_ids = [_point_id(cid) for cid in clause_ids]
    found = {str(p.id) for p in qdrant.client.retrieve(COLLECTION, ids=point_ids)}
    for row, pid in zip([r for r in rows if r["clause_id"]], point_ids, strict=True):
        mark = "vector ok" if pid in found else "NO VECTOR"
        print(f"\n  Khoản {row['clause']} [{mark}] {row['clause_id']}")
        print("    " + _cell(row["content"], 400))


# --------------------------------------------------------------------------- search


def cmd_search(args: argparse.Namespace) -> int:
    _, qdrant = _connect()
    from src.agents import lawgraph

    embedder = lawgraph._get_embedder()
    if embedder is None:
        sys.exit("Embedder unavailable: install the extra with `make install-embeddings`.")
    graph = lawgraph._load_graph_status()

    vector = [float(x) for x in embedder.encode(args.query, normalize_embeddings=True)]
    hits = qdrant.search(vector, limit=args.top_k, status_filter=None)
    rows = []
    for hit in hits:
        payload = hit["payload"] or {}
        truth = graph.get(str(payload.get("doc_id")), {})
        rows.append(
            {
                "score": f"{hit['score']:.3f}",
                "doc_id": payload.get("doc_id"),
                "art": payload.get("article_number"),
                "khoan": payload.get("clause_number"),
                "payload_status": payload.get("status"),
                "graph_status": truth.get("status"),
                "revoked_by": truth.get("revoked_by"),
                "text": payload.get("raw_clause"),
            }
        )
    _header(f"Raw Qdrant hits (clause level, no status filter) for: {args.query}")
    _table(
        rows, ["score", "doc_id", "art", "khoan", "graph_status", "revoked_by", "text"], width=45
    )

    agent = lawgraph.LawGraphAgent()
    final = agent.retrieve_provisions([args.query], [], query=args.query)
    _header("Final LawGraphAgent ranking (article level, in-force first)")
    _table(
        [
            {
                "rank": i,
                "doc_id": r.get("doc_id"),
                "article": r.get("article"),
                "status": r.get("status"),
                "revoked_by": r.get("revoked_by"),
                "source": r.get("source") or r.get("retriever"),
            }
            for i, r in enumerate(final, 1)
        ],
        ["rank", "doc_id", "article", "status", "revoked_by", "source"],
    )
    return 0


# --------------------------------------------------------------------------- check


def cmd_check(args: argparse.Namespace) -> int:
    neo4j, qdrant = _connect()
    q = neo4j.execute_query
    results: list[tuple[str, str, str]] = []

    def record(level: str, name: str, detail: str, examples: list[Any] | None = None) -> None:
        results.append((level, name, detail))
        if examples:
            detail += "  e.g. " + ", ".join(str(e) for e in examples[:5])
        print(f"  [{level:<4}] {name}: {detail}")

    _header("Loading graph and vector payloads")
    docs = {
        r["doc_id"]: r
        for r in q(
            "MATCH (d:Document) OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article) "
            "RETURN d.doc_id AS doc_id, d.title AS title, d.status AS status, "
            "       d.revoked_by AS revoked_by, d.status_source AS status_source, "
            "       count(a) AS articles"
        )
    }
    graph_clauses = {
        r["clause_id"]: r["doc_id"]
        for r in q(
            "MATCH (d:Document)-[:CONTAINS]->(:Article)-[:CONTAINS]->(c:Clause) "
            "RETURN c.clause_id AS clause_id, d.doc_id AS doc_id"
        )
    }
    superseded = {
        r["doc_id"]
        for r in q(
            "MATCH (:Document)-[:SUPERSEDES]->(d:Document) RETURN DISTINCT d.doc_id AS doc_id"
        )
    }
    points = _scroll(qdrant, ["clause_id", "doc_id", "status", "source"])
    # Ingestion keys every point by uuid5(clause_id), so match on point id, not payload.
    point_payloads = {str(p.id): p.payload or {} for p in points}
    print(f"  {len(docs)} documents, {len(graph_clauses)} clauses, {len(points)} points")

    _header("Checks")
    leaked_points = [pl for pl in point_payloads.values() if pl.get("source") == LEAK_SOURCE]
    record(
        "FAIL" if leaked_points else "OK",
        "benchmark leakage (Qdrant)",
        f"{len(leaked_points)} points were built from testset reference answers",
        sorted({pl.get("doc_id") for pl in leaked_points}),
    )
    leaked_clauses = _leaked_clauses(neo4j)
    record(
        "FAIL" if leaked_clauses else "OK",
        "benchmark leakage (Neo4j)",
        f"{len(leaked_clauses)} Clause nodes contain a testset reference answer",
        leaked_clauses,
    )
    corpus = _load_manifest_doc_ids()
    if not corpus:
        record("WARN", "manifest", f"{MANIFEST_FILE} missing; corpus checks skipped")
    else:
        missing = [d for d in corpus if d not in docs]
        stubs = [d for d in corpus if d in docs and not docs[d]["title"]]
        record(
            "FAIL" if missing else "OK",
            "corpus docs in Neo4j",
            f"{len(corpus) - len(missing)}/{len(corpus)} present",
            missing,
        )
        record(
            "FAIL" if stubs else "OK",
            "corpus docs with metadata",
            f"{len(stubs)} are title-less stubs",
            stubs,
        )
        empty = [d for d in corpus if d in docs and not docs[d]["articles"]]
        record(
            "WARN" if empty else "OK",
            "corpus docs with articles",
            f"{len(empty)} have 0 articles (parser could not split them)",
            empty,
        )
        no_source = [d for d in corpus if d in docs and not docs[d]["status_source"]]
        record(
            "WARN" if no_source else "OK",
            "MoJ status applied",
            f"{len(no_source)} corpus docs lack status_source",
            no_source,
        )
        expired = [
            d
            for d in corpus
            if d in docs and not is_active_status(docs[d]["status"], docs[d]["revoked_by"])
        ]
        unlinked = [d for d in expired if d not in superseded and not docs[d]["revoked_by"]]
        record(
            "INFO",
            "replacement links",
            f"{len(expired) - len(unlinked)}/{len(expired)} inactive corpus docs have a "
            "successor (SUPERSEDES or revoked_by)",
            unlinked,
        )

    no_vector = [c for c in graph_clauses if _point_id(c) not in point_payloads]
    record(
        "WARN" if no_vector else "OK",
        "clauses with a vector",
        f"{len(graph_clauses) - len(no_vector)}/{len(graph_clauses)}",
        no_vector,
    )
    placeholder = [c for c in graph_clauses if c.endswith(":Clause_?")]
    record(
        "WARN" if placeholder else "OK",
        "placeholder clause ids",
        f"{len(placeholder)} Clause nodes end in ':Clause_?' (left over from older ingests)",
        placeholder,
    )
    expected_ids = {_point_id(c) for c in graph_clauses}
    legacy = [pid for pid, pl in point_payloads.items() if not pl.get("clause_id")]
    record(
        "WARN" if legacy else "OK",
        "points with clause_id payload",
        f"{len(legacy)} points have no clause_id (older payload schema)",
        sorted({point_payloads[pid].get("doc_id") for pid in legacy}),
    )
    orphans = [
        pid for pid, pl in point_payloads.items() if pl.get("clause_id") and pid not in expected_ids
    ]
    record(
        "WARN" if orphans else "OK",
        "vectors with a graph clause",
        f"{len(orphans)} points have no matching Clause node",
        [point_payloads[pid].get("clause_id") for pid in orphans],
    )

    mismatch = [
        pl["doc_id"]
        for pid, pl in point_payloads.items()
        if pid in expected_ids
        and pl.get("doc_id") in docs
        and is_active_status(pl.get("status"))
        != is_active_status(docs[pl["doc_id"]]["status"], docs[pl["doc_id"]]["revoked_by"])
    ]
    record(
        "INFO",
        "payload vs graph status",
        f"{len(mismatch)} points disagree (harmless: retrieval uses the graph)",
        sorted(set(mismatch)),
    )

    contradictory = [
        d for d, r in docs.items() if r["revoked_by"] and r["status"] in ("in_force", "active")
    ]
    record(
        "WARN" if contradictory else "OK",
        "status vs revoked_by",
        f"{len(contradictory)} docs are in_force but have revoked_by",
        contradictory,
    )

    sample = _scroll(qdrant, [], with_vectors=True, max_points=args.sample)
    zero = [str(p.id) for p in sample if _is_zero(p.vector)]
    sizes = collections.Counter(len(p.vector or []) for p in sample)
    record(
        "FAIL" if zero else "OK",
        "zero vectors",
        f"{len(zero)}/{len(sample)} sampled points are all zeros",
        zero,
    )
    record("FAIL" if len(sizes) > 1 else "OK", "vector size", f"{dict(sizes)}")

    failed = sum(1 for level, _, _ in results if level == "FAIL")
    _header(f"{'FAILED' if failed else 'PASSED'}: {failed} failing check(s)")
    return 1 if failed else 0


# --------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="counts and status breakdown").set_defaults(func=cmd_summary)

    doc = sub.add_parser("doc", help="inspect one document")
    doc.add_argument("doc_id", help="e.g. 40/2024/TT-NHNN (case and Đ/D insensitive)")
    doc.add_argument("--article", help="also print the clauses of this article number")
    doc.add_argument("--limit", type=int, default=30, help="rows per table")
    doc.set_defaults(func=cmd_doc)

    search = sub.add_parser("search", help="semantic search over Qdrant")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=10)
    search.set_defaults(func=cmd_search)

    check = sub.add_parser("check", help="consistency checks (exit 1 on failure)")
    check.add_argument("--sample", type=int, default=2000, help="points to scan for zero vectors")
    check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
