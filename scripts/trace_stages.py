#!/usr/bin/env python3
"""Replicate LegalOrchestrator.run step by step and print what each stage holds."""

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

from src.agents.orchestrator import LegalOrchestrator  # noqa: E402
from src.core.statute_status import is_active_status  # noqa: E402


def summary(tag: str, clauses: list[dict]) -> None:
    docs = Counter(c.get("doc_id") for c in clauses or [])
    print(f"  {tag:<34} n={len(clauses or []):>2}  k={len(docs)}  {dict(docs)}")


qid = int(sys.argv[1]) if len(sys.argv) > 1 else 16
testset = {int(r["question_id"]): r for r in json.loads(
    (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8"))}
item = testset[qid]

orch = LegalOrchestrator()
subgoals, keywords = orch.plan_subgoals(item["question"])
print(f"Q{qid}: {item['question']}")
print(f"GT: {item['relevant_articles']}\n")

res = orch.runner.dispatch(
    "LawGraphAgent", {"subgoals": subgoals, "keywords": keywords, "query": item["question"]}
)
retrieved = res.data if res.success else []
print(f"dispatch success={res.success}")
summary("runner.dispatch retrieved", retrieved)
print(f"  sample keys: {sorted(retrieved[0].keys()) if retrieved else '-'}")
print(f"  sample keys: {sorted(retrieved[0].keys()) if retrieved else '-'}")

active = [c for c in retrieved if is_active_status(c.get("status"), c.get("revoked_by"))]
summary("after is_active_status", active)
print(f"  statuses seen: {Counter(repr(c.get('status')) for c in retrieved)}")

audit = orch.runner.dispatch("ClaimAuditorAgent", retrieved, context={"enable_live_vbpl": False})
ar = audit.data
print(f"\naudit: fully_verified={ar.is_fully_verified} grounding={ar.grounding_rate} "
      f"claims={ar.total_claims} grounded={ar.grounded_claims}")
print(f"  live_verifications doc ids: {[v.get('doc_id') for v in ar.live_verifications]}")
print(f"  unsupported claims cited   : {[c.cited_statute for c in ar.unsupported_claims]}")
print(f"  unsupported claim reasons  : {[getattr(c, 'reason', '')[:70] for c in ar.unsupported_claims]}")
