#!/usr/bin/env python3
"""Grade the generated answers of every benchmark arm with an LLM judge.

Ground truth already exists in ``data/benchmarks/sbv_testset_tvpl.json``:
  * ``reference_answer``    -> what a correct answer must contain
  * ``relevant_articles``   -> which document + article is the legal basis

The judge does NOT invent answers. It only compares a candidate answer against
the existing reference and emits a structured verdict.

Usage
-----
    .venv/bin/python scripts/judge_sbv.py --tag full
    .venv/bin/python scripts/judge_sbv.py --tag full --limit 20 --spot-check

Outputs
-------
    data/benchmarks/sbv_{tag}_judge.json           per-item verdicts
    data/benchmarks/sbv_{tag}_judge_summary.json   aggregated per arm
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
BENCH = WORKSPACE / "data/benchmarks"
TESTSET = BENCH / "sbv_testset_tvpl.json"

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WORKSPACE / ".env")
load_dotenv(WORKSPACE.parent / ".env")

import urllib.request  # noqa: E402

API_URL = "https://api.deepseek.com/chat/completions"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "deepseek-flash")

ARMS = {
    "workflow": (["benchmark_{tag}_raw.json"], "workflow", "output"),
    "react": (["benchmark_{tag}_raw.json"], "react", "output"),
    "multi_agent": (["benchmark_{tag}_raw.json"], "multi_agent", "output"),
    "adk": (["benchmark_adkpipe_{tag}_raw.json", "benchmark_adk_{tag}_raw.json"], None, "output"),
}

JUDGE_PROMPT = """Bạn là giám khảo chấm câu trả lời pháp lý Việt Nam.

CÂU HỎI:
{question}

ĐÁP ÁN CHUẨN (do chuyên gia biên soạn, dùng làm mốc duy nhất):
{reference}

CĂN CỨ ĐÚNG (số hiệu văn bản_Điều):
{articles}

CÂU TRẢ LỜI CẦN CHẤM:
{candidate}

Hãy chấm theo 4 tiêu chí. CHỈ dùng ĐÁP ÁN CHUẨN làm mốc, không tự suy luận thêm luật
và không phạt câu trả lời vì thiếu chi tiết không có trong đáp án chuẩn.

1. "correct": mức độ đúng so với ĐÁP ÁN CHUẨN
   - "correct": nêu đủ ý chính của đáp án chuẩn, không có thông tin sai
   - "partial": nêu được một phần ý chính, hoặc thiếu ý quan trọng
   - "incorrect": sai bản chất, lạc đề, hoặc không trả lời được

2. "faithful": CHỈ đánh giá câu trả lời có MÂU THUẪN hoặc BỊA hay không.
   - true  = không có khẳng định nào trái với ĐÁP ÁN CHUẨN hoặc CĂN CỨ ĐÚNG, và không
             tự tạo ra số hiệu văn bản / số Điều / con số không có thật.
   - false = có ít nhất một khẳng định trái với ĐÁP ÁN CHUẨN, hoặc tự nghĩ ra một văn
             bản/điều khoản không tồn tại.
   QUAN TRỌNG: trích thêm điều khoản khác ngoài CĂN CỨ ĐÚNG **không** bị coi là
   unfaithful. Chỉ ghi nhận vào khóa "extra_cites". Chỉ đặt false khi nội dung đó
   thực sự sai hoặc bịa.

3. "cites_expected": true nếu câu trả lời có nêu đúng số hiệu văn bản VÀ số Điều trong
   CĂN CỨ ĐÚNG.
4. "extra_cites": true nếu câu trả lời trích thêm văn bản/điều khoản nằm ngoài CĂN CỨ
   ĐÚNG (không phạt, chỉ ghi nhận).
5. "conciseness": số nguyên 1-5 (5 = rất gọn, đi thẳng vào câu trả lời; 1 = dài dòng,
   lặp câu hỏi, nhiều dẫn nhập/miễn trừ thừa).

Trả về DUY NHẤT một dòng JSON, không thêm chữ nào khác:
{{"correct":"correct|partial|incorrect","faithful":true,"cites_expected":true,"extra_cites":false,"conciseness":4,"missing":["ý thiếu"],"wrong":["ý sai"],"reason":"tối đa 30 từ"}}
"""


def strip_diacritics(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def extract_json(raw: str) -> dict[str, Any] | None:
    """Find any balanced JSON object containing a 'correct' key."""
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in reversed(starts):
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                    except Exception:  # noqa: BLE001
                        break
                    if isinstance(obj, dict) and "correct" in obj:
                        return obj
                    break
    return None


SIMPLE_PROMPT = """CÂU HỎI: {question}
ĐÁP ÁN CHUẨN: {reference}
CĂN CỨ: {articles}
CÂU TRẢ LỜI: {candidate}

