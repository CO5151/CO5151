#!/usr/bin/env python3
"""Check per-PI membership and story points against the original summary."""

from __future__ import annotations

import csv
from pathlib import Path

p = Path.home() / "Downloads/tung_danglam_sprint_tasks_report_clean.csv"
rows = list(csv.DictReader(p.open(encoding="utf-8")))
print("total rows:", len(rows))
print()

for pi in ("PI2", "PI3", "PI4", "PI5", "PI6"):
    sub = [r for r in rows if pi in r["Sprint(s)"]]
    sp = sum(float(r["Story Points"]) for r in sub)
    print(f"{pi}: n={len(sub):2d} SP={sp:5.1f}")
    for r in sub:
        if r["Sprint(s)"].count("PI") > 1:
            print(f"    MULTI-PI: {r['Key']} SP={r['Story Points']} sprints={r['Sprint(s)']}")

print()
print("Sprint Count vs number of sprints listed:")
for r in rows:
    listed = len([s for s in r["Sprint(s)"].split(",") if s.strip()])
    if listed != int(r["Sprint Count"]):
        print(f"  {r['Key']}: count={r['Sprint Count']} listed={listed} -> {r['Sprint(s)']}")

print()
print("Rows with zero story points:")
for r in rows:
    if float(r["Story Points"]) == 0.0:
        print(f"  {r['Key']} {r['Status']} {r['Issue Type']} -> {r['Summary'][:70]}")

print()
print("Story point total:", sum(float(r["Story Points"]) for r in rows))
print("Done total       :", sum(float(r["Story Points"]) for r in rows if r["Status"] == "Done"))
