#!/usr/bin/env python3
"""Final 4-arm table: all arms pinned to the same dense retriever."""

from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "data/benchmarks"

lg = json.loads((BENCH / "benchmark_full_stats.json").read_text(encoding="utf-8"))
adk = json.loads((BENCH / "benchmark_adk_densefix_stats.json").read_text(encoding="utf-8"))
js = json.loads((BENCH / "sbv_full_judge_summary.json").read_text(encoding="utf-8"))
js_adk = json.loads((BENCH / "sbv_densefix_judge_summary.json").read_text(encoding="utf-8"))

ARMS = {
    "workflow": (lg["workflow"], js["workflow"]),
    "react": (lg["react"], js["react"]),
    "multi_agent": (lg["multi_agent"], js["multi_agent"]),
    "adk": (adk, js_adk["adk"]),
}

rows = []
for arm, (det, judge) in ARMS.items():
    tok = det["token_mean"]
    correct = judge["correct_rate"]
    rows.append(
        {
            "arm": arm,
            "tokens": round(tok),
            "latency_ms": round(det["lat_mean_ms"]),
            "k_mean": det["k_mean"],
            "p_at_k": det["p_at_k"],
            "r_at_k": det["r_at_k"],
            "hit_at_k": det["hit_at_k"],
            "article_hit": det["article_hit"],
            "correct_rate": correct,
            "partial_rate": judge["partial_rate"],
            "answerable_rate": round(correct + judge["partial_rate"], 2),
            "faithful_rate": judge["faithful_rate"],
            "cites_rate": judge["cites_rate"],
            "strict_pass_rate": judge["strict_pass_rate"],
            "conciseness": judge["conciseness_mean"],
            "answer_words_median": judge["answer_words_median"],
            "tokens_per_correct": round(tok / (correct / 100)) if correct else None,
        }
    )

out = BENCH / "sbv_final_combined.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

print(
    f"{'arm':13s}{'tok':>7s}{'ms':>7s}{'k':>5s}{'R@k':>7s}{'art':>7s}"
    f"{'corr':>7s}{'part':>7s}{'faith':>7s}{'cite':>7s}{'strict':>7s}{'conc':>6s}"
    f"{'words':>7s}{'tok/corr':>10s}"
)
for r in rows:
    print(
        f"{r['arm']:13s}{r['tokens']:>7d}{r['latency_ms']:>7d}{r['k_mean']:>5.1f}"
        f"{r['r_at_k']:>7.1f}{r['article_hit']:>7.1f}{r['correct_rate']:>7.1f}"
        f"{r['partial_rate']:>7.1f}{r['faithful_rate']:>7.1f}{r['cites_rate']:>7.1f}"
        f"{r['strict_pass_rate']:>7.1f}{r['conciseness']:>6.2f}{r['answer_words_median']:>7.0f}"
        f"{r['tokens_per_correct']:>10d}"
    )
print(f"\nSaved: {out}")
