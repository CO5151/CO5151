#!/usr/bin/env python3
"""Diagnose why one arm retrieves worse than another on the SBV set."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "data/benchmarks"


def strip_diacritics(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def norm_doc(doc: str) -> str:
    return re.sub(r"\s+", "", strip_diacritics(doc).upper())


testset = {int(r["question_id"]): r for r in json.loads((BENCH / "sbv_testset_tvpl.json").read_text(encoding="utf-8"))}
lg = json.loads((BENCH / "benchmark_full_raw.json").read_text(encoding="utf-8"))
adk = json.loads((BENCH / "benchmark_adk_full_raw.json").read_text(encoding="utf-8"))

print("=" * 78)
print("1. R@k / Hit@k distribution: how many questions does each arm MISS entirely?")
print("=" * 78)
for name, rows, key in (("workflow", lg, "workflow"), ("react", lg, "react"), ("multi_agent", lg, "multi_agent")):
    miss = [r["question_id"] for r in rows if r[key]["retrieval"]["hit_at_k"] == 0]
    print(f"  {name:12s} miss={len(miss):3d}  {miss}")
miss_adk = [r["question_id"] for r in adk if r["retrieval"]["hit_at_k"] == 0]
print(f"  {'adk':12s} miss={len(miss_adk):3d}  {miss_adk}")

print()
print("=" * 78)
print("2. For questions ADK misses but workflow hits, inspect the retrieval")
print("=" * 78)
wf_by = {int(r["question_id"]): r for r in lg}
adk_by = {int(r["question_id"]): r for r in adk}
only_adk_miss = [q for q in miss_adk if wf_by[q]["workflow"]["retrieval"]["hit_at_k"] == 1]
print(f"  ADK-only misses: {len(only_adk_miss)} -> {only_adk_miss}")

for q in only_adk_miss[:6]:
    t = testset[q]
    wf = wf_by[q]["workflow"]
    a = adk_by[q]
    print(f"\n--- Q{q}: {t['question'][:95]}")
    print(f"    GT docs      : {t['relevant_articles']}")
    print(f"    ADK k={a['retrieval']['k']} retrieved_docs={a['gt_docs']} (gt list)  P@k={a['retrieval']['p_at_k']}")
    print(f"    ADK plan_steps={a['plan_steps']} retrieved={a['retrieved']}")
    out = a["output"][:600].replace("\n", " ")
    print(f"    ADK out head : {out[:350]}")
    print(f"    WF  P@k={wf['retrieval']['p_at_k']} k={wf['retrieval']['k']} out: {wf['output'][:200]}")

print()
print("=" * 78)
print("3. ADK P@k vs k (does it over-retrieve?)\n" + "=" * 78)
import statistics as st
buckets: dict[int, list[float]] = {}
for r in adk:
    buckets.setdefault(r["retrieval"]["k"], []).append(r["retrieval"]["p_at_k"])
for k in sorted(buckets):
    print(f"  k={k}: n={len(buckets[k]):3d}  mean P@k={st.mean(buckets[k]) * 100:5.1f}%")
