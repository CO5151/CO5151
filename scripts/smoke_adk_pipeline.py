#!/usr/bin/env python3
"""Smoke-test the real ADK pipeline on a couple of SBV questions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

from src.agents.adk_pipeline import LegalPilotADK  # noqa: E402
from src.agents.claim_auditor import ClaimAuditorAgent  # noqa: E402
from src.agents.lawgraph import LawGraphAgent  # noqa: E402

testset = {int(r["question_id"]): r for r in json.loads(
    (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8"))}

retriever = LawGraphAgent()
retriever.dense_retrieve("khởi động", top_k=1)
auditor = ClaimAuditorAgent()

pipeline = LegalPilotADK(retriever=retriever, auditor=auditor)

for qid in (16, 29, 65):
    item = testset[qid]
    state = pipeline.run(item["question"])
    print("=" * 78)
    print(f"Q{qid}: {item['question']}")
    print(f"GT   : {item['relevant_articles']}")
    print(f"plan : {str(state.get('plan'))[:160]}")
    print(f"rets : {[c.get('doc_id') for c in (state.get('retrieved_clauses') or [])]}")
    print(f"audit: {state.get('audit_report')}")
    print(f"out  : {str(state.get('final_dossier'))[:400]}")
