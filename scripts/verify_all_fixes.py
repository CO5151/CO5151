#!/usr/bin/env python3
"""End-to-end verification of every fix claimed so far."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

DL = Path.home() / "Downloads"
WS = Path("/Users/tungdl/Documents/CO5151")
PKG = WS / "CO5151"
ok = []
bad = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (ok if cond else bad).append(f"{name}{(' -> ' + detail) if detail else ''}")


# ---------------- CSV ----------------
clean = DL / "tung_danglam_sprint_tasks_report_clean.csv"
fixed = DL / "tung_danglam_sprint_tasks_report_with_review_and_calculations_FIXED.csv"
metrics = DL / "tung_danglam_sprint_tasks_report_metrics.csv"

rows = list(csv.DictReader(clean.open(encoding="utf-8")))
header = list(rows[0].keys())

check("clean.csv ton tai", clean.exists())
check("so cot = 14", len(header) == 14, str(len(header)))
check("bo cot Days to Review", all("Days to Review" not in h and "Days Created to Review" not in h for h in header))
check("con cot Review Duration", "Review Duration (Days)" in header)
check("bo PI6 khoi detail", not any("PI6" in r["Sprint(s)"] for r in rows))
check("52 dong", len(rows) == 52, str(len(rows)))
check("tat ca Done", Counter(r["Status"] for r in rows) == {"Done": 1} or set(r["Status"] for r in rows) == {"Done"})

# malformed rows re-quoted -> every row parses with the right field count
raw = clean.read_text(encoding="utf-8").splitlines()
widths = {len(next(csv.reader([ln]))) for ln in raw if ln.strip()}
check("khong con hang lech cot", widths == {14}, str(widths))

# formulas
check("khong con cong thuc", "=" not in "".join(
    c for ln in fixed.read_text(encoding="utf-8").splitlines() for c in ln.split(",")
))

# metrics arithmetic
m = list(csv.DictReader(metrics.open(encoding="utf-8")))
total = [r for r in m if r["Scope"].startswith("Completed Tasks (PI2")][0]
check("on-time = 47/52 = 90.4", total["On-Time Rate % (of Done)"] == "90.4", total["On-Time Rate % (of Done)"])
check("single + rolled = total", int(total["Single Sprint"]) + int(total["Rolled Over"]) == int(total["Total Tasks"]))
check("median review duration = 3.0", total["Median Review Duration (Days)"] == "3.0")
sp_detail = sum(float(r["Story Points"]) for r in rows)
check("tong SP khop", abs(sp_detail - float(total["Total Story Points"])) < 0.05,
      f"{sp_detail} vs {total['Total Story Points']}")

# per-PI sums reconcile
pi_rows = {r["Scope"]: r for r in m if r["Scope"].startswith("PI") and len(r["Scope"]) == 3}
check("tong task theo PI = 52", sum(int(r["Total Tasks"]) for r in pi_rows.values()) == 52,
      str({k: v["Total Tasks"] for k, v in pi_rows.items()}))

# ---------------- code ----------------
base = (PKG / "src/agents/base.py").read_text(encoding="utf-8")
check("base.py: tools khong con None", "tools=adk_callables if adk_callables else None" not in base)

lg = (PKG / "src/agents/lawgraph.py").read_text(encoding="utf-8")
check("lawgraph: co BENCH_RETRIEVER", "BENCH_RETRIEVER" in lg)
check("lawgraph: pass2 bi chan khi forced dense", 'forced != "dense"' in lg)

check("adk_pipeline.py ton tai", (PKG / "src/agents/adk_pipeline.py").exists())
pipe = (PKG / "src/agents/adk_pipeline.py").read_text(encoding="utf-8")
for sym in ("SequentialAgent", "LoopAgent", "LlmAgent", "DatabaseSessionService", "Runner"):
    check(f"adk_pipeline dung {sym}", sym in pipe)
check("adk_pipeline khong dung ADKRunner tu viet", "class ADKRunner" not in pipe)

bench = PKG / "data/benchmarks"
for f in ("benchmark_adkpipe_real_stats.json", "sbv_real_judge_summary.json",
          "benchmark_full_stats.json", "sbv_full_judge_summary.json"):
    check(f"co {f}", (bench / f).exists())

# ---------------- slides ----------------
tex = (WS / "slides_s1_7_vi.tex").read_text(encoding="utf-8")
check("33 frame", tex.count(r"\begin{frame}") == 33, str(tex.count(r"\begin{frame}")))
check("brace can bang", tex.count("{") == tex.count("}"))
check("khong con DeepSeek-V3", "DeepSeek-V3" not in tex)
check("khong con so ADK sai 9.542", "9.542" not in tex)
check("khong con judge ADK 36,0", "36,0" not in tex)
check("backup4 dung 2.394", "2.394" in tex)
check("slide26 dung chuoi 40,0", "46,0 / 44,0 / 41,0 / 40,0" in tex)

# ---------------- still open ----------------
metrics_py = (PKG / "src/evaluation/metrics.py").read_text(encoding="utf-8")
grounding_00_fixed = bool(
    re.search(r"if total_claims <= 0:\s*\n\s*return 0\.0", metrics_py)
)
check("grounding_rate(0,0) = 0.0", grounding_00_fixed,
      "van con return 1.0" if not grounding_00_fixed else "")

orch = (PKG / "src/agents/orchestrator.py").read_text(encoding="utf-8")
check("orchestrator khong ghi de retrieved_clauses",
      "state.retrieved_clauses = active_clauses" not in orch,
      "van con dong 241" if "state.retrieved_clauses = active_clauses" in orch else "")

states = (PKG / "src/memory/state_models.py").read_text(encoding="utf-8")
check("LegalAgentState co active_clauses", "active_clauses:" in states)

print("=" * 70)
print(f"PASS {len(ok)}")
print("=" * 70)
for line in ok:
    print("  [ok]  " + line)
if bad:
    print("\n" + "=" * 70)
    print(f"FAIL / STILL OPEN {len(bad)}")
    print("=" * 70)
    for line in bad:
        print("  [!!]  " + line)
