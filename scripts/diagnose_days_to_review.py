#!/usr/bin/env python3
"""Diagnose why 'Days to Review' is ~11-18 instead of the expected 2-3 days."""

from __future__ import annotations

import csv
import statistics as st
from collections import Counter
from pathlib import Path

p = Path.home() / "Downloads/tung_danglam_sprint_tasks_report_clean.csv"
rows = list(csv.DictReader(p.open(encoding="utf-8")))


def num(v: str) -> float | None:
    v = (v or "").strip()
    return None if v in ("", "N/A") else float(v)


print("=" * 78)
print("1. THE THREE COLUMNS ARE A DECOMPOSITION, NOT THREE MEASURES")
print("=" * 78)
print("   Days to Review      = Date Changed to Review - Created Date")
print("   Review Duration     = Resolved Date - Date Changed to Review")
print("   Cycle Time          = Resolved Date - Created Date")
print("   => Days to Review + Review Duration == Cycle Time\n")

bad = 0
for r in rows:
    a, b, c = num(r["Days to Review"]), num(r["Review Duration (Days)"]), num(r["Cycle Time (Days)"])
    if None not in (a, b, c) and abs((a + b) - c) > 0.01:
        print(f"   MISMATCH {r['Key']}: {a} + {b} != {c}")
        bad += 1
print(f"   rows checked: {sum(1 for r in rows if None not in (num(r['Days to Review']), num(r['Review Duration (Days)']), num(r['Cycle Time (Days)'])))}"
      f", mismatches: {bad}")

print("\n" + "=" * 78)
print("2. DISTRIBUTION: 'Days to Review' is bimodal, not centred on 2-3")
print("=" * 78)
dtr = [num(r["Days to Review"]) for r in rows if num(r["Days to Review"]) is not None]
buckets = Counter()
for v in dtr:
    if v <= 3:
        buckets["0-3   (healthy)"] += 1
    elif v <= 7:
        buckets["4-7"] += 1
    elif v <= 14:
        buckets["8-14"] += 1
    elif v <= 30:
        buckets["15-30"] += 1
    else:
        buckets["31+   (backlog-aged)"] += 1
for label in ("0-3   (healthy)", "4-7", "8-14", "15-30", "31+   (backlog-aged)"):
    n = buckets[label]
    print(f"   {label:24s} {n:3d}  {'#' * n}")

print(f"\n   mean={st.mean(dtr):.2f}  median={st.median(dtr):.1f}  "
      f"share <=3d = {buckets['0-3   (healthy)']}/{len(dtr)} = {buckets['0-3   (healthy)'] / len(dtr) * 100:.0f}%")

print("\n" + "=" * 78)
print("3. THE 2-3 DAY FIGURE YOU EXPECT IS THE 'REVIEW DURATION' COLUMN")
print("=" * 78)
rd = [num(r["Review Duration (Days)"]) for r in rows if num(r["Review Duration (Days)"]) is not None]
print(f"   n={len(rd)}  mean={st.mean(rd):.2f}  median={st.median(rd):.1f}  "
      f"min={min(rd):.0f}  max={max(rd):.0f}")
print(f"   share <=3d: {sum(1 for v in rd if v <= 3)}/{len(rd)} = {sum(1 for v in rd if v <= 3) / len(rd) * 100:.0f}%")
print(f"   negative values (impossible): {sum(1 for v in rd if v < 0)}")

print("\n" + "=" * 78)
print("4. WHY 'Days to Review' IS LONG: Created Date is backlog age, not work start")
print("=" * 78)
print("   Tickets created long before the sprint they were actually worked in:\n")
slow = sorted(
    ((num(r["Days to Review"]), r) for r in rows if num(r["Days to Review"]) is not None),
    reverse=True, key=lambda x: x[0],
)
print(f"   {'Key':>10}  {'Created':<12}{'To Review':<12}{'Days':>5}  {'Resolved':<12}{'Sprint':<18}")
for v, r in slow[:12]:
    print(f"   {r['Key']:>10}  {r['Created Date']:<12}{r['Date Changed to Review']:<12}{v:>5.0f}  "
          f"{r['Resolved Date']:<12}{r['Sprint(s)']:<18}")

print("\n   same tickets, measured as review duration instead:")
for v, r in slow[:12]:
    print(f"   {r['Key']:>10}  review duration = {r['Review Duration (Days)']:>4} d")

print("\n" + "=" * 78)
print("5. VERDICT")
print("=" * 78)
print("   No parse/arithmetic error in the date columns.")
print("   The metric labelled 'Days to Review' measures Created -> Review,")
print("   i.e. backlog wait + implementation time. It cannot be 2-3 days")
print("   because Created Date is set when the ticket is filed, often months")
print("   before the sprint that actually worked on it.")
print("   The 2-3 day KPI you are looking for is 'Review Duration' (median 3).")
