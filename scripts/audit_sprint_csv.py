#!/usr/bin/env python3
"""Audit the sprint-tasks CSV export: structure + arithmetic consistency."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date
from pathlib import Path

SRC = Path.home() / "Downloads/tung_danglam_sprint_tasks_report_with_review_and_calculations.csv"
text = SRC.read_text(encoding="utf-8")

# Split the file into its three merged tables.
sections: dict[str, list[str]] = {}
current = "_preamble"
for line in text.splitlines():
    if line.startswith("# "):
        current = line[2:].strip()
        sections[current] = []
    else:
        sections.setdefault(current, []).append(line)

print("SECTIONS FOUND")
for name, lines in sections.items():
    print(f"  {name!r}: {len(lines)} lines")

def parse(name: str) -> list[dict[str, str]]:
    body = "\n".join(sections[name]).strip()
    return list(csv.DictReader(io.StringIO(body)))

summary = parse("EXECUTIVE SUMMARY & DELIVERY METRICS")
pi = parse("BREAKDOWN BY PROGRAM INCREMENT (PI)")
detail = parse("DETAILED TASK LIST WITH REVIEW DATES AND CALCULATIONS")

print(f"\nrows: summary={len(summary)} pi={len(pi)} detail={len(detail)}")
print(f"detail columns: {list(detail[0].keys())}")

# ---------- 1. unevaluated formulas ----------
print("\n=== 1. UNEVALUATED SPREADSHEET FORMULAS ===")
bad = 0
for tbl_name, rows in (("summary", summary), ("pi", pi), ("detail", detail)):
    for i, row in enumerate(rows, 1):
        for k, v in row.items():
            if isinstance(v, str) and v.startswith("="):
                print(f"  {tbl_name}[{i}] {k} = {v}")
                bad += 1
print(f"  total: {bad}")

# ---------- 2. recompute the summary from the detail rows ----------
print("\n=== 2. SUMMARY RECOMPUTED FROM DETAIL ROWS ===")
def d(s: str) -> date | None:
    s = (s or "").strip()
    if not s or s.upper() == "N/A":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None

done = [r for r in detail if r["Status"].strip() == "Done"]
active = [r for r in detail if r["Status"].strip() != "Done"]
all_tasks = detail

def stats(rows: list[dict[str, str]], label: str) -> None:
    n = len(rows)
    single = sum(1 for r in rows if int(float(r["Sprint Count"] or 0)) == 1)
    multi = n - single
    sp = sum(float(r["Story Points"] or 0) for r in rows)
    dtr = [float(r["Days to Review"]) for r in rows if (r["Days to Review"] or "").strip() not in ("", "N/A")]
    cyc = [float(r["Cycle Time (Days)"]) for r in rows if (r["Cycle Time (Days)"] or "").strip() not in ("", "N/A")]
    print(f"  {label:46s} n={n:3d} single={single:3d} rolled={multi:3d} "
          f"SP={sp:6.1f} SP/task={sp/n if n else 0:4.2f} "
          f"avgDayToReview={sum(dtr)/len(dtr) if dtr else 0:5.1f} "
          f"avgCycle={sum(cyc)/len(cyc) if cyc else 0:5.1f}")

stats(done, "Completed (all-time)")
p6 = [r for r in detail if "PI6" in r["Sprint(s)"]]
stats(p6, "Touched PI6")
stats(detail, "All rows in detail")

print("\n  stated vs recomputed:")
stated = {
    "Completed Tasks (All-Time)": (53, 48, 117.0, 17.8, 21.3),
    "All Sprint Tasks Combined": (56, 50, 124.5, 17.7, 21.3),
}
for row in summary:
    key = row["Scope"]
    print(f"    {key:46s} stated total={row['Total Tasks']:>5} single={row['Completed within Sprint Plan (Single Sprint)']:>5} SP={row['Total Story Points']:>7}")

# ---------- 3. per-row arithmetic ----------
print("\n=== 3. PER-ROW DATE ARITHMETIC ===")
errs = 0
for r in detail:
    created, review, resolved = d(r["Created Date"]), d(r["Date Changed to Review"]), d(r["Resolved Date"])
    dtr, cyc, dur = r["Days to Review"].strip(), r["Cycle Time (Days)"].strip(), r["Review Duration (Days)"].strip()
    if created and review and dtr not in ("N/A", ""):
        expect = (review - created).days
        if abs(expect - float(dtr)) > 0.01:
            print(f"  {r['Key']}: Days to Review={dtr} but dates give {expect}")
            errs += 1
    if created and resolved and cyc not in ("N/A", ""):
        expect = (resolved - created).days
        if abs(expect - float(cyc)) > 0.01:
            print(f"  {r['Key']}: Cycle Time={cyc} but dates give {expect}")
            errs += 1
    if review and resolved and dur not in ("N/A", ""):
        expect = (resolved - review).days
        if abs(expect - float(dur)) > 0.01:
            print(f"  {r['Key']}: Review Duration={dur} but dates give {expect}")
            errs += 1
    if review and created and review < created:
        print(f"  {r['Key']}: review date {review} before created {created}")
        errs += 1
print(f"  arithmetic errors: {errs}")

# ---------- 4. Done but no resolved date ----------
print("\n=== 4. STATUS vs DATE CONSISTENCY ===")
for r in detail:
    if r["Status"].strip() == "Done" and not d(r["Resolved Date"]):
        print(f"  {r['Key']}: Done but Resolved Date = {r['Resolved Date']!r}")
    if r["Status"].strip() != "Done" and d(r["Resolved Date"]):
        print(f"  {r['Key']}: {r['Status']} but Resolved Date = {r['Resolved Date']}")

# ---------- 5. sprint count vs assessment ----------
print("\n=== 5. SPRINT COUNT vs ASSESSMENT TEXT ===")
for r in detail:
    sc = r["Sprint Count"].strip()
    a = r["Sprint Plan Assessment"].strip()
    if sc == "1" and "Extended" in a:
        print(f"  {r['Key']}: Sprint Count=1 but assessment={a!r}")
    if sc not in ("1", "") and "Completed" in a and "within" in a:
        print(f"  {r['Key']}: Sprint Count={sc} but assessment={a!r}")
    listed = len([s for s in r["Sprint(s)"].split(",") if s.strip()])
    if sc not in ("",) and listed != int(float(sc)):
        print(f"  {r['Key']}: Sprint Count={sc} but Sprint(s) lists {listed}: {r['Sprint(s)']!r}")

# ---------- 6. sprint naming inconsistency ----------
print("\n=== 6. SPRINT LABEL FORMATS ===")
c = Counter()
for r in detail:
    for s in r["Sprint(s)"].split(","):
        s = s.strip()
        if not s:
            continue
        if re.match(r"^PI\d+ - Sprint \d+$", s):
            c["'PI6 - Sprint 2' (dash)"] += 1
        elif re.match(r"^PI\d+_TAL[ _]Sprint \d+$", s):
            c["'PI5_TAL Sprint 5' (underscore TAL)"] += 1
        else:
            c[f"other: {s!r}"] += 1
for k, v in c.most_common():
    print(f"  {v:3d}  {k}")
