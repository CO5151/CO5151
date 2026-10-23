#!/usr/bin/env python3
"""Merge the 4-arm benchmark stats with the LLM-judge verdicts into one table."""

from __future__ import annotations

import json
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "data/benchmarks"

lg = json.loads((BENCH / "benchmark_full_stats.json").read_text(encoding="utf-8"))
adk = json.loads((BENCH / "benchmark_adk_full_stats.json").read_text(encoding="utf-8"))
js = json.loads((BENCH / "sbv_full_judge_summary.json").read_text(encoding="utf-8"))

ARMS = {
    "workflow": lg["workflow"],
    "react": lg["react"],
    "multi_agent": lg["multi_agent"],
    "adk": adk,
}

rows = []
for arm, det in ARMS.items():
    judge = js[arm]
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
            "extra_cites_rate": judge["extra_cites_rate"],
            "strict_pass_rate": judge["strict_pass_rate"],
            "conciseness": judge["conciseness_mean"],
            "answer_words_median": judge["answer_words_median"],
            "tokens_per_correct": round(tok / (correct / 100)) if correct else None,
            "correct_per_1k_tokens": round(correct / (tok / 1000), 1) if tok else None,
        }
    )

out = BENCH / "sbv_full_combined.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

header = (
    f"{'arm':13s}{'tok':>7s}{'ms':>7s}{'k':>5s}{'P@k':>7s}{'R@k':>7s}"
    f"{'art':>7s}{'corr':>7s}{'part':>7s}{'ans':>7s}{'faith':>7s}{'cite':>7s}"
    f"{'strict':>7s}{'conc':>6s}{'tok/corr':>10s}{'corr/1k':>9s}"
)
print(header)
for r in rows:
    print(
        f"{r['arm']:13s}{r['tokens']:>7d}{r['latency_ms']:>7d}{r['k_mean']:>5.1f}"
        f"{r['p_at_k']:>7.1f}{r['r_at_k']:>7.1f}{r['article_hit']:>7.1f}"
        f"{r['correct_rate']:>7.1f}{r['partial_rate']:>7.1f}{r['answerable_rate']:>7.1f}"
        f"{r['faithful_rate']:>7.1f}{r['cites_rate']:>7.1f}{r['strict_pass_rate']:>7.1f}"
        f"{r['conciseness']:>6.2f}{r['tokens_per_correct']:>10d}{r['correct_per_1k_tokens']:>9.1f}"
    )
print(f"\nSaved: {out}")
