#!/usr/bin/env python3
"""Nạp văn bản pháp luật mới vào LawGraph — có kiểm định, có chống trùng.

    python scripts/watch_and_ingest.py                 # chỉ báo cáo (mặc định)
    python scripts/watch_and_ingest.py --apply         # nạp thật vào graph
    python scripts/watch_and_ingest.py --inbox data/inbox --apply

Quy trình (khớp docs/PLAN_AUTO_INGEST.md, tầng 1→6):

  1. WATCH    — quét thư mục inbox, tính hash nội dung
  2. FETCH    — bỏ qua file không đổi (so hash trong state file)
  3. NORMALIZE— chuẩn hoá doc_id bằng canonical_doc_id
  4. EXTRACT  — dùng LegalIngestionPipeline có sẵn
  5. VALIDATE — cổng validate_document; không qua thì chuyển sang rejected/
  6. PUBLISH  — ingest_file(sync_neo4j=True) rồi chạy lại repair trùng

Mặc định chỉ báo cáo. `--apply` mới ghi vào graph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.core.doc_ids import canonical_doc_id  # noqa: E402
from src.knowledge.ingestion import LegalIngestionPipeline, parse_legal_document  # noqa: E402
from src.knowledge.neo4j_client import Neo4jClient  # noqa: E402
from src.knowledge.validate import validate_document  # noqa: E402

STATE_FILE = WORKSPACE / "data" / "ingest_state.json"
DEFAULT_INBOX = WORKSPACE / "data" / "inbox"
REJECTED = WORKSPACE / "data" / "rejected"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def known_docs(client: Neo4jClient) -> set[str]:
    try:
        with client.driver.session() as sess:
            return {canonical_doc_id(r["doc"]) for r in sess.run(
                "MATCH (d:Document) RETURN d.doc_id AS doc")}
    except Exception:  # noqa: BLE001
        return set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default=str(DEFAULT_INBOX))
    ap.add_argument("--apply", action="store_true", help="ghi thật vào graph")
    a = ap.parse_args()

    inbox = Path(a.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in inbox.iterdir() if p.suffix.lower() in (".txt", ".html", ".htm"))
    if not files:
        print(f"Inbox rỗng: {inbox}")
        print("Bỏ file văn bản vào đó rồi chạy lại. (--apply để nạp thật)")
        return 0

    state = load_state()
    client = Neo4jClient()
    existing = known_docs(client)
    pipeline = LegalIngestionPipeline(neo4j_client=client) if a.apply else None

    print(f"Inbox: {inbox}  |  {len(files)} file  |  graph hiện có {len(existing)} văn bản")
    print(f"Chế độ: {'APPLY (ghi thật)' if a.apply else 'DRY-RUN (chỉ báo cáo)'}")
    print("=" * 74)

    stats = {"new": 0, "unchanged": 0, "rejected": 0, "ok": 0, "duplicate": 0}
    for f in files:
        digest = sha256(f)
        doc_id = canonical_doc_id(parse_legal_document(f.read_text(encoding="utf-8", errors="ignore")).doc_id)
        key = str(f.name)

        if state.get(key, {}).get("sha256") == digest:
            print(f"[bỏ qua] {f.name} — không đổi kể từ lần nạp trước")
            stats["unchanged"] += 1
            continue
        if digest in {v.get("sha256") for v in state.values()}:
            print(f"[bỏ qua] {f.name} — nội dung trùng file khác")
            stats["duplicate"] += 1
            continue

        parsed = parse_legal_document(f.read_text(encoding="utf-8", errors="ignore"))
        report = validate_document(
            {
                "doc_id": parsed.doc_id,
                "title": parsed.title,
                "articles": [
                    {"article_number": x.article_number, "title": x.title, "content": x.content}
                    for x in parsed.articles
                ],
                "effective_date": getattr(parsed, "effective_date", "") or "",
            },
            known_doc_ids=existing,
            raw_text=f.read_text(encoding="utf-8", errors="ignore"),
            allow_replace=True,
        )
        errors = [i for i in report.issues if i.severity == "error"]
        if not report.passed:
            print(f"[TỪ CHỐI] {f.name} ({doc_id}): " + "; ".join(i.message for i in errors))
            stats["rejected"] += 1
            if a.apply:
                REJECTED.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(REJECTED / f.name))
                (REJECTED / (f.name + ".reason.txt")).write_text(
                    json.dumps(report.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            continue

        print(f"[NẠP] {f.name} -> {doc_id} ({len(parsed.articles)} điều)")
        stats["new"] += 1
        if a.apply:
            res = pipeline.ingest_file(str(f), sync_qdrant=False, sync_neo4j=True)
            print(f"        đã ghi: {res['articles_count']} điều, {res['chunks_count']} chunk")
            state[key] = {
                "sha256": digest,
                "doc_id": doc_id,
                "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            existing.add(doc_id)
            stats["ok"] += 1

    client.close()
    if a.apply:
        save_state(state)

    print("=" * 74)
    print(
        f"mới={stats['new']} đã nạp={stats['ok']} từ chối={stats['rejected']} "
        f"không đổi={stats['unchanged']} trùng={stats['duplicate']}"
    )
    if not a.apply and stats["new"]:
        print("DRY-RUN: thêm --apply để ghi thật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
