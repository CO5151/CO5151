"""Doi chieu TOAN BO corpus (Neo4j) voi du lieu chinh thuc cua Bo Tu phap.

Buoc 1: tai sitemap vbpl.vn, map so hieu -> id
Buoc 2: goi /api/qtdc/public/doc/{id} cho tung van ban
Buoc 3: so sanh status/revoked_by cua nhom voi effStatus cua Bo
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import httpx

UA = "LegalPilot-VN/1.0 (Educational Academic Agentic RAG; HCMUT)"
GW = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/"
OUT = Path("/Users/tungdl/Documents/CO5151/CO5151/data/processed/moj_status_audit.json")

# (doc_id, status, revoked_by) lay tu Neo4j
CORPUS = [
    ("02/2025/TT-NHNN", "in_force", None),
    ("08/2023/TT-NHNN", "in_force", None),
    ("101/2012/ND-CP", "expired", "52/2024/ND-CP"),
    ("12/2022/TT-NHNN", "in_force", None),
    ("14/2024/TT-NHNN", "in_force", None),
    ("17/2024/TT-NHNN", "in_force", None),
    ("18/2024/TT-NHNN", "in_force", None),
    ("20/2024/TT-NHNN", "in_force", None),
    ("21/2017/TT-NHNN", "in_force", None),
    ("21/2024/TT-NHNN", "in_force", None),
    ("26/2018/TT-NHNN", "in_force", None),
    ("26/2024/TT-NHNN", "in_force", None),
    ("26/2025/ND-CP", "in_force", None),
    ("32/2024/TT-NHNN", "in_force", None),
    ("37/2024/TT-NHNN", "in_force", None),
    ("39/2016/TT-NHNN", "in_force", None),
    ("40/2024/TT-NHNN", "in_force", None),
    ("45/2024/TT-NHNN", "in_force", None),
    ("48/2018/TT-NHNN", "in_force", None),
    ("50/2024/TT-NHNN", "in_force", None),
    ("51/2024/TT-NHNN", "in_force", None),
    ("52/2024/ND-CP", "in_force", None),
    ("57/2024/TT-NHNN", "in_force", None),
    ("58/2024/TT-NHNN", "in_force", None),
    ("60/2024/TT-NHNN", "in_force", None),
    ("61/2024/TT-NHNN", "in_force", None),
    ("64/2024/TT-NHNN", "in_force", None),
    ("94/2025/ND-CP", "in_force", None),
]


def needle(doc_id: str) -> str:
    """'101/2012/ND-CP' -> '-so-101-2012-nd-cp' de tim trong slug.

    The ``-so-`` anchor is required: without it the slug of an *amending*
    document ("nghi-dinh-sua-doi-nghi-dinh-so-101-2012-nd-cp") also matches and
    the audit compares against the wrong record.
    """
    s = unicodedata.normalize("NFD", doc_id.lower().replace("đ", "d"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"-so-{s}"


def norm_doc_num(value: str | None) -> str:
    """Compare-friendly form of a statute number (NĐ -> ND, upper, no spaces)."""
    s = unicodedata.normalize("NFD", (value or "").upper().replace("Đ", "D"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Z0-9/]+", "", s)
    return s.replace("ND-CP", "ND-CP")


def main() -> None:
    targets = {d: needle(d) for d, _, _ in CORPUS}
    found: dict[str, str] = {}

    with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": UA}) as c:
        idx = c.get("https://vbpl.vn/sitemap.xml").text
        subs = re.findall(r"<loc>([^<]+)</loc>", idx)
        print(f"{len(subs)} sitemap, dang quet...")
        for u in subs:
            try:
                txt = c.get(u).text
            except Exception:  # noqa: BLE001
                continue
            for url in re.findall(r"<loc>([^<]+)</loc>", txt):
                if "--" not in url:
                    continue
                slug, _, did = url.rpartition("--")
                # Prefer the shortest slug for a given number: the base
                # document has a shorter title than its amendments.
                for doc_id, nd in targets.items():
                    if nd not in slug:
                        continue
                    prev = found.get(doc_id)
                    if prev is None or len(slug) < prev[1]:
                        found[doc_id] = (did.strip(), len(slug))

    print(f"\nmap duoc {len(found)}/{len(targets)} van ban")
    for d in targets:
        if d not in found:
            print(f"  KHONG TIM THAY trong sitemap: {d}")

    results = []
    with httpx.Client(timeout=25.0, follow_redirects=True,
                      headers={"User-Agent": UA, "Accept": "application/json"}) as c:
        for doc_id, ours, revoked in CORPUS:
            entry = found.get(doc_id)
            did = entry[0] if entry else None
            rec = {"doc_id": doc_id, "graph_status": ours, "graph_revoked_by": revoked,
                   "moj_id": did}
            if not did:
                rec["moj"] = None
                results.append(rec)
                continue
            try:
                r = c.get(GW + did)
                if r.status_code == 200:
                    d = (r.json() or {}).get("data") or {}
                    eff = d.get("effStatus") or {}
                    rec["moj"] = {
                        "doc_num": d.get("docNum"),
                        "doc_num_matches": norm_doc_num(d.get("docNum")) == norm_doc_num(doc_id),
                        "eff_status": eff.get("name"),
                        "eff_code": eff.get("code"),
                        "eff_from": str(d.get("effFrom"))[:10] if d.get("effFrom") else None,
                        "eff_to": str(d.get("effTo"))[:10] if d.get("effTo") else None,
                        "title": (d.get("title") or "")[:80],
                    }
                else:
                    rec["moj"] = {"http": r.status_code}
            except Exception as e:  # noqa: BLE001
                rec["moj"] = {"error": f"{type(e).__name__}: {e}"}
            results.append(rec)
            time.sleep(0.15)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n{:<16} {:<9} {:<26} {:<12} {:<12}".format("doc_id", "graph", "moj_eff_status", "eff_from", "eff_to"))
    print("-" * 80)
    mism: list[str] = []
    unverified: list[str] = []
    for r in results:
        m = r.get("moj") or {}
        if m.get("doc_num_matches") is False:
            unverified.append(f"{r['doc_id']} -> matched {m.get('doc_num')}")
            continue
        eff = m.get("eff_status") or m.get("http") or m.get("error") or "(khong map duoc)"
        code = m.get("eff_code") or ""
        flag = ""
        if code == "CHL" and r["graph_status"] != "in_force":
            flag = "  <-- MISMATCH"
            mism.append(r["doc_id"])
        elif code and code != "CHL" and r["graph_status"] == "in_force":
            flag = "  <-- MISMATCH"
            mism.append(r["doc_id"])
        print("{:<16} {:<9} {:<26} {:<12} {:<12}{}".format(
            r["doc_id"], r["graph_status"], (eff or "")[:26],
            m.get("eff_from") or "-", m.get("eff_to") or "-", flag))

    print(f"\n{len(mism)} van ban lech: {mism}")
    if unverified:
        print(f"{len(unverified)} mapping khong khop docNum (bo qua): {unverified}")
    print("chi tiet:", OUT)


main()