Chấm và trả JSON một dòng, đúng 5 khóa:
{{"correct":"correct|partial|incorrect","faithful":true|false,"cites_expected":true|false,"extra_cites":true|false,"conciseness":1-5}}
"""


def normalize(verdict: dict[str, Any]) -> dict[str, Any]:
    c = str(verdict.get("correct", "")).strip().lower()
    if c not in ("correct", "partial", "incorrect"):
        c = "partial" if c.startswith("part") else ("correct" if c in ("true", "yes") else "incorrect")
    verdict["correct"] = c
    for key in ("faithful", "cites_expected", "extra_cites"):
        val = verdict.get(key)
        if isinstance(val, str):
            verdict[key] = val.strip().lower() in ("true", "yes", "1")
    conc = verdict.get("conciseness")
    try:
        verdict["conciseness"] = max(1, min(5, int(conc)))
    except (TypeError, ValueError):
        verdict["conciseness"] = None
    return verdict


def call_judge(question: str, reference: str, articles: str, candidate: str) -> dict[str, Any]:
    key = os.getenv("DEEPSEEK_API_KEY")
    bodies = []
    for prompt in (
        JUDGE_PROMPT,
        JUDGE_PROMPT,
        SIMPLE_PROMPT,
        SIMPLE_PROMPT,
        SIMPLE_PROMPT,
    ):
        bodies.append(
            json.dumps(
                {
                    "model": JUDGE_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Bạn là máy chấm điểm. Chỉ trả về một dòng JSON hợp lệ, "
                            "không giải thích, không markdown, không code fence.",
                        },
                        {
                            "role": "user",
                            "content": prompt.format(
                                question=question,
                                reference=reference,
                                articles=articles,
                                candidate=candidate[:6000],
                            ),
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 1200,
                    "response_format": {"type": "json_object"},
                }
            ).encode()
        )

    last_err = ""
    for attempt, body in enumerate(bodies):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
            msg = payload["choices"][0]["message"]
            raw = msg.get("content") or msg.get("reasoning_content") or ""
            verdict = extract_json(raw)
            if verdict is None:
                last_err = f"unparseable content (len={len(raw)})"
                time.sleep(1 + attempt)
                continue
            verdict = normalize(verdict)
            verdict["served_model"] = payload.get("model", JUDGE_MODEL)
            return verdict
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return {"correct": "error", "faithful": None, "cites_expected": None,
            "conciseness": None, "error": last_err}


def load_arm(tag: str, arm: str) -> dict[int, str]:
    patterns, key, field = ARMS[arm]
    path = None
    for pattern in patterns:
        candidate = BENCH / pattern.format(tag=tag)
        if candidate.exists():
            path = candidate
            break
    if path is None:
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for row in rows:
        block = row if key is None else row.get(key, {})
        out[int(row["question_id"])] = str(block.get(field, "") or "")
    return out


def collect_tasks(tag: str, limit: int | None) -> tuple[list[dict[str, Any]], dict[str, dict[int, str]]]:
    testset = {int(r["question_id"]): r for r in json.loads(TESTSET.read_text(encoding="utf-8"))}
    answers = {arm: load_arm(tag, arm) for arm in ARMS}
    qids = sorted(set().union(*[set(a) for a in answers.values()]))
    if limit:
        qids = qids[:limit]

    tasks: list[dict[str, Any]] = []
    for arm, per_q in answers.items():
        for qid in qids:
            candidate = per_q.get(qid, "")
            if not candidate:
                continue
            item = testset[qid]
            tasks.append(
                {
                    "question_id": qid,
                    "arm": arm,
                    "question": item["question"],
                    "reference": item.get("reference_answer", ""),
                    "articles": ", ".join(item.get("relevant_articles", [])),
                    "candidate": candidate,
                }
            )
    random.Random(42).shuffle(tasks)
    return tasks, answers


def words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARMS:
        rows = [r for r in records if r["arm"] == arm]
        ok = [r for r in rows if r["verdict"].get("correct") in ("correct", "partial", "incorrect")]
        if not ok:
            continue
        correct = sum(1 for r in ok if r["verdict"]["correct"] == "correct")
        partial = sum(1 for r in ok if r["verdict"]["correct"] == "partial")
        faithful = sum(1 for r in ok if r["verdict"].get("faithful") is True)
        cites = sum(1 for r in ok if r["verdict"].get("cites_expected") is True)
        extra = sum(1 for r in ok if r["verdict"].get("extra_cites") is True)
        conc = [r["verdict"]["conciseness"] for r in ok if isinstance(r["verdict"].get("conciseness"), int)]
        strict = sum(
            1
            for r in ok
            if r["verdict"]["correct"] == "correct"
            and r["verdict"].get("faithful") is True
            and r["verdict"].get("cites_expected") is True
        )
        lens = [words(r["candidate"]) for r in ok]
        out[arm] = {
            "n": len(ok),
            "correct_rate": round(100.0 * correct / len(ok), 2),
            "partial_rate": round(100.0 * partial / len(ok), 2),
            "incorrect_rate": round(100.0 * (len(ok) - correct - partial) / len(ok), 2),
            "faithful_rate": round(100.0 * faithful / len(ok), 2),
            "cites_rate": round(100.0 * cites / len(ok), 2),
            "extra_cites_rate": round(100.0 * extra / len(ok), 2),
            "strict_pass_rate": round(100.0 * strict / len(ok), 2),
            "conciseness_mean": round(statistics.mean(conc), 2) if conc else None,
            "answer_words_mean": round(statistics.mean(lens), 1) if lens else None,
            "answer_words_median": round(statistics.median(lens), 1) if lens else None,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="full")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--spot-check", action="store_true",
                        help="print 20 random candidate/reference pairs for manual review")
    parser.add_argument("--resume", action="store_true",
                        help="only judge items missing from the existing output file")
    parser.add_argument("--arms", default="",
                        help="comma-separated subset of arms, e.g. 'adk'")
    args = parser.parse_args()

    tasks, _ = collect_tasks(args.tag, args.limit or None)
    if args.arms:
        keep = {a.strip() for a in args.arms.split(",") if a.strip()}
        tasks = [t for t in tasks if t["arm"] in keep]
    if not tasks:
        print(f"[ERROR] no candidates found for tag={args.tag}", file=sys.stderr)
        sys.exit(1)

    out_path = BENCH / f"sbv_{args.tag}_judge.json"
    done: dict[tuple[int, str], dict[str, Any]] = {}
    if args.resume and out_path.exists():
        for rec in json.loads(out_path.read_text(encoding="utf-8")):
            if rec["verdict"].get("correct") != "error":
                done[(int(rec["question_id"]), rec["arm"])] = rec
        tasks = [t for t in tasks if (int(t["question_id"]), t["arm"]) not in done]
        print(f">>> Resuming: {len(done)} already judged, {len(tasks)} remaining")

    print(f">>> Judging {len(tasks)} answers with {JUDGE_MODEL} ({args.workers} workers)")

    def work(task: dict[str, Any]) -> dict[str, Any]:
        verdict = call_judge(task["question"], task["reference"], task["articles"], task["candidate"])
        return {**task, "verdict": verdict}

    t0 = time.perf_counter()
    records: list[dict[str, Any]] = list(done.values())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, rec in enumerate(pool.map(work, tasks), 1):
            records.append(rec)
            if i % 25 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} judged ({time.perf_counter()-t0:.0f}s)")

    summary = summarize(records)
    errors = sum(1 for r in records if r["verdict"].get("correct") == "error")

    out_path = BENCH / f"sbv_{args.tag}_judge.json"
    out_path = BENCH / f"sbv_{args.tag}_judge.json"
    sum_path = BENCH / f"sbv_{args.tag}_judge_summary.json"
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    sum_path.write_text(
        json.dumps(
            {
                **summary,
                "_metadata": {
                    "judge_model": JUDGE_MODEL,
                    "served_models": sorted({r["verdict"].get("served_model", "") for r in records} - {""}),
                    "tag": args.tag,
                    "n_verdicts": len(records),
                    "n_errors": errors,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "rubric": "correct(3) / faithful(contradiction-or-fabrication only) / cites_expected / extra_cites / conciseness(1-5) / strict_pass",
                    "ground_truth": "reference_answer + relevant_articles (existing, not generated)",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== JUDGE SUMMARY ===")
    for arm, s in summary.items():
        print(
            f"{arm:12s}: n={s['n']:>3} correct={s['correct_rate']:5.1f}% "
            f"partial={s['partial_rate']:5.1f}% faithful={s['faithful_rate']:5.1f}% "
            f"cites={s['cites_rate']:5.1f}% strict={s['strict_pass_rate']:5.1f}% "
            f"conc={s['conciseness_mean']} words={s['answer_words_median']}"
        )
    if errors:
        print(f"\n[WARN] {errors} verdicts failed -> re-run to fill them in.")
    print(f"\nSaved: {out_path}\nSummary: {sum_path}")

    if args.spot_check:
        print("\n=== SPOT CHECK (20) ===")
        sample = random.Random(7).sample(records, min(20, len(records)))
        for r in sample:
            print(f"\n--- Q{r['question_id']} [{r['arm']}] verdict={r['verdict'].get('correct')} ---")
            print(f"REF : {r['reference'][:220]}")
            print(f"GEN : {r['candidate'][:220]}")
            print(f"WHY : {r['verdict'].get('reason', '')}")


if __name__ == "__main__":
    main()
