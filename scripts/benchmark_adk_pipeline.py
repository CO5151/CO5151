#!/usr/bin/env python3
"""Benchmark the REAL Google ADK pipeline on the SBV test set.

Pipeline under test: ``src/agents/adk_pipeline.py``
    SequentialAgent[ PlannerAgent -> RetrievalWorker
                      -> LoopAgent[AuditWorker, RecoveryWorker]
                      -> DrafterAgent ]
driven by ADK ``Runner`` with a SQLite ``DatabaseSessionService``.

Usage:
    BENCH_CONCISE=1 BENCH_RETRIEVER=dense \
        /Users/tungdl/Documents/CO5151/.venv-adk/bin/python \
        scripts/benchmark_adk_pipeline.py --limit 100 --tag adkreal
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

from src.agents.adk_pipeline import LegalPilotADK  # noqa: E402
from src.agents.claim_auditor import ClaimAuditorAgent  # noqa: E402
from src.agents.lawgraph import LawGraphAgent  # noqa: E402

TESTSET = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
BENCH = WORKSPACE / "data/benchmarks"


def strip_diacritics(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def norm_doc(doc: str) -> str:
    return re.sub(r"\s+", "", strip_diacritics(doc).upper())


def canonical_article_id(doc_id: str, art_raw: str) -> str:
    """Canonicalize (doc_id, article) into format matching relevant_articles (e.g. '12/2022/tt-nhnn_15')."""
    d = str(doc_id).strip().lower().replace("nđ-cp", "nd-cp")
    m = re.search(r"(\d+[a-zA-Z]?)", str(art_raw))
    num = m.group(1).lower() if m else str(art_raw).strip().lower()
    return f"{d}_{num}"


def gt_docs(item: dict[str, Any]) -> list[str]:
    docs: list[str] = []
    for art in item.get("relevant_articles", []):
        doc = norm_doc(art.split("_")[0])
        if doc and doc not in docs:
            docs.append(doc)
    return docs


def gt_articles(item: dict[str, Any]) -> list[str]:
    """Extract canonical article IDs from benchmark ground truth."""
    return [str(a).strip().lower().replace("nđ-cp", "nd-cp") for a in item.get("relevant_articles", [])]


def article_hit(answer: str, item: dict[str, Any]) -> float:
    """Checks whether the answer cites both the document and the exact article number."""
    arts = gt_articles(item)
    if not arts:
        return 0.0
    flat = strip_diacritics(answer).lower()
    hits = 0
    for art in arts:
        parts = art.split("_")
        doc_code = parts[0]
        num = parts[1] if len(parts) > 1 else ""
        raw_num = doc_code.split("/")[0]
        year = doc_code.split("/")[1] if len(doc_code.split("/")) > 1 else ""
        doc_found = (doc_code in flat) or (f"{raw_num}/{year}" in flat)
        art_found = bool(re.search(rf"dieu\s+{re.escape(num)}\b|khoan\s+\d+\s+dieu\s+{re.escape(num)}\b", flat))
        if doc_found and art_found:
            hits += 1
    return hits / len(arts)


def citation_recall(answer: str, docs: list[str]) -> float:
    if not docs:
        return 0.0
    hay = re.sub(r"[^A-Z0-9/\-]", "", norm_doc(answer))
    return sum(1 for d in docs if d in hay) / len(docs)


def metrics_at_k(retrieved: list[str], gt: list[str]) -> dict[str, Any]:
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
    parser.add_argument("--tag", default="adkreal")
    args = parser.parse_args()

    data = json.loads(TESTSET.read_text(encoding="utf-8"))
    subset = data[args.offset : args.offset + args.limit]

    counter = TokenCounter()
    litellm.callbacks = [counter]

    retriever = LawGraphAgent()
    t_warm = time.perf_counter()
    retriever.dense_retrieve("khởi động bộ mã hoá", top_k=1)
    print(f">>> Embedder warm-up: {(time.perf_counter() - t_warm) * 1000:.0f} ms")

    auditor = ClaimAuditorAgent()
    pipeline = LegalPilotADK(retriever=retriever, auditor=auditor)
    print(f">>> ADK graph: {pipeline.graph.name} = {[a.name for a in pipeline.graph.sub_agents]}")

    rows: list[dict[str, Any]] = []
    print(f">>> Real ADK pipeline on {len(subset)} SBV questions")
    for item in subset:
        q = item["question"]
        docs = gt_docs(item)

        counter.total = 0
        counter.calls = 0
        t0 = time.perf_counter()
        try:
            state = pipeline.run(q)
            error = ""
        except Exception as exc:  # noqa: BLE001
            state, error = {}, f"{type(exc).__name__}: {exc}"
        elapsed = (time.perf_counter() - t0) * 1000

        clauses = state.get("retrieved_clauses") or []
        dossier = str(state.get("final_dossier") or "")
        ret_articles = [canonical_article_id(c.get("doc_id", ""), c.get("article", "")) for c in clauses]
        target_articles = gt_articles(item)
        row = {
            "question_id": item["question_id"],
            "question": q,
            "gt_docs": docs,
            "gt_articles": target_articles,
            "tokens": counter.total,
            "llm_calls": counter.calls,
            "latency_ms": round(elapsed, 1),
            "retrieval_attempts": int(state.get("retrieval_attempt", 0) or 0),
            "retrieved": len(clauses),
            "retrieval": metrics_at_k(ret_articles, target_articles),
            "citation_recall": round(citation_recall(dossier, docs), 4),
            "article_hit": round(article_hit(dossier, item), 4),
            "output": dossier,
            "error": error,
        }
        rows.append(row)
        print(
            f"  Q{row['question_id']:>3} {row['tokens']:>5}tok {row['llm_calls']}calls "
            f"{elapsed:>7.0f}ms P@k={row['retrieval']['p_at_k']:.2f} "
            f"R@k={row['retrieval']['r_at_k']:.2f} hit={row['retrieval']['hit_at_k']:.0f} "
            f"art={row['article_hit']:.2f} k={row['retrieval']['k']}"
            + (f" ERR={error[:60]}" if error else "")
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
        "n_errors": sum(1 for r in rows if r["error"]),
        "_metadata": {
            "method": "measured",
            "runtime": "Google ADK 2.12.0 (SequentialAgent + LoopAgent + Runner + DatabaseSessionService/SQLite)",
            "graph": pipeline.graph.name,
            "sub_agents": [a.name for a in pipeline.graph.sub_agents],
            "entrypoint": "src/agents/adk_pipeline.py::LegalPilotADK.run",
            "model": os.getenv("ADK_MODEL", "deepseek/deepseek-chat") + " (alias -> DeepSeek Flash V4.1)",
            "retriever": os.getenv("BENCH_RETRIEVER", "neo4j"),
            "concise": bool(os.getenv("BENCH_CONCISE")),
            "testset": "data/benchmarks/sbv_testset_tvpl.json",
            "questions": [r["question_id"] for r in rows],
            "n_questions": len(subset),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "script": "scripts/benchmark_adk_pipeline.py",
            "token_source": "LiteLLM usage.total_tokens (CustomLogger)",
        },
    }

    BENCH.mkdir(parents=True, exist_ok=True)
    out = BENCH / f"benchmark_adkpipe_{args.tag}_stats.json"
    raw = BENCH / f"benchmark_adkpipe_{args.tag}_raw.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raw.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== ADK PIPELINE AGGREGATE ===")
    print(
        f"adk_pipeline: {payload['token_mean']:.1f} tok | {payload['lat_mean_ms']:.0f} ms | "
        f"k={payload['k_mean']:.1f} | P@k={payload['p_at_k']:.1f}% | R@k={payload['r_at_k']:.1f}% | "
        f"Hit@k={payload['hit_at_k']:.1f}% | ans_article={payload['article_hit']:.1f}% | "
        f"errors={payload['n_errors']}"
    )
    print(f"Saved: {out}\nRaw:   {raw}")


if __name__ == "__main__":
    main()
