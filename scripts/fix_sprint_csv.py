#!/usr/bin/env python3
"""Repair the sprint-tasks CSV export.

Problems fixed
--------------
1. Four detail rows contain an unquoted comma inside ``Summary``
   ("As a PO, I want ..."), which shifts every following column by one.
2. Fifteen summary cells hold literal spreadsheet formulas (``=C3/B3*100``)
   that CSV cannot evaluate, so the rates show up as text.
3. Three logically different tables are stacked in one file behind ``#``
   comment rows, which no CSV reader can parse as a single table.

Outputs
-------
* ``..._clean.csv``    one valid RFC-4180 table (56 tasks x 15 columns)
* ``..._metrics.csv``  summary + per-PI metrics, formulas evaluated
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date
from pathlib import Path

SRC = Path.home() / "Downloads/tung_danglam_sprint_tasks_report_with_review_and_calculations.csv"
OUT_DIR = SRC.parent
CLEAN = OUT_DIR / "tung_danglam_sprint_tasks_report_clean.csv"
METRICS = OUT_DIR / "tung_danglam_sprint_tasks_report_metrics.csv"

DETAIL_COLS = [
    "Key", "Summary", "Issue Type", "Status", "Story Points", "Sprint Count",
    "Sprint(s)", "Sprint Plan Assessment", "Created Date",
    "Date Changed to Review", "Resolved Date",
    "Cycle Time (Days)", "Review Duration (Days)", "Jira URL",
]


def d(value: str) -> date | None:
    value = (value or "").strip()
    if not value or value.upper() == "N/A":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def num(value: str) -> float | None:
    value = (value or "").strip()
    if not value or value.upper() == "N/A":
        return None
    return float(value)


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "_preamble"
    for line in text.splitlines():
        if line.startswith("# "):
            current = line[2:].strip()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)
    return sections


def repair_detail(lines: list[str]) -> list[dict[str, str]]:
    """Re-quote rows whose Summary field swallowed extra commas."""
    reader = csv.reader(io.StringIO("\n".join(line for line in lines if line.strip())))
    header = next(reader)
    n_cols = len(header)
    fixed_rows: list[dict[str, str]] = []
    repaired = 0

    for raw in reader:
        if len(raw) == n_cols:
            fields = raw
        elif len(raw) > n_cols:
            # Merge the surplus cells back into Summary (index 1).
            extra = len(raw) - n_cols
            summary = ", ".join(raw[1 : 2 + extra])
            fields = [raw[0], summary] + raw[2 + extra :]
            repaired += 1
        else:
            continue
        fixed_rows.append(dict(zip(header, fields)))

    print(f"  repaired {repaired} rows with an unquoted comma in Summary")
    return fixed_rows


def pct(numerator: float, denominator: float) -> str:
    if not denominator:
        return "N/A"
    return f"{numerator / denominator * 100:.1f}"


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    sections = split_sections(text)
    detail_lines = sections["DETAILED TASK LIST WITH REVIEW DATES AND CALCULATIONS"]
    rows = repair_detail(detail_lines)

    # ---- normalise types and recompute derived columns ----
    for r in rows:
        r["Story Points"] = f"{float(r['Story Points']):.1f}"
        r["Sprint Count"] = str(int(float(r["Sprint Count"])))

        created = d(r["Created Date"])
        review = d(r["Date Changed to Review"])
        resolved = d(r["Resolved Date"])

        r.pop("Days to Review", None)
        r.pop("Days Created to Review", None)
        r["Cycle Time (Days)"] = str((resolved - created).days) if created and resolved else "N/A"
        r["Review Duration (Days)"] = str((resolved - review).days) if review and resolved else "N/A"

        single = r["Sprint Count"] == "1"
        r["Sprint Plan Assessment"] = (
            "Completed within Sprint Plan" if single and r["Status"] == "Done"
            else "Extended / Rolled Over" if not single
            else "Active Sprint (Single Sprint)"
        )
        # unify the two sprint-label dialects
        parts = [re.sub(r"^(PI\d+)_TAL[ _]+Sprint (\d+)$", r"\1 - Sprint \2", p.strip())
                 for p in r["Sprint(s)"].split(",")]
        r["Sprint(s)"] = ", ".join(p for p in parts if p)

    # PI6 is the increment currently in flight (4 tasks: 1 Done, 1 Review,
    # 1 In Progress, 1 To Do), so it is not delivery history yet. Drop it.
    def in_pi6(r: dict[str, str]) -> bool:
        labels = [s.strip() for s in r["Sprint(s)"].split(",") if s.strip()]
        return bool(labels) and all(s.startswith("PI6") for s in labels)

    before = len(rows)
    rows = [r for r in rows if not in_pi6(r)]
    print(f"  excluded {before - len(rows)} PI6 tasks (current increment, not finished)")

    rows.sort(key=lambda r: (r["Sprint(s)"], r["Key"]))

    with CLEAN.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DETAIL_COLS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {CLEAN} ({len(rows)} rows)")

    # ---- metrics, computed instead of pasted as formulas ----
    def block(label: str, subset: list[dict[str, str]]) -> dict[str, str]:
        """Aggregate a scope.

        ``On-Time Rate %`` is only meaningful for finished work, so it is
        computed over Done tasks in the scope; open tasks are reported
        separately instead of being counted as on time.
        """
        n = len(subset)
        finished = [r for r in subset if r["Status"] == "Done"]
        single_all = sum(1 for r in subset if r["Sprint Count"] == "1")
        single_done = sum(1 for r in finished if r["Sprint Count"] == "1")
        sp = sum(float(r["Story Points"]) for r in subset)
        rev = [float(r["Review Duration (Days)"]) for r in subset if r["Review Duration (Days)"] != "N/A"]
        cyc = [float(r["Cycle Time (Days)"]) for r in subset if r["Cycle Time (Days)"] != "N/A"]
        return {
            "Scope": label,
            "Total Tasks": str(n),
            "Done Tasks": str(len(finished)),
            "Single Sprint": str(single_all),
            "Rolled Over": str(n - single_all),
            "On-Time Rate % (of Done)": pct(single_done, len(finished)),
            "Total Story Points": f"{sp:.1f}",
            "Avg SP / Task": f"{sp / n:.2f}" if n else "N/A",
            "Avg Review Duration (Days)": f"{sum(rev) / len(rev):.1f}" if rev else "N/A",
            "Median Review Duration (Days)": f"{sorted(rev)[len(rev) // 2]:.1f}" if rev else "N/A",
            "Avg Cycle Time (Days)": f"{sum(cyc) / len(cyc):.1f}" if cyc else "N/A",
        }

    metrics_rows = [block("Completed Tasks (PI2-PI5)", rows)]
    recent = [r for r in rows if r["Sprint(s)"].startswith(("PI4", "PI5"))]
    metrics_rows.append(block("Completed Tasks (PI4-PI5)", recent))

    with METRICS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(metrics_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metrics_rows)
        for pi in ("PI2", "PI3", "PI4", "PI5"):
            subset = [r for r in rows if pi in r["Sprint(s)"]]
            if subset:
                writer.writerow(block(pi, subset))
        writer.writerow(block("TOTAL / AVERAGE", rows))
    print(f"  wrote {METRICS}")

    # ---- same three-section layout as the original, but valid ----
    fixed_path = OUT_DIR / "tung_danglam_sprint_tasks_report_with_review_and_calculations_FIXED.csv"
    buf = io.StringIO()
    buf.write("# EXECUTIVE SUMMARY & DELIVERY METRICS\n")
    w = csv.writer(buf, lineterminator="\n")
    first = metrics_rows[0].keys()
    w.writerow(list(first))
    for m in metrics_rows:
        w.writerow(list(m.values()))

    buf.write("\n# BREAKDOWN BY PROGRAM INCREMENT (PI)\n")
    w.writerow(list(first))
    for pi in ("PI5", "PI4", "PI3", "PI2"):
        subset = [r for r in rows if pi in r["Sprint(s)"]]
        if subset:
            b = block(pi, subset)
            w.writerow(list(b.values()))
    w.writerow(list(block("TOTAL / AVERAGE", rows).values()))

    buf.write("\n# DETAILED TASK LIST WITH REVIEW DATES AND CALCULATIONS\n")
    w = csv.DictWriter(buf, fieldnames=DETAIL_COLS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

    fixed_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"  wrote {fixed_path}")

    # ---- report ----
    print("\nSTATUS COUNTS:", dict(Counter(r["Status"] for r in rows)))
    print("SPRINT LABELS:", sorted({s.strip() for r in rows for s in r["Sprint(s)"].split(",")}))
    print("\nMETRICS PREVIEW:")
    for m in metrics_rows:
        print("  " + " | ".join(f"{k}={v}" for k, v in m.items()))


if __name__ == "__main__":
    main()
