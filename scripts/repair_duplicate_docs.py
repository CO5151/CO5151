#!/usr/bin/env python3
"""Gộp các Document trùng mã trong Neo4j (ví dụ '52/2024/ND-CP' vs '52/2024/NĐ-CP').

    python scripts/repair_duplicate_docs.py           # chỉ báo cáo (dry-run)
    python scripts/repair_duplicate_docs.py --apply   # gộp thật

Nguyên tắc: giữ node có NHIỀU điều khoản nhất (nếu hoà thì giữ dạng không dấu),
chuyển toàn bộ quan hệ của node kia sang, rồi xoá node thừa.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.doc_ids import canonical_doc_id  # noqa: E402
from src.knowledge.neo4j_client import Neo4jClient  # noqa: E402

REL_TYPES = ["CONTAINS", "ISSUED_BY", "GUIDES", "SUPERSEDES", "AMENDS", "REPEALS", "CITES"]


def list_docs(client: Neo4jClient) -> list[dict]:
    with client.driver.session() as s:
        return [r.data() for r in s.run(
            "MATCH (d:Document) "
            "OPTIONAL MATCH (d)-[:CONTAINS]->(c) "
            "RETURN d.doc_id AS id, count(c) AS children ORDER BY id")]


def merge(client: Neo4jClient, keep: str, drop: str) -> None:
    """Chuyển hết quan hệ từ `drop` sang `keep`, rồi xoá `drop`."""
    with client.driver.session() as s:
        for rel in REL_TYPES:
            # đi ra
            s.run(
                f"MATCH (drop:Document {{doc_id: $drop}})-[r:{rel}]->(t) "
                f"MATCH (keep:Document {{doc_id: $keep}}) "
                f"MERGE (keep)-[:{rel}]->(t) "
                f"DELETE r",
                drop=drop, keep=keep)
            # đi vào
            s.run(
                f"MATCH (src)-[r:{rel}]->(drop:Document {{doc_id: $drop}}) "
                f"MATCH (keep:Document {{doc_id: $keep}}) "
                f"MERGE (src)-[:{rel}]->(keep) "
                f"DELETE r",
                drop=drop, keep=keep)
        s.run("MATCH (drop:Document {doc_id: $drop}) DELETE drop", drop=drop)


def dedupe_articles(client: Neo4jClient) -> None:
    """Gộp các Article cùng (doc_id, số điều) — giữ bản nội dung dài nhất."""
    # Sau khi gộp Document, các Article cùng số hiệu có thể bị nhân đôi
    # (mỗi node cũ mang một bản). Giữ bản nội dung dài nhất, chuyển Clause
    # con sang, xoá bản còn lại.
    with client.driver.session() as s:
        dup = [r.data() for r in s.run(
            "MATCH (d:Document)-[:CONTAINS]->(a:Article) "
            "WITH d, a.article_number AS num, collect(a) AS arts "
            "WHERE size(arts) > 1 "
            "RETURN d.doc_id AS doc, num, size(arts) AS n")]
        if dup:
            print(f"\nĐiều khoản bị nhân đôi: {len(dup)} nhóm")
            for row in dup:
                print(f"  {row['doc']} Điều {row['num']} × {row['n']}")
            s.run(
                "MATCH (d:Document)-[:CONTAINS]->(a:Article) "
                "WITH d, a.article_number AS num, collect(a) AS arts "
                "WHERE size(arts) > 1 "
                "WITH d, num, arts, "
                "     reduce(best = arts[0], x IN arts | "
                "       CASE WHEN size(coalesce(x.content,'')) > size(coalesce(best.content,'')) "
                "            THEN x ELSE best END) AS keep "
                "FOREACH (x IN [y IN arts WHERE y <> keep] | "
                "   FOREACH (c IN [(x)-[:CONTAINS]->(z) | z] | MERGE (keep)-[:CONTAINS]->(c)) "
                "   DETACH DELETE x)")
            print("  đã gộp xong.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="thực sự gộp (mặc định chỉ báo cáo)")
    a = ap.parse_args()

    client = Neo4jClient()
    try:
        docs = list_docs(client)
        groups: dict[str, list[dict]] = defaultdict(list)
        for d in docs:
            groups[canonical_doc_id(d["id"])].append(d)

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Tổng số Document: {len(docs)}")
        print(f"Nhóm trùng mã   : {len(dupes)}")

        if not dupes:
            print("Không có Document trùng mã.")
            dedupe_articles(client)
            return 0

        plans = []
        for key, items in dupes.items():
            items.sort(key=lambda x: (-x["children"], "Đ" in x["id"], x["id"]))
            keep, drops = items[0], items[1:]
            plans.append((key, keep, drops))
            print(f"\n  {key}")
            print(f"    giữ  : {keep['id']}  ({keep['children']} điều khoản)")
            for d in drops:
                print(f"    gộp  : {d['id']}  ({d['children']} điều khoản)")

        if not a.apply:
            print("\n(dry-run) thêm --apply để gộp thật.")
            return 0

        for key, keep, drops in plans:
            for d in drops:
                merge(client, keep["id"], d["id"])
                print(f"  đã gộp {d['id']} -> {keep['id']}")

        after = list_docs(client)
        print(f"\nSau khi sửa: {len(after)} Document")

        dedupe_articles(client)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
