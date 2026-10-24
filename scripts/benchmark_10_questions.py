#!/usr/bin/env python3
"""Run the 3 architectures on N questions from the SBV test set (default 10).

Companion to ``benchmark_10_runs.py``:
  * benchmark_10_runs.py      -> 1 question x 10 repetitions  (variance study)
  * benchmark_10_questions.py -> 10 questions x 1 run each   (coverage study)

Scoring (deterministic, no LLM judge):
  * doc_hit    : answer cites the ground-truth legal document (from ``relevant_articles``)
  * citation_recall : fraction of ground-truth documents cited
  * token_f1   : token-level F1 against ``reference_answer`` (diacritics-insensitive)
  * tokens / latency_ms

Usage:
    .venv/bin/python scripts/benchmark_10_questions.py --limit 10
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

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import run_langgraph_deepseek as bench  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage  # noqa: E402

TESTSET = WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json"
OUTPUT_PATH = WORKSPACE / "data/benchmarks/benchmark_10_questions_stats.json"
RAW_PATH = WORKSPACE / "data/benchmarks/benchmark_10_questions_raw.json"

REACT_SYSTEM = (
    "Bạn là chuyên gia tư vấn pháp lý. Hãy sử dụng các công cụ để tra cứu "
    "văn bản và kiểm tra hiệu lực trước khi kết luận."
)
if os.getenv("BENCH_CONCISE"):
    REACT_SYSTEM += bench.CONCISE_INSTRUCTION

# ---------------------------------------------------------------------------
# Generic recovery worker (the original one is hard-coded to the e-wallet query,
# which is fine for the single-query variance study but invalid for a test set).
# Patched onto the imported module so the graph builder picks it up.
# ---------------------------------------------------------------------------
def generic_recovery_worker(state: dict[str, Any]) -> dict[str, Any]:
    hits = bench.dense_hybrid_search(state["user_query"], top_k=4)
    return {"retrieved_provisions": hits}


bench.ma_recovery_worker = generic_recovery_worker


# ---------------------------------------------------------------------------
# Same for the workflow synthesizer: the original prompt hard-codes
# "hãy tư vấn ngắn gọn mức phạt/điều kiện", which is only valid for the
# single penalty question used in the variance study.
# ---------------------------------------------------------------------------
def generic_wf_synthesizer(state: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        f"Trả lời câu hỏi pháp lý sau dựa trên các căn cứ được cung cấp.\n\n"
        f"Câu hỏi: {state['query']}\n\n"
        f"Căn cứ pháp lý:\n{state['retrieved_context']}\n\n"
        "Yêu cầu: trả lời trực tiếp câu hỏi, nêu rõ số hiệu văn bản và điều khoản. "
        "Nếu căn cứ không đủ để trả lời thì nói rõ là không đủ."
    )
    if os.getenv("BENCH_CONCISE"):
        prompt += bench.CONCISE_INSTRUCTION
    resp = bench.llm.invoke([HumanMessage(content=prompt)])
    tokens = resp.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    return {"final_output": resp.content, "total_tokens": state["total_tokens"] + tokens}


bench.wf_synthesizer = generic_wf_synthesizer


# ---------------------------------------------------------------------------
# Deterministic scoring helpers
# ---------------------------------------------------------------------------
def strip_diacritics(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def norm_doc(doc: str) -> str:
    """'12/2022/tt-nhnn' / '52/2024/NĐ-CP' -> '12/2022/TT-NHNN' / '52/2024/ND-CP'."""
    doc = strip_diacritics(doc).upper()
    return re.sub(r"\s+", "", doc)


def norm_doc_in_text(text: str) -> str:
    """Normalise a whole answer so doc codes survive formatting noise."""
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
    hits = sum(1 for d in docs if d in hay)
    return hits / len(docs)


def article_hit(answer: str, item: dict[str, Any]) -> float:
    """Does the answer mention the right 'Điều <n>' of the right document?"""
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
    txt = strip_diacritics(text).lower()
    return re.findall(r"[a-z0-9]+", txt)


def token_f1(pred: str, ref: str) -> float:
    p, r = words(pred), words(ref)
    if not p or not r:
        return 0.0
    from collections import Counter

    common = Counter(p) & Counter(r)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p)
    recall = overlap / len(r)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Retrieval-level metrics (precision/recall belong to the retriever, not the
# generated answer). Granularity: document. GT = relevant_articles' doc codes.
# ---------------------------------------------------------------------------
CTX_DOC_RE = re.compile(r"^\[([^\]]+)\]", flags=re.M)
TOOL_DOC_RE = re.compile(r"\[Doc:\s*([^|\]]+?)\s*\|")


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


def docs_from_context(ctx: str) -> list[str]:
    return [norm_doc(d) for d in CTX_DOC_RE.findall(ctx or "")]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
def run_question(
    item: dict[str, Any], wf_graph: Any, react_graph: Any, ma_graph: Any
) -> dict[str, Any]:
    q = item["question"]
    ref = item.get("reference_answer", "")
    docs = gt_docs(item)
    out: dict[str, Any] = {"question_id": item["question_id"], "question": q, "gt_docs": docs}

    t0 = time.perf_counter()
    wf = wf_graph.invoke(
        {"query": q, "category": "", "retrieved_context": "", "final_output": "", "total_tokens": 0}
    )
    out["workflow"] = {
        "tokens": int(wf["total_tokens"]),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "citation_recall": round(citation_recall(wf["final_output"], docs), 4),
        "article_hit": round(article_hit(wf["final_output"], item), 4),
        "token_f1": round(token_f1(wf["final_output"], ref), 4),
        "retrieval": metrics_at_k(docs_from_context(wf["retrieved_context"]), docs),
        "output": wf["final_output"],
    }

    t0 = time.perf_counter()
    react = react_graph.invoke(
        {"messages": [SystemMessage(content=REACT_SYSTEM), HumanMessage(content=q)],
         "total_tokens": 0, "step_count": 0}
    )
    react_out = react["messages"][-1].content
    react_docs: list[str] = []
    for msg in react["messages"]:
        if isinstance(msg, ToolMessage):
            react_docs.extend(norm_doc(d) for d in TOOL_DOC_RE.findall(str(msg.content)))
    out["react"] = {
        "tokens": int(react["total_tokens"]),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "steps": int(react["step_count"]),
        "citation_recall": round(citation_recall(react_out, docs), 4),
        "article_hit": round(article_hit(react_out, item), 4),
        "token_f1": round(token_f1(react_out, ref), 4),
        "retrieval": metrics_at_k(react_docs, docs),
        "output": react_out,
    }

    t0 = time.perf_counter()
    ma = ma_graph.invoke(
        {"user_query": q, "subgoals": [], "retrieved_provisions": [], "audited_provisions": [],
         "audit_passed": True, "retry_count": 0, "final_dossier": "", "total_tokens": 0}
    )
    out["multi_agent"] = {
        "tokens": int(ma["total_tokens"]),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "subgoals": len(ma["subgoals"]),
        "retrieval": metrics_at_k(
            [norm_doc(p.get("doc_id", "")) for p in ma["retrieved_provisions"]], docs
        ),
        "citation_recall": round(citation_recall(ma["final_dossier"], docs), 4),
        "article_hit": round(article_hit(ma["final_dossier"], item), 4),
        "token_f1": round(token_f1(ma["final_dossier"], ref), 4),
        "output": ma["final_dossier"],
    }
    return out


def agg(values: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.mean(values), 4) if values else 0.0,
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("workflow", "react", "multi_agent"):
        tokens = [r[name]["tokens"] for r in rows]
        lat = [r[name]["latency_ms"] for r in rows]
        rec = [r[name]["citation_recall"] for r in rows]
        art = [r[name]["article_hit"] for r in rows]
        f1 = [r[name]["token_f1"] for r in rows]
        pk = [r[name]["retrieval"]["p_at_k"] for r in rows]
        rk = [r[name]["retrieval"]["r_at_k"] for r in rows]
        hk = [r[name]["retrieval"]["hit_at_k"] for r in rows]
        kk = [r[name]["retrieval"]["k"] for r in rows]
        out[name] = {
            "token_mean": round(statistics.mean(tokens), 1),
            "token_std": round(statistics.stdev(tokens), 1) if len(tokens) > 1 else 0.0,
            "lat_mean_ms": round(statistics.mean(lat), 1),
            "lat_std_ms": round(statistics.stdev(lat), 1) if len(lat) > 1 else 0.0,
            # retrieval-level (document granularity)
            "k_mean": round(statistics.mean(kk), 2),
            "p_at_k": round(100.0 * statistics.mean(pk), 2),
            "r_at_k": round(100.0 * statistics.mean(rk), 2),
            "hit_at_k": round(100.0 * statistics.mean(hk), 2),
            # answer-level
            "doc_hit_rate": round(100.0 * statistics.mean([1.0 if r > 0 else 0.0 for r in rec]), 2),
            "citation_recall": round(100.0 * statistics.mean(rec), 2),
            "article_hit": round(100.0 * statistics.mean(art), 2),
            "token_f1": round(100.0 * statistics.mean(f1), 2),
            "empty_answers": sum(1 for r in rows if len(r[name]["output"].strip()) < 20),
        }
        if name == "react":
            out[name]["step_mean"] = round(statistics.mean([r[name]["steps"] for r in rows]), 2)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--tag", default="", help="suffix for output files, e.g. 'full'")
    args = parser.parse_args()

    out_path = OUTPUT_PATH.with_name(
        f"benchmark_{args.tag}_stats.json" if args.tag else OUTPUT_PATH.name
    )
    raw_path = RAW_PATH.with_name(
        f"benchmark_{args.tag}_raw.json" if args.tag else RAW_PATH.name
    )

    data = json.loads(TESTSET.read_text(encoding="utf-8"))
    subset = data[args.offset : args.offset + args.limit]

    wf_graph = bench.build_workflow_graph()
    react_graph = bench.build_react_graph()
    ma_graph = bench.build_multiagent_graph()

    print(f">>> {len(subset)} questions x {args.runs} run x 3 architectures (DeepSeek Flash V4.1)")
    rows: list[dict[str, Any]] = []
    for rep in range(1, args.runs + 1):
        for i, item in enumerate(subset, 1):
            t0 = time.perf_counter()
            row = run_question(item, wf_graph, react_graph, ma_graph)
            rows.append(row)
            print(
                f"  [{rep}/{args.runs}] Q{item['question_id']:>3} "
                f"wf={row['workflow']['tokens']:>5}tok/{row['workflow']['citation_recall']:.2f} "
                f"react={row['react']['tokens']:>5}tok/{row['react']['citation_recall']:.2f} "
                f"ma={row['multi_agent']['tokens']:>5}tok/{row['multi_agent']['citation_recall']:.2f} "
                f"({time.perf_counter()-t0:.1f}s)"
            )

    stats = aggregate(rows)
    payload = {
        **stats,
        "_metadata": {
            "method": "measured",
            "model": "deepseek-chat (alias -> DeepSeek Flash V4.1)",
            "temperature": 0.1,
            "testset": "data/benchmarks/sbv_testset_tvpl.json",
            "questions": [r["question_id"] for r in rows],
            "n_questions": len(subset),
            "runs": args.runs,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "script": "scripts/benchmark_10_questions.py",
            "concise": bool(os.getenv("BENCH_CONCISE")),
            "corpus_chunks": len(bench.ALL_CHUNKS),
            "corpus_documents": len({c["payload"].get("doc_id") for c in bench.ALL_CHUNKS}),
            "patched": {
                "recovery_worker": "generic (state['user_query'])",
                "wf_synthesizer": "generic prompt (original hard-codes 'mức phạt')",
            },
            "metrics": {
                "doc_hit_rate": "% câu trả lời có trích đúng ít nhất 1 văn bản chuẩn",
                "citation_recall": "% văn bản chuẩn được trích (trung bình)",
                "article_hit": "% điều khoản chuẩn được nêu đúng số Điều",
                "token_f1": "F1 token với reference_answer (bỏ dấu)",
            },
        },
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== AGGREGATE ===")
    for name in ("workflow", "react", "multi_agent"):
        r = payload[name]
        print(
            f"{name:12s}: {r['token_mean']:>8.1f} tok | {r['lat_mean_ms']:>7.0f} ms | "
            f"k={r['k_mean']:.1f} | P@k={r['p_at_k']:5.1f}% | R@k={r['r_at_k']:5.1f}% | "
            f"Hit@k={r['hit_at_k']:5.1f}% | ans_doc_hit={r['doc_hit_rate']:5.1f}% | "
            f"ans_article={r['article_hit']:5.1f}%"
        )
    print(f"\nSaved: {out_path}")
    print(f"Raw:   {raw_path}")


if __name__ == "__main__":
    main()
