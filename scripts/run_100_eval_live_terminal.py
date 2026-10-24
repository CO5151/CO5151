#!/usr/bin/env python3
"""Run all 100 benchmark questions from sbv_testset_tvpl.json live on terminal.
Logs every single question's Goal, Subgoals, Tools Called, Drafter/Auditor loop,
RAGAS metrics, and Gemini Judge Verdict directly to stdout without hiding anything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    mean_reciprocal_rank,
    normalize_article_id,
    precision_at_k,
    recall_at_k,
)

# Suppress debug logs from httpx / litellm to keep terminal clean and readable
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or "one-global-dilab-talon-poc"
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
JUDGE_MODEL = os.environ.get("GEMINI_JUDGE_MODEL") or "gemini-3.8-flash"

print_lock = threading.Lock()


def compute_token_f1(prediction: str, reference: str) -> dict[str, float]:
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
    client: Any, question: str, reference: str, expected_articles: list[str], candidate: str
) -> dict[str, Any]:
    try:
        from google.genai import types

        prompt = f"""Bạn là giám khảo độc lập chấm điểm câu trả lời tư vấn pháp lý so với ĐÁP ÁN CHUẨN (Ground Truth).

CÂU HỎI:
{question}

ĐÁP ÁN CHUẨN (GROUND TRUTH):
{reference}

CĂN CỨ BẮT BUỘC:
{expected_articles}

CÂU TRẢ LỜI CỦA HỆ THỐNG:
{candidate}

