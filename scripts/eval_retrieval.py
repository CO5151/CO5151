#!/usr/bin/env python3
"""Reproducible retrieval benchmark on the 100-question SBV test set.

Evaluates LawGraphAgent across three configurations:
  - dense_only : bi-encoder semantic search (deduplicated per article)
  - bm25_only  : Neo4j lexical BM25 or local BM25+IDF fallback
  - hybrid_rrf : default production Reciprocal Rank Fusion (K=60)

Saves aggregate + per-question raw results to ``eval/raw/retrieval_100.json``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.agents.lawgraph import (  # noqa: E402
    _CHUNK_EXPORT,
    _get_neo4j_client,
    LawGraphAgent,
)
from src.evaluation.metrics import (  # noqa: E402
    f2_at_k,
    hit_at_k,
    precision_at_k,
    recall_at_k,
)

DEFAULT_TESTSET = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
DEFAULT_OUT = WORKSPACE / "eval/raw/retrieval_100.json"

MODES: tuple[tuple[str, bool, bool], ...] = (
    ("dense_only", False, True),
    ("bm25_only", True, False),
    ("hybrid_rrf", True, True),
)


def _corpus_stats(questions: list[dict[str, Any]]) -> dict[str, Any]:
    chunks = json.loads(_CHUNK_EXPORT.read_text(encoding="utf-8")) if _CHUNK_EXPORT.exists() else []
    docs = {c.get("payload", {}).get("doc_id") for c in chunks}
    articles = {
        f"{c.get('payload', {}).get('doc_id')}:{c.get('payload', {}).get('article_number')}"
        for c in chunks
    }
    gt_lens = [len(q["relevant_articles"]) for q in questions]
    p2_max = sum(min(length, 2) / 2.0 for length in gt_lens) / len(questions)
    return {
        "testset_size": len(questions),
        "corpus_docs": len(docs),
        "corpus_unique_articles": len(articles),
        "corpus_chunks": len(chunks),
        "avg_gt_per_question": round(sum(gt_lens) / len(questions), 4),
        "theoretical_max_p2": round(p2_max, 4),
        "neo4j_connected": _get_neo4j_client() is not None,
    }


def _run_mode(
    agent: LawGraphAgent,
    questions: list[dict[str, Any]],
    mode_name: str,
    use_neo4j: bool,
    use_dense: bool,
    top_k: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        t0 = time.perf_counter()
        prov = agent.retrieve_provisions(
            subgoals=[q["question"]],
            keywords=[],
            use_neo4j=use_neo4j,
            use_dense=use_dense,
            dense_top_k=top_k,
            query=q["question"],
        )
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        retrieved = [f"{p['doc_id']}:{p.get('article', '')}".rstrip(":") for p in prov]
        gt = q["relevant_articles"]
        rows.append(
            {
                "id": q.get("id", idx),
                "question": q["question"],
                "ground_truth": gt,
                "retrieved": retrieved,
                "latency_ms": latency_ms,
                "p2": precision_at_k(retrieved, gt, 2),
                "r2": recall_at_k(retrieved, gt, 2),
                "f2_2": f2_at_k(retrieved, gt, 2),
                "hit2": hit_at_k(retrieved, gt, 2),
                "p3": precision_at_k(retrieved, gt, 3),
                "r3": recall_at_k(retrieved, gt, 3),
                "f2_3": f2_at_k(retrieved, gt, 3),
                "hit3": hit_at_k(retrieved, gt, 3),
                "p6": precision_at_k(retrieved, gt, 6),
                "r6": recall_at_k(retrieved, gt, 6),
                "f2_6": f2_at_k(retrieved, gt, 6),
                "hit6": hit_at_k(retrieved, gt, 6),
            }
        )

    n = len(rows)
    mean = lambda key: round(sum(r[key] for r in rows) / n, 4)
    p2 = mean("p2")
    summary = {
        "mode": mode_name,
        "top_k": top_k,
        "p2": p2,
        "r2": mean("r2"),
        "f2_2": mean("f2_2"),
        "hit2": mean("hit2"),
        "noise2": round(1.0 - p2, 4),
        "p3": mean("p3"),
        "r3": mean("r3"),
        "f2_3": mean("f2_3"),
        "hit3": mean("hit3"),
        "p6": mean("p6"),
        "r6": mean("r6"),
        "f2_6": mean("f2_6"),
        "hit6": mean("hit6"),
        "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / n, 2),
    }
    return {"summary": summary, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LawGraphAgent retrieval on SBV benchmark.")
    parser.add_argument("--testset", type=Path, default=DEFAULT_TESTSET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()

    logging.disable(logging.WARNING)
    questions = json.loads(args.testset.read_text(encoding="utf-8"))
    agent = LawGraphAgent()

    # Warm up index loads outside per-question latency
    corpus = _corpus_stats(questions)
    results_by_mode: dict[str, Any] = {}
    for mode_name, use_neo4j, use_dense in MODES:
        res = _run_mode(agent, questions, mode_name, use_neo4j, use_dense, args.top_k)
        results_by_mode[mode_name] = res
        s = res["summary"]
        print(
            f"{mode_name:12s} | P@2={s['p2']*100:5.2f}% | R@2={s['r2']*100:5.2f}% | "
            f"F2@2={s['f2_2']:.4f} | Hit@2={s['hit2']*100:5.1f}% | "
            f"R@6={s['r6']*100:5.2f}% | Noise@2={s['noise2']*100:5.2f}% | "
            f"ms/q={s['avg_latency_ms']:.1f}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "corpus": corpus,
        "top_k": args.top_k,
        "modes": {k: v["summary"] for k, v in results_by_mode.items()},
        "per_question": {k: v["rows"] for k, v in results_by_mode.items()},
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
