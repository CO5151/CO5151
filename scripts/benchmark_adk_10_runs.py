#!/usr/bin/env python3
"""Measure the Google ADK production pipeline (src/agents/orchestrator.py) N times.

This is the ADK counterpart of ``benchmark_10_runs.py`` (which measures the
LangGraph harness). Same query, same knowledge exports, different runtime:

    benchmark_10_runs.py      -> LangGraph graph builders (scripts/)
    benchmark_adk_10_runs.py  -> LegalOrchestrator + ADKRunner (src/agents/)

Requires the ``google-adk`` + ``litellm`` stack:

    .venv-adk/bin/python scripts/benchmark_adk_10_runs.py --runs 10

Token accounting: ADK goes through LiteLLM, so we hook a CustomLogger and sum
``response.usage.total_tokens`` -- the ADK state object itself has no counters.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE / "source" / ".env")
load_dotenv(WORKSPACE.parent / ".env")

import litellm  # noqa: E402
from litellm.integrations.custom_logger import CustomLogger  # noqa: E402

from src.agents.orchestrator import LegalOrchestrator  # noqa: E402

QUERY = (
    "Doanh nghiệp muốn xin cấp phép cung ứng dịch vụ Ví điện tử thì vốn điều lệ "
    "tối thiểu cần bao nhiêu tiền và căn cứ theo văn bản quy phạm pháp luật nào hiện hành?"
)
OUTPUT_PATH = WORKSPACE / "data/benchmarks/benchmark_adk_10_runs_stats.json"
RAW_PATH = WORKSPACE / "data/benchmarks/benchmark_adk_10_runs_raw.json"


class TokenCounter(CustomLogger):
    """Accumulates total_tokens across all LiteLLM calls in a run."""

    def __init__(self) -> None:
        self.total = 0
        self.calls = 0

    def _acc(self, response_obj: Any) -> None:
        usage = getattr(response_obj, "usage", None)
        if usage is None:
            return
        self.total += int(getattr(usage, "total_tokens", 0) or 0)
        self.calls += 1

    def log_success_event(self, kwargs, response_obj, start_time, end_time):  # noqa: D102
        self._acc(response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):  # noqa: D102
        self._acc(response_obj)


def is_correct(text: str) -> bool:
    compact = (text or "").replace(",", ".")
    cites_active = "52/2024" in compact
    states_capital = (
        "50.000.000.000" in compact or "50 tỷ" in compact or "50.000.000" in compact
    )
    return bool(cites_active and states_capital)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    counter = TokenCounter()
    litellm.callbacks = [counter]

    orch = LegalOrchestrator()
    rows: list[dict[str, Any]] = []

    # Warm up the dense retriever so run 1 does not absorb embedder load time.
    t_warm = time.perf_counter()
    orch.lawgraph_agent.dense_retrieve("khởi động bộ mã hoá", top_k=1)
    print(f">>> Embedder warm-up: {(time.perf_counter() - t_warm) * 1000:.0f} ms")

    print(f">>> Google ADK pipeline x {args.runs} runs (DeepSeek via LiteLLM)")
    for i in range(1, args.runs + 1):
        counter.total = 0
        counter.calls = 0
        t0 = time.perf_counter()
        state = orch.run(query=QUERY)
        elapsed = (time.perf_counter() - t0) * 1000
        dossier = getattr(state, "final_compliance_dossier", "") or ""
        rows.append(
            {
                "run": i,
                "tokens": counter.total,
                "llm_calls": counter.calls,
                "latency_ms": round(elapsed, 1),
                "correct": is_correct(dossier),
                "plan_steps": len(getattr(state, "plan_steps", []) or []),
                "retry_count": getattr(state, "retry_count", 0),
                "output": dossier,
            }
        )
        print(
            f"  run {i:02d}/{args.runs}: {counter.total} tok, {counter.calls} calls, "
            f"{elapsed:.0f} ms, correct={rows[-1]['correct']}"
        )

    tokens = [r["tokens"] for r in rows]
    lat = [r["latency_ms"] for r in rows]
    payload = {
        "tokens_mean": round(statistics.mean(tokens), 1),
        "tokens_std": round(statistics.stdev(tokens), 1) if len(tokens) > 1 else 0.0,
        "lat_mean_ms": round(statistics.mean(lat), 1),
        "lat_std_ms": round(statistics.stdev(lat), 1) if len(lat) > 1 else 0.0,
        "llm_calls_mean": round(statistics.mean([r["llm_calls"] for r in rows]), 2),
        "acc": round(100.0 * statistics.mean([1.0 if r["correct"] else 0.0 for r in rows]), 2),
        "_metadata": {
            "method": "measured",
            "runtime": "Google ADK (google-adk + LiteLLM)",
            "entrypoint": "src/agents/orchestrator.py::LegalOrchestrator.run",
            "model": "deepseek/deepseek-chat (alias -> DeepSeek Flash V4.1)",
            "query": QUERY,
            "runs": args.runs,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "script": "scripts/benchmark_adk_10_runs.py",
            "token_source": "LiteLLM usage.total_tokens (CustomLogger)",
        },
    }

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    RAW_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== ADK AGGREGATE ===")
    print(
        f"multi_agent_adk: {payload['tokens_mean']:.1f} ± {payload['tokens_std']:.1f} tokens | "
        f"{payload['lat_mean_ms']:.0f} ± {payload['lat_std_ms']:.0f} ms | "
        f"{payload['llm_calls_mean']} LLM calls | acc={payload['acc']:.1f}%"
    )
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
