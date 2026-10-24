#!/usr/bin/env python3
"""Measure retrieval determinism: same query, repeated calls, count distinct doc sets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

from src.agents.lawgraph import LawGraphAgent  # noqa: E402

testset = {int(r["question_id"]): r for r in json.loads(
    (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8"))}

agent = LawGraphAgent()
agent.dense_retrieve("khởi động", top_k=1)

print(f"BENCH_RETRIEVER={__import__('os').getenv('BENCH_RETRIEVER', 'neo4j')}")
for qid in (16, 6, 55):
    q = testset[qid]["question"]
    sets = []
    for _ in range(5):
        hits = agent.retrieve_provisions(
            subgoals=[f"Subgoal 1: {q}"], keywords=["ngân hàng"], query=q
        )
        sets.append(tuple(sorted({h.get("doc_id") for h in hits})))
    uniq = len(set(sets))
    print(f"\nQ{qid} {q[:60]}")
    print(f"  GT={testset[qid]['relevant_articles']}")
    print(f"  distinct doc-sets over 5 identical calls: {uniq}")
    for s in dict.fromkeys(sets):
        print(f"    {s}  (x{sets.count(s)})")
