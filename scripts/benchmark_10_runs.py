#!/usr/bin/env python3
"""Run the three agent architectures N times against DeepSeek and aggregate stats.

This is the reproducible harness behind the benchmark table in the S1-7 slides.
It reuses the exact graph builders and prompts from ``run_langgraph_deepseek.py``
so the reported numbers are API-measured, not simulated.

Usage:
    .venv/bin/python scripts/benchmark_10_runs.py --runs 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import run_langgraph_deepseek as bench  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

QUERY = (
    "Doanh nghiệp muốn xin cấp phép cung ứng dịch vụ Ví điện tử thì vốn điều lệ "
    "tối thiểu cần bao nhiêu tiền và căn cứ theo văn bản quy phạm pháp luật nào hiện hành?"
)
REACT_SYSTEM = (
    "Bạn là chuyên gia tư vấn pháp lý. Hãy sử dụng các công cụ để tra cứu "
    "văn bản và kiểm tra hiệu lực trước khi kết luận."
)
OUTPUT_PATH = WORKSPACE / "data/benchmarks/benchmark_10_runs_stats.json"
RAW_PATH = WORKSPACE / "data/benchmarks/benchmark_10_runs_raw.json"


def is_correct(text: str) -> bool:
    """Deterministic outcome check for the e-wallet licence question."""
    compact = (text or "").replace(",", ".")
    cites_active = "52/2024" in compact
    states_capital = (
        "50.000.000.000" in compact
        or "50 tỷ" in compact
        or "50.000.000" in compact
    )
    return bool(cites_active and states_capital)


def summarise(values: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def run_once(
    wf_graph: Any, react_graph: Any, ma_graph: Any
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    t0 = time.perf_counter()
    wf = wf_graph.invoke(
        {
            "query": QUERY,
            "category": "",
            "retrieved_context": "",
            "final_output": "",
            "total_tokens": 0,
        }
    )
    wf_ms = (time.perf_counter() - t0) * 1000
    results["workflow"] = {
        "tokens": int(wf["total_tokens"]),
        "latency_ms": round(wf_ms, 1),
        "correct": is_correct(wf["final_output"]),
        "output": wf["final_output"],
    }

    t0 = time.perf_counter()
    react = react_graph.invoke(
        {
            "messages": [
                SystemMessage(content=REACT_SYSTEM),
                HumanMessage(content=QUERY),
            ],
            "total_tokens": 0,
            "step_count": 0,
        }
    )
    react_ms = (time.perf_counter() - t0) * 1000
    react_out = react["messages"][-1].content
    results["react"] = {
        "tokens": int(react["total_tokens"]),
        "latency_ms": round(react_ms, 1),
        "steps": int(react["step_count"]),
        "correct": is_correct(react_out),
        "output": react_out,
    }

    t0 = time.perf_counter()
    ma = ma_graph.invoke(
        {
            "user_query": QUERY,
            "subgoals": [],
            "retrieved_provisions": [],
            "audited_provisions": [],
            "audit_passed": True,
            "retry_count": 0,
            "final_dossier": "",
            "total_tokens": 0,
        }
    )
    ma_ms = (time.perf_counter() - t0) * 1000
    results["multi_agent"] = {
        "tokens": int(ma["total_tokens"]),
        "latency_ms": round(ma_ms, 1),
        "correct": is_correct(ma["final_dossier"]),
        "output": ma["final_dossier"],
    }

    return results


def aggregate(runs: list[dict[str, dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("workflow", "react", "multi_agent"):
        tokens = [r[name]["tokens"] for r in runs]
        latencies = [r[name]["latency_ms"] for r in runs]
        correct = [1.0 if r[name]["correct"] else 0.0 for r in runs]
        token_stats = summarise(tokens)
        latency_stats = summarise(latencies)
        out[name] = {
            "token_mean": token_stats["mean"],
            "token_std": token_stats["std"],
            "token_min": int(token_stats["min"]),
            "token_max": int(token_stats["max"]),
            "lat_mean_ms": latency_stats["mean"],
            "lat_std_ms": latency_stats["std"],
            "acc": round(100.0 * statistics.mean(correct), 2),
        }
        if name == "react":
            out[name]["step_mean"] = round(
                statistics.mean([r[name]["steps"] for r in runs]), 4
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--raw-output", type=Path, default=RAW_PATH)
    args = parser.parse_args()

    wf_graph = bench.build_workflow_graph()
    react_graph = bench.build_react_graph()
    ma_graph = bench.build_multiagent_graph()

    print(f">>> Running {args.runs} iterations x 3 architectures on DeepSeek...")
    runs: list[dict[str, dict[str, Any]]] = []
    for i in range(1, args.runs + 1):
        started = time.perf_counter()
        result = run_once(wf_graph, react_graph, ma_graph)
        runs.append(result)
        elapsed = time.perf_counter() - started
        print(
            f"  run {i:02d}/{args.runs}: "
            f"wf={result['workflow']['tokens']} tok, "
            f"react={result['react']['tokens']} tok, "
            f"ma={result['multi_agent']['tokens']} tok "
            f"({elapsed:.1f}s)"
        )

    stats = aggregate(runs)
    payload = {
        **stats,
        "_metadata": {
            "method": "measured",
            "model": "deepseek-chat (alias -> DeepSeek Flash V4.1)",
            "temperature": 0.1,
            "query": QUERY,
            "runs": args.runs,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "script": "scripts/benchmark_10_runs.py",
            "token_source": "DeepSeek API usage_metadata.total_tokens",
            "workspace": str(WORKSPACE),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.raw_output.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== AGGREGATE (mean ± std) ===")
    for name in ("workflow", "react", "multi_agent"):
        row = payload[name]
        print(
            f"{name:12s}: {row['token_mean']:.1f} ± {row['token_std']:.1f} tokens | "
            f"{row['lat_mean_ms']:.0f} ± {row['lat_std_ms']:.0f} ms | "
            f"acc={row['acc']:.1f}%"
        )
    print(f"\nSaved: {args.output}")
    print(f"Raw:   {args.raw_output}")


if __name__ == "__main__":
    main()
