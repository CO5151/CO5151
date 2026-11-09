#!/usr/bin/env python3
"""Đo end-to-end trên bộ SBV mà KHÔNG cần LLM judge.

    python scripts/eval_correctness.py --limit 40

Bài báo SBV-LawGraph định nghĩa Answer Correctness = 3 điều kiện:
(i) semantic equivalence, (ii) citation presence, (iii) citation validity.
Điều kiện (i) bắt buộc phải có judge. Script này đo **hai điều kiện còn lại**
cộng thêm một proxy mạnh: câu trả lời có trích đúng điều khoản chuẩn không.

Vì sao proxy hợp lý: nếu câu trả lời viện dẫn đúng điều khoản trong ground truth
thì nội dung gần như chắc chắn dựa trên đúng căn cứ. Nó không chứng minh tương
đương ngữ nghĩa, nhưng đo được ở mọi lần chạy và so sánh được giữa các cấu hình.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.core.doc_ids import canonical_doc_id  # noqa: E402
from src.security.answer_gate import extract_citations  # noqa: E402

TESTSET = WORKSPACE / "data" / "benchmarks" / "sbv_testset_tvpl.json"


def gt_pairs(relevant: list[str]) -> set[tuple[str, str]]:
    """'21/2017/tt-nhnn_8' -> ('8', '21/2017/TT-NHNN')"""
    out = set()
    for item in relevant:
        m = re.match(r"(.+)_(\d+)$", item.lower().strip())
        if m:
            out.add((m.group(2), canonical_doc_id(m.group(1))))
    return out


def graph_inventory() -> tuple[set[tuple[str, str]], set[str]]:
    """(tập (số điều, doc_id) có thật, tập doc_id còn hiệu lực) — đọc 1 lần."""
    from src.knowledge.neo4j_client import Neo4jClient

    client = Neo4jClient()
    pairs: set[tuple[str, str]] = set()
    active: set[str] = set()
    try:
        with client.driver.session() as sess:
            for r in sess.run(
                "MATCH (d:Document)-[:CONTAINS]->(a:Article) "
                "RETURN d.doc_id AS doc, a.article_number AS num, coalesce(d.status,'unknown') AS st"
            ):
                doc = canonical_doc_id(r["doc"])
                pairs.add((str(r["num"]), doc))
                if str(r["st"]).lower() in ("active", "in_force", "in-force"):
                    active.add(doc)
    finally:
        client.close()
    return pairs, active


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    logging.disable(logging.WARNING)
    from src.agents.orchestrator import LegalOrchestrator

    qs = json.loads(TESTSET.read_text(encoding="utf-8"))
    sample = qs[a.start - 1: a.start - 1 + a.limit]
    orch = LegalOrchestrator()

    pairs, active_docs = graph_inventory()
    print(f"Graph: {len(pairs)} điều khoản, {len(active_docs)} văn bản còn hiệu lực")

    rows = []
    t0 = time.time()
    for i, q in enumerate(sample, 1):
        st = orch.run(q["question"], enable_live_vbpl=False)
        answer = st.final_compliance_dossier or ""
        cites = extract_citations(answer)
        gt = gt_pairs(q.get("relevant_articles", []))
        # Định nghĩa của paper: dẫn chiếu hợp lệ = điều khoản TỒN TẠI và văn bản
        # CÒN HIỆU LỰC (không phải "nằm trong tập đã truy xuất").
        valid = bool(cites) and all(c in pairs and c[1] in active_docs for c in cites)
        hit = bool(cites & gt)
        rows.append({
            "id": q["question_id"],
            "status": st.answer_status,
            "n_citations": len(cites),
            "has_citation": bool(cites),
            "citations_valid": valid,
            "gt_hit": hit,
            "retries": st.retry_count,
            "answer_chars": len(answer),
            "answer": answer[:1500],
        })
        print(f"[{i:3d}/{len(sample)}] {st.answer_status:22s} "
              f"cite={len(cites):2d} gt_hit={'Y' if hit else '.'} "
              f"valid={'Y' if valid else '.'} | {q['question'][:44]}")

    n = len(rows)
    answered = [r for r in rows if r["status"] != "insufficient_evidence"]
    m = max(len(answered), 1)

    def pct(f): return f"{100*sum(1 for r in rows if f(r))/n:.1f}%"
    def pct_ans(f): return f"{100*sum(1 for r in answered if f(r))/m:.1f}%"
    summary = {
        "n": n,
        "seconds": round(time.time() - t0, 1),
        "abstain_rate": pct(lambda r: r["status"] == "insufficient_evidence"),
        "citation_presence": pct(lambda r: r["has_citation"]),
        # Validity chỉ tính trên các câu CÓ trả lời; câu bị chặn đã nằm ở abstain_rate.
        "citation_validity_answered": pct_ans(lambda r: r["citations_valid"]),
        "gt_hit_rate": pct(lambda r: r["gt_hit"]),
        "status_counts": {s: sum(1 for r in rows if r["status"] == s)
                          for s in {r["status"] for r in rows}},
    }
    print("\n" + "=" * 74)
    for k, v in summary.items():
        print(f"  {k:20s}: {v}")
    print("=" * 74)

    out = Path(a.out) if a.out else WORKSPACE / "data" / "benchmarks" / "eval_correctness_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"  raw: {out}")
    return 0


def _allowed_of(state) -> set[tuple[str, str]]:
    from src.security.answer_gate import allowed_from_clauses
    return allowed_from_clauses(getattr(state, "active_clauses", []) or [])


if __name__ == "__main__":
    raise SystemExit(main())