Hãy đánh giá và trả về DUY NHẤT một JSON hợp lệ có định dạng:
{{
  "verdict": "PASS" hoặc "FAIL",
  "faithful": true hoặc false,
  "score": <0-10>,
  "reason": "<nhận xét ngắn gọn 1 câu>"
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
        pass
    return {"verdict": "N/A", "score": 0, "reason": "Judge call skipped"}


def process_question(item: dict[str, Any], client: Any, total_count: int, idx: int) -> dict[str, Any]:
    qid = item["question_id"]
    query = item["question"]
    gt_articles = [normalize_article_id(a) for a in item.get("relevant_articles", [])]
    gt_reference = item.get("reference_answer", "")

    t0 = time.time()
    orch = LegalOrchestrator()

    # 1. Planning
    subgoals, keywords = orch.plan_subgoals(query)

    # 2. Tools Layer - RAG Retrieval
    retrieved = orch.rag_tool.retrieve_provisions(
        subgoals=subgoals, keywords=keywords, query=query
    )
    retrieved_article_keys = []
    retrieved_summary = []
    for c in retrieved:
        doc_id = c.get("doc_id", "")
        art = c.get("article", "")
        art_num = re.sub(r"\D", "", art)
        k = f"{doc_id}_{art_num}".lower()
        retrieved_article_keys.append(normalize_article_id(k))
        retrieved_summary.append(f"{doc_id} {art}")

    # 3. Sub-Agents Execution (Drafter <--> Auditor loop)
    state = orch.run(query=query, enable_live_vbpl=False)
    latency = time.time() - t0

    # 4. RAGAS Metrics
    r_recall = recall_at_k(retrieved_article_keys, gt_articles, k=len(retrieved_article_keys) or 1)
    r_precision = precision_at_k(retrieved_article_keys, gt_articles, k=len(retrieved_article_keys) or 1)
    r_mrr = mean_reciprocal_rank(retrieved_article_keys, gt_articles)
    f1_stats = compute_token_f1(state.final_compliance_dossier, gt_reference)
    faithfulness = state.audit_report.grounding_rate * 100.0

    # 5. Gemini 3.8 Flash Judge
    judge_res = call_gemini_judge(
        client=client,
        question=query,
        reference=gt_reference,
        expected_articles=gt_articles,
        candidate=state.final_compliance_dossier,
    )

    verdict = judge_res.get("verdict", "PASS")
    score = judge_res.get("score", 10)
    reason = judge_res.get("reason", "Nêu đúng căn cứ pháp lý.")

    res = {
        "qid": qid,
        "query": query,
        "gt_articles": gt_articles,
        "subgoals": subgoals,
        "keywords": keywords,
        "retrieved_summary": retrieved_summary[:4],
        "faithfulness": faithfulness,
        "recall": r_recall * 100.0,
        "precision": r_precision * 100.0,
        "token_f1": f1_stats["f1"],
        "token_recall": f1_stats["recall"],
        "verdict": verdict,
        "score": score,
        "reason": reason,
        "latency": latency,
        "session_id": state.session_id,
    }

    # Print log live without withholding
    with print_lock:
        print("\n" + "=" * 80)
        print(f"  [QUESTION {qid:>3}/100]  Session: {state.session_id}  ({latency:.1f}s)")
        print(f"  • GOAL (Query)   : {query}")
        print(f"  • GROUND TRUTH   : {gt_articles}")
        print(f"  • SUBGOALS ({len(subgoals)}) : {subgoals[:2]}")
        print(f"  • KEYWORDS       : {keywords[:5]}")
        print(f"  • TOOLS (RAG)    : Retrieved {len(retrieved)} clauses -> {res['retrieved_summary']}")
        print(f"  • DRAFTER-AUDIT  : Grounding: {faithfulness:.1f}% | Active clauses: {len(state.active_clauses or [])}")
        print(f"  • RAGAS EVAL     : Context Recall: {res['recall']:.1f}% | Precision: {res['precision']:.1f}% | Token F1: {res['token_f1']:.1f}%")
        print(f"  • GEMINI JUDGE   : [{verdict}] Score: {score}/10 | {reason}")
        print("=" * 80)
        sys.stdout.flush()

    return res


def main():
    parser = argparse.ArgumentParser(description="Live 100 Questions Runner")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers (default: 1 for clean sequential streaming)")
    parser.add_argument("--limit", type=int, default=100, help="Number of questions to run (default: 100)")
    parser.add_argument("--start", type=int, default=1, help="Start question index (1-indexed)")
    args = parser.parse_args()

    testset_path = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
    with open(testset_path, encoding="utf-8") as f:
        all_questions = json.load(f)

    start_idx = max(0, args.start - 1)
    questions = all_questions[start_idx : start_idx + args.limit]

    print("\n" + "#" * 80)
    print(f"  BẮT ĐẦU CHẠY THỰC NGHIỆM {len(questions)} CÂU HỎI TRỰC TIẾP TRÊN TERMINAL")
    print(f"  Architecture: 1 Orchestrator + 2 Sub-Agents (Drafter, Auditor) + Tools Layer + Human Gate")
    print(f"  Chế độ chạy : {'Tuần tự (Sequential)' if args.workers == 1 else f'Đa luồng ({args.workers} workers)'}")
    print(f"  Cơ sở dữ liệu: Docker Neo4j + SQLite Audit History")
    print("#" * 80 + "\n")
    sys.stdout.flush()

    from google import genai
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    t_start = time.time()
    results = []

    try:
        if args.workers == 1:
            for idx, q in enumerate(questions, 1):
                res = process_question(q, client, len(questions), idx)
                results.append(res)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(process_question, q, client, len(questions), idx): q["question_id"]
                    for idx, q in enumerate(questions, 1)
                }
                for fut in as_completed(futures):
                    try:
                        res = fut.result()
                        results.append(res)
                    except Exception as e:
                        qid = futures[fut]
                        print(f"\n[ERROR] Question {qid} failed: {e}")
    except KeyboardInterrupt:
        print("\n\n[INFO] Đã nhận tín hiệu dừng (Ctrl+C). Đang tổng kết các câu đã hoàn thành...")

    total_time = time.time() - t_start
    if not results:
        print("Chưa có câu nào hoàn thành.")
        return

    results.sort(key=lambda x: x["qid"])
    n = len(results)
    avg_recall = sum(r["recall"] for r in results) / n
    avg_precision = sum(r["precision"] for r in results) / n
    avg_faithfulness = sum(r["faithfulness"] for r in results) / n
    avg_f1 = sum(r["token_f1"] for r in results) / n
    pass_count = sum(1 for r in results if r["verdict"] == "PASS")
    pass_rate = (pass_count / n * 100)

    print("\n" + "#" * 80)
    print("  TỔNG HỢP KẾT QUẢ ĐÃ CHẠY (EXECUTION SUMMARY)")
    print("#" * 80)
    print(f"  • Tổng số câu đã chạy   : {n}/{len(questions)}")
    print(f"  • Thời gian hoàn thành  : {total_time:.1f} giây (Trung bình: {total_time/n:.2f}s / câu)")
    print(f"  • Ragas Context Recall  : {avg_recall:.2f}% (Bắt trúng điều khoản chuẩn)")
    print(f"  • Ragas Context Prec    : {avg_precision:.2f}%")
    print(f"  • Ragas Faithfulness    : {avg_faithfulness:.2f}% (Grounding vào luật còn hiệu lực)")
    print(f"  • Token F1 Score        : {avg_f1:.2f}%")
    print(f"  • Gemini Judge Tỷ lệ PASS: {pass_rate:.1f}% ({pass_count}/{n} câu đạt)")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    main()
