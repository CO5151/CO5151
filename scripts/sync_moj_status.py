"""Dong bo trang thai hieu luc tu cong Bo Tu phap vao graph.

Ap dung ket qua `audit_graph_vs_moj.py`:

* 12 van ban khop            -> chi ghi them metadata, khong doi status
* 11 "het hieu luc mot phan" -> KHONG phai loi: graph chi co 2 trang thai.
                                 Ghi `eff_status_code=HHL1P`, giu in_force.
*  3 "het hieu luc toan bo"  -> LOI THAT. status -> expired, ghi `expired_effective`.
*  1 nguoc chieu (101/2012)  -> `revoked_by` -> `superseded_by`, status -> in_force,
                                 giu eff_to = 2027-07-01.
*  1 bat thuong (52/2024)    -> MoJ ghi "Chua co hieu luc" tu 2027-07-01, mau thuan
                                 voi thuc te va voi chinh 101/2012. KHONG sua,
                                 chi ghi co `moj_anomaly`.

Chay: ../.venv-adk/bin/python scripts/sync_moj_status.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

AUDIT = Path("data/processed/moj_status_audit.json")
EXPORT = Path("data/processed/neo4j_graph_export.json")

BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "legalpilot2026")

# Trang thai MoJ -> status cua graph
CODE_TO_STATUS = {"CHL": "in_force", "HHL1P": "in_force", "HHL": "expired"}

ANOMALY = {"52/2024/ND-CP"}


def plan(rows: list[dict]) -> list[dict]:
    """Tinh ra danh sach lenh can ap dung."""
    ops: list[dict] = []
    for r in rows:
        doc_id = r["doc_id"]
        m = r.get("moj") or {}
        if not m or m.get("doc_num_matches") is False:
            continue
        code = m.get("eff_code")
        if not code:
            continue

        op = {
            "doc_id": doc_id,
            "moj_id": r.get("moj_id"),
            "eff_status_code": code,
            "eff_status_name": m.get("eff_status"),
            "eff_from": m.get("eff_from"),
            "eff_to": m.get("eff_to"),
        }

        if doc_id in ANOMALY:
            op["moj_anomaly"] = "MoJ ghi chua co hieu luc tu 2027-07-01; mau thuan thuc te"
        elif code in CODE_TO_STATUS:
            op["set_status"] = CODE_TO_STATUS[code]
            if code == "HHL":
                op["expired_effective"] = m.get("eff_to")
        if doc_id == "101/2012/ND-CP":
            op["superseded_by"] = r.get("graph_revoked_by")
            op["set_status"] = "in_force"
            op["clear_revoked_by"] = True
        ops.append(op)
    return ops


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = json.loads(AUDIT.read_text(encoding="utf-8"))
    ops = plan(rows)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print(f"{len(ops)} van ban se duoc cap nhat")
    for op in ops:
        extra = ""
        if op.get("set_status") and op["set_status"] != "in_force":
            extra = f" -> {op['set_status']} ({op.get('expired_effective')})"
        if op.get("superseded_by"):
            extra = f" -> superseded_by={op['superseded_by']}, in_force den {op.get('eff_to')}"
        if op.get("moj_anomaly"):
            extra = " -> GIU NGUYEN (bat thuong du lieu MoJ)"
        print(f"  {op['doc_id']:<18} {op['eff_status_code']:<6}{extra}")

    if args.dry_run:
        print("\n(dry-run, khong ghi gi)")
        return

    driver = GraphDatabase.driver(BOLT, auth=(USER, PWD))
    with driver.session() as s:
        for op in ops:
            s.run(
                """
                MATCH (d:Document {doc_id: $doc_id})
                SET d.moj_id = $moj_id,
                    d.eff_status_code = $code,
                    d.eff_status_name = $name,
                    d.eff_from = $eff_from,
                    d.eff_to = $eff_to,
                    d.moj_synced_at = $ts
                """,
                doc_id=op["doc_id"], moj_id=op["moj_id"], code=op["eff_status_code"],
                name=op["eff_status_name"], eff_from=op["eff_from"],
                eff_to=op["eff_to"], ts=ts,
            )
            if op.get("set_status"):
                s.run(
                    "MATCH (d:Document {doc_id: $doc_id}) SET d.status = $st",
                    doc_id=op["doc_id"], st=op["set_status"],
                )
            if op.get("expired_effective"):
                s.run(
                    "MATCH (d:Document {doc_id: $doc_id}) SET d.expired_effective = $e",
                    doc_id=op["doc_id"], e=op["expired_effective"],
                )
            if op.get("superseded_by"):
                s.run(
                    "MATCH (d:Document {doc_id: $doc_id}) "
                    "SET d.superseded_by = $sb REMOVE d.revoked_by",
                    doc_id=op["doc_id"], sb=op["superseded_by"],
                )
            if op.get("moj_anomaly"):
                s.run(
                    "MATCH (d:Document {doc_id: $doc_id}) SET d.moj_anomaly = $a",
                    doc_id=op["doc_id"], a=op["moj_anomaly"],
                )
    driver.close()
    print(f"\nda ghi Neo4j ({BOLT})")

    # Cap nhat file export de fallback offline cung dung
    if EXPORT.exists():
        data = json.loads(EXPORT.read_text(encoding="utf-8"))
        changed = 0
        for op in ops:
            node = data.get(op["doc_id"])
            if not node:
                continue
            node["moj_id"] = op["moj_id"]
            node["eff_status_code"] = op["eff_status_code"]
            node["eff_status_name"] = op["eff_status_name"]
            node["eff_from"] = op["eff_from"]
            node["eff_to"] = op["eff_to"]
            node["moj_synced_at"] = ts
            if op.get("set_status"):
                node["status"] = op["set_status"]
            if op.get("expired_effective"):
                node["expired_effective"] = op["expired_effective"]
            if op.get("superseded_by"):
                node["superseded_by"] = op["superseded_by"]
                node.pop("revoked_by", None)
            if op.get("moj_anomaly"):
                node["moj_anomaly"] = op["moj_anomaly"]
            changed += 1
        EXPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"da cap nhat {changed} node trong {EXPORT}")


main()
