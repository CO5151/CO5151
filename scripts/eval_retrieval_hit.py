#!/usr/bin/env python3
"""Retrieval-only check of LawGraphAgent on the 100 SBV questions (no LLM calls).

Uses the deterministic fallback planner so runs are comparable and free, then
reports document- and article-level Hit@k, the share of in-force results and
latency against the ground truth in data/benchmarks/sbv_testset_tvpl.json.

    BENCH_RETRIEVER=neo4j python scripts/eval_retrieval_hit.py
    python scripts/eval_retrieval_hit.py              # default (dense Qdrant) retriever
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.agents.lawgraph import LawGraphAgent  # noqa: E402
from src.core.statute_status import is_active_status  # noqa: E402


def _norm_doc(value: str) -> str:
    return value.upper().replace("Đ", "D").strip()


def _fallback_plan(query: str) -> tuple[list[str], list[str]]:
    """Mirrors LegalOrchestrator.plan_subgoals when the LLM is unavailable."""
    statute_patterns = re.findall(r"\d+/\d+/[A-ZĐa-zđ\-_]+", query)
    clean = [w.lower() for w in re.findall(r"\b[\w\-]+\b", query, flags=re.UNICODE) if len(w) > 2]
    keywords = list(dict.fromkeys(statute_patterns + clean[:8]))
    subgoals = [
        f"Xác định quy định pháp lý điều chỉnh cho yêu cầu: {query}",
        f"Tra cứu căn cứ và điều kiện áp dụng liên quan đến: {' '.join(clean[:6])}",
    ]
    return subgoals, keywords


def main() -> None:
    testset = json.loads(
        (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8")
    )
    agent = LawGraphAgent()
    doc_hits = art_hits = 0
    active_share: list[float] = []
    latencies: list[float] = []
    for item in testset:
        gold = [g.rsplit("_", 1) for g in item["relevant_articles"]]
        gold_docs = {_norm_doc(d) for d, _ in gold}
        gold_arts = {(_norm_doc(d), a) for d, a in gold}

        subgoals, keywords = _fallback_plan(item["question"])
        start = time.perf_counter()
        results = agent.retrieve_provisions(subgoals, keywords, query=item["question"])
        latencies.append((time.perf_counter() - start) * 1000)

        got_docs = {_norm_doc(r.get("doc_id", "")) for r in results}
        got_arts = {
            (_norm_doc(r.get("doc_id", "")), str(r.get("article", "")).replace("Điều", "").strip())
            for r in results
        }
        doc_hits += bool(gold_docs & got_docs)
        art_hits += bool(gold_arts & got_arts)
        if results:
            active = sum(is_active_status(r.get("status"), r.get("revoked_by")) for r in results)
            active_share.append(active / len(results))

    n = len(testset)
    print(f"retriever        : {os.getenv('BENCH_RETRIEVER') or 'default'}")
    print(f"questions        : {n}")
    print(f"doc Hit@k        : {doc_hits / n:.1%}")
    print(f"article Hit@k    : {art_hits / n:.1%}")
    print(f"in-force results : {statistics.mean(active_share):.1%}")
    print(f"latency median   : {statistics.median(latencies):.0f} ms")


if __name__ == "__main__":
    main()
