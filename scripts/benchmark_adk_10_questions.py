#!/usr/bin/env python3
"""Run the Google ADK production pipeline on N questions from the SBV test set.

Counterpart of ``benchmark_10_questions.py`` (which drives the LangGraph harness):
same 10 questions, same scoring, but the pipeline under test is the real
``LegalOrchestrator`` + ``ADKRunner`` from ``src/agents/``.

    .venv-adk/bin/python scripts/benchmark_adk_10_questions.py --limit 10

Notes
-----
* ``enable_live_vbpl=False`` so validity comes from the local graph export
  (deterministic, no network) -- same information the LangGraph harness used.
* Tokens come from a LiteLLM ``CustomLogger`` because ``LegalAgentState`` has
  no token counters.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

import litellm  # noqa: E402
from litellm.integrations.custom_logger import CustomLogger  # noqa: E402

from src.agents.orchestrator import LegalOrchestrator  # noqa: E402

TESTSET = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
OUTPUT_PATH = WORKSPACE / "data/benchmarks/benchmark_adk_10_questions_stats.json"
RAW_PATH = WORKSPACE / "data/benchmarks/benchmark_adk_10_questions_raw.json"


# ---------------------------------------------------------------------------
# Deterministic scoring (identical definitions to benchmark_10_questions.py)
# ---------------------------------------------------------------------------
def strip_diacritics(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def norm_doc(doc: str) -> str:
    return re.sub(r"\s+", "", strip_diacritics(doc).upper())


def norm_doc_in_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9/\-]", "", norm_doc(text))


def gt_docs(item: dict[str, Any]) -> list[str]:
    docs: list[str] = []
    for art in item.get("relevant_articles", []):
        doc = norm_doc(art.split("_")[0])
        if doc and doc not in docs:
            docs.append(doc)
    return docs


def citation_recall(answer: str, docs: list[str]) -> float:
    if not docs:
        return 0.0
    hay = norm_doc_in_text(answer)
    return sum(1 for d in docs if d in hay) / len(docs)


def article_hit(answer: str, item: dict[str, Any]) -> float:
    arts = item.get("relevant_articles", [])
    if not arts:
        return 0.0
    flat = strip_diacritics(answer).lower()
    hits = 0
    for art in arts:
        try:
            num = art.rsplit("_", 1)[1]
        except IndexError:
            continue
        if re.search(rf"dieu\s+{re.escape(num)}\b", flat):
            hits += 1
    return hits / len(arts)


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", strip_diacritics(text).lower())


def metrics_at_k(retrieved: list[str], gt: list[str]) -> dict[str, Any]:
    """Retrieval-level Precision@k / Recall@k / Hit@k at document granularity."""
    uniq = list(dict.fromkeys(retrieved))
    if not uniq:
        return {"k": 0, "p_at_k": 0.0, "r_at_k": 0.0, "hit_at_k": 0.0}
    hit = len(set(uniq) & set(gt))
    return {
        "k": len(uniq),
        "p_at_k": round(hit / len(uniq), 4),
        "r_at_k": round(hit / len(gt), 4) if gt else 0.0,
        "hit_at_k": 1.0 if hit else 0.0,
    }


def token_f1(pred: str, ref: str) -> float:
    from collections import Counter

    p, r = words(pred), words(ref)
    if not p or not r:
        return 0.0
    overlap = sum((Counter(p) & Counter(r)).values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(r)
    return 2 * precision * recall / (precision + recall)


class TokenCounter(CustomLogger):
    def __init__(self) -> None:
        self.total = 0
        self.calls = 0

    def _acc(self, response_obj: Any) -> None:
        usage = getattr(response_obj, "usage", None)
        if usage is not None:
            self.total += int(getattr(usage, "total_tokens", 0) or 0)
            self.calls += 1

    def log_success_event(self, kwargs, response_obj, start_time, end_time):  # noqa: D102
        self._acc(response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):  # noqa: D102
        self._acc(response_obj)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--live", action="store_true", help="enable live VBPL lookup")
    parser.add_argument("--tag", default="", help="suffix for output files, e.g. 'full'")
    args = parser.parse_args()

    out_path = OUTPUT_PATH.with_name(
        f"benchmark_adk_{args.tag}_stats.json" if args.tag else OUTPUT_PATH.name
    )
    raw_path = RAW_PATH.with_name(
        f"benchmark_adk_{args.tag}_raw.json" if args.tag else RAW_PATH.name
    )

    data = json.loads(TESTSET.read_text(encoding="utf-8"))
    subset = data[args.offset : args.offset + args.limit]

    counter = TokenCounter()
    litellm.callbacks = [counter]
    orch = LegalOrchestrator()

    # Warm up the embedder so the first question does not absorb model-load time.
    t_warm = time.perf_counter()
    orch.lawgraph_agent.dense_retrieve("khởi động bộ mã hoá", top_k=1)
    print(f">>> Embedder warm-up: {(time.perf_counter() - t_warm) * 1000:.0f} ms")

    rows: list[dict[str, Any]] = []
    print(f">>> Google ADK pipeline on {len(subset)} SBV questions (live_vbpl={args.live})")
    for item in subset:
        q = item["question"]
        ref = item.get("reference_answer", "")
        docs = gt_docs(item)

        counter.total = 0
        counter.calls = 0
        t0 = time.perf_counter()
        state = orch.run(query=q, enable_live_vbpl=args.live)
        elapsed = (time.perf_counter() - t0) * 1000
        dossier = getattr(state, "final_compliance_dossier", "") or ""

        row = {
            "question_id": item["question_id"],
            "question": q,
            "gt_docs": docs,
            "tokens": counter.total,
            "llm_calls": counter.calls,
            "latency_ms": round(elapsed, 1),
            "plan_steps": len(getattr(state, "plan_steps", []) or []),
            "retrieved": len(getattr(state, "retrieved_clauses", []) or []),
            "retrieval": metrics_at_k(
                [norm_doc(str(c.get("doc_id", ""))) for c in (getattr(state, "retrieved_clauses", []) or [])],
                docs,
            ),
            "citation_recall": round(citation_recall(dossier, docs), 4),
            "article_hit": round(article_hit(dossier, item), 4),
            "token_f1": round(token_f1(dossier, ref), 4),
            "output": dossier,
        }
        rows.append(row)
        print(
            f"  Q{row['question_id']:>3} {row['tokens']:>5}tok {row['llm_calls']}calls "
            f"{elapsed:>7.0f}ms P@k={row['retrieval']['p_at_k']:.2f} "
            f"R@k={row['retrieval']['r_at_k']:.2f} hit={row['retrieval']['hit_at_k']:.0f} "
            f"art={row['article_hit']:.2f} k={row['retrieval']['k']}"
        )

    tok = [r["tokens"] for r in rows]
    lat = [r["latency_ms"] for r in rows]
    payload = {
        "token_mean": round(statistics.mean(tok), 1),
        "token_std": round(statistics.stdev(tok), 1) if len(tok) > 1 else 0.0,
        "lat_mean_ms": round(statistics.mean(lat), 1),
        "lat_std_ms": round(statistics.stdev(lat), 1) if len(lat) > 1 else 0.0,
        "doc_hit_rate": round(100.0 * statistics.mean([1.0 if r["citation_recall"] > 0 else 0.0 for r in rows]), 2),
        "k_mean": round(statistics.mean([r["retrieval"]["k"] for r in rows]), 2),
        "p_at_k": round(100.0 * statistics.mean([r["retrieval"]["p_at_k"] for r in rows]), 2),
        "r_at_k": round(100.0 * statistics.mean([r["retrieval"]["r_at_k"] for r in rows]), 2),
        "hit_at_k": round(100.0 * statistics.mean([r["retrieval"]["hit_at_k"] for r in rows]), 2),
        "citation_recall": round(100.0 * statistics.mean([r["citation_recall"] for r in rows]), 2),
        "article_hit": round(100.0 * statistics.mean([r["article_hit"] for r in rows]), 2),
        "token_f1": round(100.0 * statistics.mean([r["token_f1"] for r in rows]), 2),
        "_metadata": {
            "method": "measured",
            "runtime": "Google ADK (google-adk + LiteLLM)",
            "entrypoint": "src/agents/orchestrator.py::LegalOrchestrator.run",
            "model": "deepseek/deepseek-chat (alias -> DeepSeek Flash V4.1)",
            "testset": "data/benchmarks/sbv_testset_tvpl.json",
            "questions": [r["question_id"] for r in rows],
            "n_questions": len(subset),
            "enable_live_vbpl": args.live,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "script": "scripts/benchmark_adk_10_questions.py",
            "concise": bool(os.getenv("BENCH_CONCISE")),
            "token_source": "LiteLLM usage.total_tokens (CustomLogger)",
        },
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== ADK AGGREGATE ===")
    print(
        f"multi_agent_adk: {payload['token_mean']:.1f} tok | {payload['lat_mean_ms']:.0f} ms | "
        f"k={payload['k_mean']:.1f} | P@k={payload['p_at_k']:.1f}% | R@k={payload['r_at_k']:.1f}% | "
        f"Hit@k={payload['hit_at_k']:.1f}% | ans_article={payload['article_hit']:.1f}%"
    )


if __name__ == "__main__":
    main()
