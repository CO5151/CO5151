#!/usr/bin/env python3
"""Trace one question through the ADK pipeline: planner -> retrieval -> status filter."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

from src.agents.lawgraph import LawGraphAgent  # noqa: E402
from src.agents.orchestrator import LegalOrchestrator  # noqa: E402
from src.core.statute_status import is_active_status  # noqa: E402

qid = int(sys.argv[1]) if len(sys.argv) > 1 else 16
testset = {int(r["question_id"]): r for r in json.loads(
    (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8"))}
item = testset[qid]

orch = LegalOrchestrator()
subgoals, keywords = orch.plan_subgoals(item["question"])

print("=" * 78)
print(f"Q{qid}: {item['question']}")
print(f"GT      : {item['relevant_articles']}")
print(f"subgoals: {subgoals}")
print(f"keywords: {keywords}")
print("=" * 78)

# Raw retrieval exactly as the orchestrator does it
retrieved = orch.lawgraph_agent.retrieve_provisions(
    subgoals=subgoals, keywords=keywords, query=item["question"]
)
print(f"retrieved {len(retrieved)} clauses")
for c in retrieved:
    print(f"  {c.get('doc_id'):<22} {c.get('article'):<10} status={c.get('status')!r:<12} "
          f"revoked_by={c.get('revoked_by')!r:<16} active={is_active_status(c.get('status'), c.get('revoked_by'))}")

docs = Counter(c.get("doc_id") for c in retrieved)
print(f"\ndoc-level k = {len(docs)} -> {dict(docs)}")

active = [c for c in retrieved if is_active_status(c.get("status"), c.get("revoked_by"))]
print(f"after is_active_status filter: {len(active)} clauses, "
      f"{len({c.get('doc_id') for c in active})} docs")

# Now run the full pipeline to see what state.retrieved_clauses ends up as
state = orch.run(query=item["question"], enable_live_vbpl=False)
final_docs = Counter(c.get("doc_id") for c in (state.retrieved_clauses or []))
print(f"\nstate.retrieved_clauses after run(): {len(state.retrieved_clauses or [])} clauses, "
      f"k={len(final_docs)} -> {dict(final_docs)}")
print(f"retry_count={state.retry_count}  fully_verified={state.audit_report.is_fully_verified} "
      f"grounding={state.audit_report.grounding_rate}")
