"""Chay THAT 3 kien truc tren cau hoi cua demo va xuat ket qua do duoc.

Khong viet tay so nao. Dung lai dung cac graph trong
`scripts/run_langgraph_deepseek.py` (workflow / react / multiagent).

    cd CO5151 && ../.venv/bin/python scripts/run_3_designs.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_langgraph_deepseek as bench  # noqa: E402

QUERY = (
    "Công ty cổ phần Thanh toán An Phát có vốn điều lệ thực góp 35 tỷ đồng, "
    "muốn xin cấp phép cung ứng dịch vụ ví điện tử. Công ty có đủ điều kiện "
    "về vốn theo quy định hiện hành không?"
)
OUT = ROOT / "data/benchmarks/three_designs_real.json"


def main() -> None:
    print(f"\nQUERY: {QUERY}\n")
    results: dict[str, dict] = {}

    # 1. Workflow tuyen tinh
    t0 = time.perf_counter()
    wf = bench.build_workflow_graph().invoke(
        {
            "query": QUERY,
            "category": "",
            "retrieved_context": "",
            "final_output": "",
            "total_tokens": 0,
        }
    )
    ms = (time.perf_counter() - t0) * 1000
    results["workflow"] = {
        "tokens": int(wf.get("total_tokens", 0)),
        "latency_ms": round(ms, 1),
        "output": wf.get("final_output", ""),
    }

    # 2. ReAct loop
    t0 = time.perf_counter()
    re_ = bench.build_react_graph().invoke(
        {"messages": [("user", QUERY)], "total_tokens": 0, "step_count": 0}
    )
    ms = (time.perf_counter() - t0) * 1000
    results["react"] = {
        "tokens": int(re_.get("total_tokens", 0)),
        "latency_ms": round(ms, 1),
        "steps": int(re_.get("step_count", 0)),
        "output": re_["messages"][-1].content,
    }

    # 3. Orchestrator-Workers
    t0 = time.perf_counter()
    ma = bench.build_multiagent_graph().invoke(
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
    ms = (time.perf_counter() - t0) * 1000
    results["multi_agent"] = {
        "tokens": int(ma.get("total_tokens", 0)),
        "latency_ms": round(ms, 1),
        "recovery_fired": int(ma.get("retry_count", 0)) > 0,
        "docs_kept": sorted({p.get("doc_id") for p in ma.get("audited_provisions", [])}),
        "output": ma.get("final_dossier", ""),
    }

    base = results["workflow"]["tokens"] or 1
    print(f"{'kien truc':<14}{'tokens':>9}{'x':>7}{'latency':>10}  ghi chu")
    print("-" * 70)
    for k, v in results.items():
        extra = f"steps={v['steps']}" if "steps" in v else ""
        if v.get("recovery_fired"):
            extra += " recovery=YES"
        print(f"{k:<14}{v['tokens']:>9}{v['tokens']/base:>6.1f}x{v['latency_ms']:>9.0f}ms  {extra}")

    for k, v in results.items():
        print(f"\n=== {k.upper()} — OUTPUT ===\n{v['output'][:500]}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nluu: {OUT}")


main()
