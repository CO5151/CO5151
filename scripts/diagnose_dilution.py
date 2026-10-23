#!/usr/bin/env python3
"""Test whether concatenating planner subgoals + keywords dilutes the dense query."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

import re  # noqa: E402
import unicodedata  # noqa: E402

from src.agents.lawgraph import LawGraphAgent  # noqa: E402


def norm_doc(doc: str) -> str:
    d = doc.replace("đ", "d").replace("Đ", "D")
    d = "".join(c for c in unicodedata.normalize("NFD", d) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", d.upper())


testset = {int(r["question_id"]): r for r in json.loads(
    (WORKSPACE / "data/benchmarks/sbv_testset_tvpl.json").read_text(encoding="utf-8"))}

agent = LawGraphAgent()
agent.dense_retrieve("khởi động", top_k=1)  # warm up embedder

QUESTIONS = [6, 7, 9, 11, 14, 16, 20, 27, 30, 31, 55, 57, 58, 62, 65, 66, 70, 78, 86, 95]

print(f"{'Q':>4} {'GT doc':<18} {'query-only':^12} {'query+2 subgoals (paraphrase)':^32}")
print("-" * 80)
hit_q = 0
hit_p = 0
for qid in QUESTIONS:
    item = testset[qid]
    query = item["question"]
    gt = {norm_doc(a.split("_")[0]) for a in item["relevant_articles"]}

    # A. encode the raw question only (what the LangGraph harness does)
    a_docs = {norm_doc(h["doc_id"]) for h in agent.dense_retrieve(query, top_k=6)}

    # B. encode question + two paraphrased subgoals + keywords (what ADK does today)
    subgoals = [
        f"Xác định các quy định pháp luật liên quan trực tiếp đến nội dung: {query}",
        "Xác định thời điểm áp dụng và hiệu lực của văn bản quy định",
    ]
    keywords = ["ngân hàng", "thông tư", "nghị định"]
    diluted = " ".join([query] + subgoals + keywords)
    b_docs = {norm_doc(h["doc_id"]) for h in agent.dense_retrieve(diluted, top_k=6)}

    a = "HIT" if gt & a_docs else "miss"
    b = "HIT" if gt & b_docs else "miss"
    hit_q += a == "HIT"
    hit_p += b == "HIT"
    print(f"{qid:>4} {'/'.join(sorted(gt)):<18} {a:^12} {b:^32}")

print("-" * 80)
print(f"query-only           : {hit_q}/{len(QUESTIONS)}")
print(f"query + paraphrases  : {hit_p}/{len(QUESTIONS)}")
