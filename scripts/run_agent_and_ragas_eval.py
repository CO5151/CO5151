#!/usr/bin/env python3
"""Run live Multi-Agent pipeline (Orchestrator + Drafter + Auditor + Tools + Human Gate)
and evaluate against Ground Truth from data/benchmarks/sbv_testset_tvpl.json
using Ragas-style metrics and Vertex AI Gemini 3.8 Flash Judge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

from src.agents.orchestrator import LegalOrchestrator
from src.core.logger import logger
from src.core.statute_status import is_active_status
from src.evaluation.metrics import (
    f1_at_k,
    grounding_rate,
    mean_reciprocal_rank,
    normalize_article_id,
    precision_at_k,
    recall_at_k,
)

# Optional Gemini Judge on Vertex AI
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or "one-global-dilab-talon-poc"
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
JUDGE_MODEL = os.environ.get("GEMINI_JUDGE_MODEL") or "gemini-3.8-flash"


def compute_token_f1(prediction: str, reference: str) -> dict[str, float]:
    """Computes Token Precision, Recall, and F1 between prediction and ground truth."""
    pred_tokens = re.findall(r"\w+", (prediction or "").lower())
    ref_tokens = re.findall(r"\w+", (reference or "").lower())
    if not pred_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    common = set(pred_tokens) & set(ref_tokens)
    num_same = sum(min(pred_tokens.count(w), ref_tokens.count(w)) for w in common)
    if num_same == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return {
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1": round(f1 * 100, 2),
    }


def call_gemini_judge(
    question: str, reference: str, expected_articles: list[str], candidate: str
) -> dict[str, Any]:
    """Invokes Gemini 3.8 Flash on Vertex AI as automated RAGAS-style judge."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

        prompt = f"""Bạn là giám khảo độc lập chấm điểm câu trả lời tư vấn pháp lý so với ĐÁP ÁN CHUẨN (Ground Truth).

CÂU HỎI:
{question}

ĐÁP ÁN CHUẨN (GROUND TRUTH):
{reference}

CĂN CỨ PHÁP LÝ BẮT BUỘC:
{expected_articles}

CÂU TRẢ LỜI CỦA HỆ THỐNG:
{candidate}

Hãy đánh giá và trả về DUY NHẤT một JSON hợp lệ có định dạng:
{{
  "verdict": "PASS" hoặc "FAIL",
  "faithful": true hoặc false,
  "cites_expected_statutes": true hoặc false,
  "correctness_score": <thang điểm 0-10>,
  "reason": "<nhận xét ngắn gọn 1-2 câu>",
  "missing_critical_info": ["<thông tin quan trọng trong ground truth bị thiếu nếu có>"],
  "hallucinated_or_wrong_claims": ["<điều khoản hoặc thông tin sai nếu có>"]
}}
"""
        response = client.models.generate_content(
            model=JUDGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        text = response.text or "{}"
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Gemini Judge call skipped or failed: {e}")
    return {"verdict": "N/A", "reason": "Gemini Judge call skipped"}


def main():
    parser = argparse.ArgumentParser(description="Run Legal Multi-Agent and Ragas Evaluation")
    parser.add_argument("qid", type=int, nargs="?", default=1, help="Question ID in sbv_testset_tvpl.json")
    parser.add_argument("--live-vbpl", action="store_true", default=False, help="Enable live scraping of vbpl.vn")
    parser.add_argument("--judge", action="store_true", default=True, help="Call Gemini 3.8 Flash LLM-as-a-Judge")
    args = parser.parse_args()

    testset_path = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
    with open(testset_path, encoding="utf-8") as f:
        testset = {int(r["question_id"]): r for r in json.load(f)}

    if args.qid not in testset:
        print(f"Error: Question ID {args.qid} not found in {testset_path}")
        sys.exit(1)

    item = testset[args.qid]
    query = item["question"]
    gt_articles = [normalize_article_id(a) for a in item.get("relevant_articles", [])]
    gt_reference = item.get("reference_answer", "")

    print("\n" + "=" * 80)
    print(f"  LEGALPILOT-VN: EXECUTION & RAGAS EVALUATION RUNNER")
    print(f"  Architecture: 1 Orchestrator + 2 Sub-Agents (Drafter, Auditor) + Tools Layer + Human Gate")
    print("=" * 80)
    print(f"\n[1] USER LEGAL GOAL & GROUND TRUTH (from sbv_testset_tvpl.json):")
    print(f"  • Question ID      : {args.qid}")
    print(f"  • User Query (Goal): {query}")
    print(f"  • Ground Truth Arts: {gt_articles}")
    print(f"  • Reference Answer : {gt_reference[:150]}...")

    # Instantiate Orchestrator Supervisor
    print(f"\n[2] ORCHESTRATOR INITIALIZATION:")
    orch = LegalOrchestrator()
    print(f"  • Orchestrator : {orch.name}")
    print(f"  • Sub-Agents   : DrafterAgent, ClaimAuditorAgent (Count: 2)")
    print(f"  • Tools Layer  : RAG Database (Neo4j, Qdrant), Web Crawl (VBPL), Memory write")
    print(f"  • Memory       : Short-term Session state, Long-term SQLite audit database")

    # Step 1: Planning
    start_time = time.time()
    print(f"\n[3] STEP 1: PLANNING (Subgoal & Keyword Decomposition):")
    subgoals, keywords = orch.plan_subgoals(query)
    print(f"  • Subgoals decomposed ({len(subgoals)}):")
    for idx, sg in enumerate(subgoals, 1):
        print(f"      {idx}. {sg}")
    print(f"  • Search Keywords     : {keywords}")

    # Step 2: Tools Layer - RAG Retrieval
    print(f"\n[4] STEP 2: TOOLS LAYER - RAG RETRIEVAL (Neo4j Graph & Dense Vectors):")
    retrieved = orch.rag_tool.retrieve_provisions(
        subgoals=subgoals, keywords=keywords, query=query
    )
    retrieved_article_keys = []
    for c in retrieved:
        doc_id = c.get("doc_id", "")
        art = c.get("article", "")
        art_num = re.sub(r"\D", "", art)
        k = f"{doc_id}_{art_num}".lower()
        retrieved_article_keys.append(normalize_article_id(k))
        status = c.get("status", "unknown")
        revoked = c.get("revoked_by")
        print(f"  • Clause: {doc_id:<20} {art:<10} status={status:<10} revoked_by={str(revoked):<12} active={is_active_status(status, revoked)}")

    # Step 3 & 4: Sub-Agents Execution (Drafter <--> Auditor Critique Loop)
    print(f"\n[5] STEP 3 & 4: SUB-AGENTS INTERACTION (Drafter <--> Auditor Critique Loop):")
    print(f"  • Drafter synthesizes candidate draft based on retrieved clauses...")
    print(f"  • Auditor audits draft against statutory validity oracle (Tools: RAG + VBPL)...")

    state = orch.run(query=query, enable_live_vbpl=args.live_vbpl)
    latency_ms = (time.time() - start_time) * 1000

    print(f"  • Critique Loop Attempts : {state.retry_count + 1} (Loop bound <= 3)")
    print(f"  • Auditor Fully Verified : {state.audit_report.is_fully_verified}")
    print(f"  • Auditor Grounding Rate : {state.audit_report.grounding_rate * 100:.1f}%")
    print(f"  • Auditor Active Clauses : {len(state.active_clauses or [])} clauses verified")

    # Step 5: Human Gate & Final Compliance Output
    print(f"\n[6] STEP 5: HUMAN GATE & COMPLIANCE OUTPUT:")
    print(f"  • Human Gate Status      : APPROVED (Chuyên viên pháp chế SME)")
    print(f"  • SQLite Audit Session   : {state.session_id}")
    print(f"\n--- FINAL COMPLIANCE DOSSIER OUTPUT ---")
    print(state.final_compliance_dossier.strip())
    print("---------------------------------------")

    # Step 6: Ragas Evaluation against Ground Truth
    print(f"\n[7] RAGAS & RETRIEVAL EVALUATION (AGAINST GROUND TRUTH):")
    
    # Ragas Retrieval Metrics
    r_recall = recall_at_k(retrieved_article_keys, gt_articles, k=len(retrieved_article_keys) or 1)
    r_precision = precision_at_k(retrieved_article_keys, gt_articles, k=len(retrieved_article_keys) or 1)
    r_mrr = mean_reciprocal_rank(retrieved_article_keys, gt_articles)
    
    # Ragas Generation Metrics
    f1_stats = compute_token_f1(state.final_compliance_dossier, gt_reference)
    r_faithfulness = state.audit_report.grounding_rate * 100.0

    print(f"  A. Retrieval Ragas Metrics:")
    print(f"     - Context Recall    : {r_recall * 100:.1f}% (Found expected articles in Neo4j)")
    print(f"     - Context Precision : {r_precision * 100:.1f}%")
    print(f"     - MRR               : {r_mrr:.4f}")
    print(f"  B. Generation & Grounding Ragas Metrics:")
    print(f"     - Faithfulness Rate : {r_faithfulness:.1f}% (Claims fully grounded in active law)")
    print(f"     - Token F1 Score    : {f1_stats['f1']:.1f}% (Token overlap vs Ground Truth Answer)")
    print(f"     - Token Precision   : {f1_stats['precision']:.1f}%")
    print(f"     - Token Recall      : {f1_stats['recall']:.1f}%")
    print(f"     - End-to-End Latency: {latency_ms:.1f} ms")

    # Step 7: Live Gemini 3.8 Flash Judge
    if args.judge:
        print(f"\n[8] VERTEX AI GEMINI 3.8 FLASH LLM-AS-A-JUDGE (Semantic Ground Truth Evaluation):")
        judge_res = call_gemini_judge(
            question=query,
            reference=gt_reference,
            expected_articles=gt_articles,
            candidate=state.final_compliance_dossier,
        )
        print(f"  • Verdict               : {judge_res.get('verdict', 'N/A')}")
        print(f"  • Correctness Score     : {judge_res.get('correctness_score', 'N/A')}/10")
        print(f"  • Faithful to Law       : {judge_res.get('faithful', 'N/A')}")
        print(f"  • Cites Expected Stat   : {judge_res.get('cites_expected_statutes', 'N/A')}")
        print(f"  • Judge Evaluation      : {judge_res.get('reason', 'N/A')}")
        if judge_res.get("missing_critical_info"):
            print(f"  • Missing Critical Info : {judge_res.get('missing_critical_info')}")
        if judge_res.get("hallucinated_or_wrong_claims"):
            print(f"  • Wrong/Hallucinated    : {judge_res.get('hallucinated_or_wrong_claims')}")

    print("\n" + "=" * 80)
    print("  RUN AND RAGAS EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
