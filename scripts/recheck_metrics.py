#!/usr/bin/env python3
"""Re-examine 'Days to Review' and the on-time rate across several definitions."""

from __future__ import annotations

import csv
import statistics as st
from datetime import date
from pathlib import Path

p = Path.home() / "Downloads/tung_danglam_sprint_tasks_report_clean.csv"
rows = list(csv.DictReader(p.open(encoding="utf-8")))


def num(v: str) -> float | None:
    v = (v or "").strip()
    return None if v in ("", "N/A") else float(v)


dtr_all = [num(r["Days to Review"]) for r in rows]
dtr = [v for v in dtr_all if v is not None]
cycle = [v for v in (num(r["Cycle Time (Days)"]) for r in rows) if v is not None]
revdur = [v for v in (num(r["Review Duration (Days)"]) for r in rows) if v is not None]

print("=" * 70)
print("A. DISTRIBUTION OF 'Days to Review' (Date Changed to Review - Created Date)")
print("=" * 70)
print(f"  n with value      : {len(dtr)} / {len(rows)}")
print(f"  mean              : {st.mean(dtr):.2f}")
print(f"  median            : {st.median(dtr):.1f}")
print(f"  min / max         : {min(dtr):.0f} / {max(dtr):.0f}")
print(f"  stdev             : {st.pstdev(dtr):.1f}")
q = st.quantiles(dtr, n=4)
print(f"  quartiles         : Q1={q[0]:.1f}  Q2={q[1]:.1f}  Q3={q[2]:.1f}")

print("\n  the 10 slowest (these pull the mean up):")
slow = sorted(((num(r["Days to Review"]), r["Key"]) for r in rows if num(r["Days to Review"])), reverse=True)
for v, k in slow[:10]:
    print(f"    {k:>10}  {v:5.0f} d")

print("\n  effect of removing the 4 repaired rows:")
repaired = {"TAL-781", "TAL-711", "TAL-705", "TAL-612"}
without = [num(r["Days to Review"]) for r in rows if r["Key"] not in repaired and num(r["Days to Review"])]
print(f"    with   : n={len(dtr):2d} mean={st.mean(dtr):5.2f}")
print(f"    without: n={len(without):2d} mean={st.mean(without):5.2f}   <- what the broken file effectively computed")

print("\n  trimmed mean (drop slowest 10%):")
k = max(1, len(dtr) // 10)
trimmed = sorted(dtr)[: len(dtr) - k]
print(f"    n={len(trimmed)} mean={st.mean(trimmed):.2f}")

print("\n" + "=" * 70)
print("B. OTHER LATENCY DEFINITIONS")
print("=" * 70)
print(f"  Cycle Time (Resolved - Created)        mean={st.mean(cycle):5.2f}  median={st.median(cycle):5.1f}  n={len(cycle)}")
print(f"  Review Duration (Resolved - Review)    mean={st.mean(revdur):5.2f}  median={st.median(revdur):5.1f}  n={len(revdur)}")

print("\n" + "=" * 70)
print("C. ON-TIME RATE")
print("=" * 70)
done = [r for r in rows if r["Status"] == "Done"]
active = [r for r in rows if r["Status"] != "Done"]


def rate(subset: list[dict[str, str]]) -> tuple[int, int, float]:
    single = sum(1 for r in subset if r["Sprint Count"] == "1")
    return single, len(subset), single / len(subset) * 100


for label, subset in (
    ("Done only", done),
    ("Active only", active),
    ("All rows", rows),
):
    s, n, pct = rate(subset)
    print(f"  {label:26s} single={s:2d}/{n:2d} = {pct:5.1f}%")

print("\n  counter-check: is 'single sprint' the same as the assessment text?")
mismatch = [
    r for r in rows
    if (r["Sprint Count"] == "1") != ("Completed within Sprint Plan" in r["Sprint Plan Assessment"] or "Active" in r["Sprint Plan Assessment"])
]
print(f"    mismatches: {len(mismatch)}")

print("\n  which tasks are NOT on time (rolled over)?")
for r in rows:
    if r["Sprint Count"] != "1":
        print(f"    {r['Key']:>10}  {r['Status']:<12} {r['Story Points']:>4} SP  {r['Sprint(s)']}")
