#!/usr/bin/env python3
"""Run sample benchmark questions against live Neo4j and report full end-to-end pipeline results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

from src.agents.orchestrator import LegalOrchestrator

QUESTION_IDS = [5, 41, 1]  # Representative questions from SBV benchmark


def main():
    testset_path = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
    if not testset_path.exists():
        print(f"Testset not found at {testset_path}")
        return

    testset = {int(r["question_id"]): r for r in json.loads(testset_path.read_text(encoding="utf-8"))}
    orch = LegalOrchestrator()

    print("=" * 80)
    print("LEGALPILOT-VN: BENCHMARK SAMPLE TEST REPORT (LIVE NEO4J ENGINE)")
    print("=" * 80)

    for qid in QUESTION_IDS:
        item = testset.get(qid)
        if not item:
            continue

        print(f"\n{'#' * 80}")
        print(f"TEST CASE Q{qid}: {item['question']}")
        print(f"Reference Ground Truth: {item.get('relevant_articles')}")
        print(f"{'#' * 80}")

        # 1. Planner Phase
        subgoals, keywords = orch.plan_subgoals(item["question"])
        print("\n[1. PLANNER AGENT]")
        print(f"  * Subgoals ({len(subgoals)}):")
        for sg in subgoals:
            print(f"    - {sg}")
        print(f"  * Keywords: {keywords}")

        # 2. Retrieval & Audit & Drafting
        state = orch.run(query=item["question"], enable_live_vbpl=False)

        print("\n[2. LAWGRAPH RETRIEVAL (NEO4J CYPHIER & GRAPH TRAVERSAL)]")
        retrieved = state.retrieved_clauses or []
        print(f"  * Total candidate clauses retrieved: {len(retrieved)}")
        for c in retrieved:
            print(f"    - [{c.get('doc_id')}] {c.get('article')} | Status: {c.get('status')} | Revoked By: {c.get('revoked_by')}")

        print("\n[3. CLAIM AUDITOR REPORT]")
        report = state.audit_report
        print(f"  * Fully Verified: {report.is_fully_verified}")
        print(f"  * Grounding Rate: {report.grounding_rate * 100:.1f}%")
        print(f"  * Backtrack Retries: {state.retry_count}")
        if report.unsupported_claims:
            print(f"  * Unsupported/Revoked Claims: {[c.cited_statute for c in report.unsupported_claims]}")
        else:
            print("  * Unsupported/Revoked Claims: None (All claims grounded in active law)")

        print("\n[4. FINAL COMPLIANCE DOSSIER (DRAFTER AGENT)]")
        dossier = state.final_compliance_dossier or state.candidate_draft or "None"
        for line in dossier.strip().splitlines():
            print(f"  {line}")

    print("\n" + "=" * 80)
    print("ALL TEST CASES EXECUTED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    main()
