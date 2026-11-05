#!/usr/bin/env python3
"""Collect the State Bank of Vietnam (SBV) statutory corpus from vbpl.vn.

SBV-LawGraph (Phan et al., ACIIDS 2026) reports 1,703 SBV documents sourced from
the national legal database but does not release them, so this script rebuilds
the corpus from the same source:

1. ``select``: read the public vbpl.vn sitemaps (allowed by robots.txt) and keep
   URLs whose slug carries an SBV document number (``tt-nhnn``, ``qd-nhnn``,
   ``ttlt-...-nhnn``, legacy ``qd-nh1``...) or a banking keyword for Laws,
   Ordinances, Decrees and Resolutions.
2. ``fetch``: call the public MoJ gateway ``/api/qtdc/public/doc/{id}`` (the
   endpoint the vbpl.vn frontend itself uses; no auth) once per candidate,
   throttled, cached as gzip so re-runs never re-download.
3. ``export``: keep documents whose drafting organisation is SBV (``NHNNVN``)
   and whose type matches the paper's composition (Table 1), then write
   ``<doc>.html`` + ``<doc>.meta.json`` pairs that
   ``python -m src.knowledge.ingestion --dir data/raw/sbv`` consumes.

Usage:
    python scripts/crawl_sbv_corpus.py all            # select + fetch + export
    python scripts/crawl_sbv_corpus.py fetch --limit 5
    python scripts/crawl_sbv_corpus.py export          # re-filter, no network
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.knowledge.ingestion import normalize_doc_id  # noqa: E402

OUT_DIR = WORKSPACE / "data/raw/sbv"
SITEMAP_DIR = OUT_DIR / "_sitemaps"
GATEWAY_DIR = OUT_DIR / "_gateway"
CANDIDATES_FILE = OUT_DIR / "candidates.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"

SITEMAP_INDEX = "https://vbpl.vn/sitemap.xml"
GATEWAY = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/"
USER_AGENT = "LegalPilot-VN/1.0 (Educational Academic Agentic RAG; HCMUT)"

SBV_ORG_CODE = "NHNNVN"

# Document types that make up the SBV corpus in SBV-LawGraph Table 1.
# Directives (Chỉ thị) and consolidated texts (Văn bản hợp nhất) are excluded.
KEPT_TYPE_NAMES = {
    "Luật",
    "Pháp lệnh",
    "Nghị quyết",
    "Nghị định",
    "Quyết định",
    "Thông tư",
    "Thông tư liên tịch",
}

# MoJ effStatus code -> canonical status (see src/core/statute_status.py).
# Partial repeal stays in force at document level, matching sync_moj_status.py.
EFF_CODE_TO_STATUS = {
    "CHL": "in_force",
    "HHL1P": "in_force",
    "HHL": "expired",
    "CCHL": "not_in_force",
}

# Documents where the MoJ record contradicts the instruments themselves.
# Decree 52/2024 Art. 37 sets effect from 2024-07-01 and replaces Decree 101/2012,
# but the gateway lists 52/2024 as "Chưa có hiệu lực" from 2027-07-01 and keeps
# 101/2012 in force (flagged as moj_anomaly by scripts/sync_moj_status.py).
STATUS_OVERRIDES: dict[str, dict[str, Any]] = {
    "52/2024/ND-CP": {
        "status": "in_force",
        "effective_date": "2024-07-01",
        "override_reason": "MoJ lists CCHL from 2027-07-01; Art. 37.1 sets 2024-07-01",
    },
    "101/2012/ND-CP": {
        "status": "expired",
        "revoked_by": "52/2024/ND-CP",
        "revoked_date": "2024-07-01",
        "inbound_relations": [
            {
                "source_doc_id": "52/2024/ND-CP",
                "rel_type": "SUPERSEDES",
                "scope": "Decree 52/2024/ND-CP Art. 37.2: thay thế",
            }
        ],
        "override_reason": "Replaced by Decree 52/2024/ND-CP Art. 37.2",
    },
}

SBV_NUMBER = re.compile(r"-so-\d+[a-z]?-\d{4}-[a-z0-9\-]*?nhnn")
SBV_NUMBER_NO_YEAR = re.compile(r"-so-\d+[a-z]?-(qd|tt|ttlt)-nhnn")
SBV_LEGACY_NUMBER = re.compile(r"-so-\d+[a-z]?-(\d{4}-)?(qd|tt|ttlt)-nh\d")
PRIMARY_TYPES = re.compile(r"^(luat|phap-lenh|nghi-dinh|nghi-quyet)")
BANKING_KEYWORDS = re.compile(
    r"ngan-hang|to-chuc-tin-dung|tien-te|ngoai-hoi|thanh-toan-khong-dung-tien-mat"
    r"|bao-hiem-tien-gui|kinh-doanh-vang|vi-dien-tu|trung-gian-thanh-toan|tin-dung"
)
EXCLUDED_PREFIXES = ("van-ban-hop-nhat", "chi-thi", "sac-lenh")

# MoJ editors record whole-document repeal in ``applicationNote``, e.g.
# "Bị thay thế bởi  Nghị định 01/2014/NĐ-CP Về việc ...". Partial repeal
# ("Bị bãi bỏ một phần bởi") is deliberately not matched.
REPEAL_NOTE = re.compile(r"^\s*Bị (thay thế|bãi bỏ|hủy bỏ|huỷ bỏ) bởi\s+(.*)", re.S)
DOC_NUMBER = re.compile(r"\d+(?:/\d{4})?/[A-ZĐ][A-ZĐa-zđ0-9\-]*")


def parse_repeal_note(note: str | None) -> list[dict[str, str]]:
    """Turns an MoJ applicationNote into inbound SUPERSEDES relations."""
    match = REPEAL_NOTE.match(note or "")
    if not match:
        return []
    verb, rest = match.groups()
    sources = dict.fromkeys(normalize_doc_id(n) for n in DOC_NUMBER.findall(rest))
    return [
        {
            "source_doc_id": source,
            "rel_type": "SUPERSEDES",
            "scope": f"MoJ applicationNote: bị {verb}",
        }
        for source in sources
    ]


def _client(accept_json: bool = False) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT}
    if accept_json:
        headers["Accept"] = "application/json"
    return httpx.Client(timeout=60.0, follow_redirects=True, headers=headers)


def download_sitemaps(delay: float) -> list[Path]:
    """Downloads the sitemap index and every sub-sitemap once (cached on disk)."""
    SITEMAP_DIR.mkdir(parents=True, exist_ok=True)
    index_file = SITEMAP_DIR / "index.xml"
    with _client() as client:
        if not index_file.exists():
            index_file.write_text(client.get(SITEMAP_INDEX).text, encoding="utf-8")
        subs = re.findall(r"<loc>([^<]+)</loc>", index_file.read_text(encoding="utf-8"))
        paths = []
        for url in subs:
            path = SITEMAP_DIR / url.rsplit("/", 1)[-1]
            if not path.exists():
                path.write_text(client.get(url).text, encoding="utf-8")
                time.sleep(delay)
            paths.append(path)
    return paths


def classify_slug(slug: str) -> str | None:
    """Returns the candidate group of a vbpl.vn slug, or None if irrelevant."""
    if slug.startswith(EXCLUDED_PREFIXES):
        return None
    if SBV_NUMBER.search(slug):
        return "sbv_number"
    if SBV_NUMBER_NO_YEAR.search(slug):
        return "sbv_number_no_year"
    if SBV_LEGACY_NUMBER.search(slug):
        return "sbv_legacy_number"
    if PRIMARY_TYPES.match(slug) and BANKING_KEYWORDS.search(slug):
        return "banking_keyword"
    return None


def select(delay: float) -> list[dict[str, str]]:
    """Builds the candidate list from the sitemaps."""
    candidates: dict[str, dict[str, str]] = {}
    for path in download_sitemaps(delay):
        for url in re.findall(r"<loc>([^<]+)</loc>", path.read_text(encoding="utf-8")):
            slug, sep, vbpl_id = url.rsplit("/", 1)[-1].rpartition("--")
            if not sep or not vbpl_id:
                continue
            group = classify_slug(slug)
            if group:
                candidates[vbpl_id] = {"vbpl_id": vbpl_id, "group": group, "url": url}
    rows = sorted(candidates.values(), key=lambda r: (r["group"], r["vbpl_id"]))
    CANDIDATES_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"select: {len(rows)} candidates", dict(collections.Counter(r["group"] for r in rows)))
    return rows


def _gateway_path(vbpl_id: str) -> Path:
    return GATEWAY_DIR / f"{vbpl_id}.json.gz"


def fetch(delay: float, limit: int | None, max_consecutive_errors: int = 10) -> None:
    """Downloads gateway records for every candidate not cached yet."""
    rows = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    GATEWAY_DIR.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if not _gateway_path(r["vbpl_id"]).exists()]
    print(f"fetch: {len(rows) - len(todo)} cached, {len(todo)} missing (delay {delay}s)")
    if limit is not None:
        todo = todo[:limit]

    errors = 0
    with _client(accept_json=True) as client:
        for i, row in enumerate(todo, 1):
            vbpl_id = row["vbpl_id"]
            for attempt in range(4):
                try:
                    resp = client.get(GATEWAY + vbpl_id)
                except httpx.HTTPError as e:
                    status, body = None, str(e)
                else:
                    status, body = resp.status_code, resp.text
                if status == 200:
                    _gateway_path(vbpl_id).write_bytes(gzip.compress(body.encode("utf-8")))
                    errors = 0
                    break
                if status in (404, 400):
                    # Permanent: record the miss so it is not retried every run.
                    _gateway_path(vbpl_id).write_bytes(
                        gzip.compress(json.dumps({"http_status": status}).encode("utf-8"))
                    )
                    break
                wait = delay * (2 ** (attempt + 2))
                print(f"  [{vbpl_id}] HTTP {status}: retry in {wait:.0f}s ({body[:80]!r})")
                time.sleep(wait)
            else:
                errors += 1
                if errors >= max_consecutive_errors:
                    sys.exit(f"fetch: stopping after {errors} consecutive failures")
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}")
            time.sleep(delay)


def _date(value: Any) -> str | None:
    return str(value)[:10] if value else None


def _load_record(vbpl_id: str) -> dict[str, Any] | None:
    path = _gateway_path(vbpl_id)
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    return payload.get("data") if isinstance(payload, dict) else None


def export() -> None:
    """Filters cached records and writes HTML + metadata sidecars for ingestion."""
    rows = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    manifest: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for row in rows:
        rec = _load_record(row["vbpl_id"])
        entry: dict[str, Any] = {"vbpl_id": row["vbpl_id"], "group": row["group"]}
        if rec is None:
            entry["kept"], entry["reason"] = False, "not_fetched_or_missing"
            manifest.append(entry)
            continue

        org = (rec.get("organization") or {}).get("code")
        type_name = (rec.get("docType") or {}).get("name")
        eff = rec.get("effStatus") or {}
        content = (rec.get("documentContent") or {}).get("content") or ""
        doc_num = rec.get("docNum") or ""
        entry.update(
            doc_num=doc_num,
            doc_type=type_name,
            organization=org,
            eff_status_code=eff.get("code"),
            eff_status_name=eff.get("name"),
            content_chars=len(content),
        )

        if org != SBV_ORG_CODE and "NHNN" not in normalize_doc_id(doc_num):
            entry["kept"], entry["reason"] = False, "not_sbv"
        elif type_name not in KEPT_TYPE_NAMES:
            entry["kept"], entry["reason"] = False, "excluded_type"
        elif not content.strip():
            entry["kept"], entry["reason"] = False, "no_content"
        else:
            entry["kept"], entry["reason"] = True, "sbv_corpus"
        manifest.append(entry)
        if not entry["kept"]:
            continue

        doc_id = normalize_doc_id(doc_num)
        issue_date = _date(rec.get("issueDate"))
        if doc_id in seen and seen[doc_id] != row["vbpl_id"]:
            # Legacy numbers have no year and are reused; disambiguate by issue year.
            doc_id = f"{doc_id}@{(issue_date or '0000')[:4]}"
        seen[doc_id] = row["vbpl_id"]
        entry["doc_id"] = doc_id

        meta: dict[str, Any] = {
            "doc_id": doc_id,
            "title": re.sub(r"\s+", " ", rec.get("title") or "").strip(),
            "doc_type": type_name,
            "issuer": rec.get("agencyName"),
            "issue_date": issue_date,
            "effective_date": _date(rec.get("effFrom")) or issue_date,
            "expiration_date": _date(rec.get("effTo")),
            "status": EFF_CODE_TO_STATUS.get(eff.get("code") or "", "unknown"),
            "eff_status_code": eff.get("code"),
            "eff_status_name": eff.get("name"),
            "moj_id": row["vbpl_id"],
            "source_url": row["url"],
            "status_source": "moj_gateway",
        }
        relations = parse_repeal_note(rec.get("applicationNote"))
        if relations and meta["status"] == "expired":
            meta["inbound_relations"] = relations
            meta["revoked_by"] = relations[0]["source_doc_id"]
            meta["revoked_date"] = meta["expiration_date"]
            meta["application_note"] = re.sub(r"\s+", " ", rec["applicationNote"]).strip()
        if doc_id in STATUS_OVERRIDES:
            meta.update(STATUS_OVERRIDES[doc_id], status_source="manual_override")

        entry["revoked_by"] = meta.get("revoked_by")
        stem = re.sub(r"[^A-Za-z0-9@._-]+", "_", doc_id)
        (OUT_DIR / f"{stem}.html").write_text(content, encoding="utf-8")
        (OUT_DIR / f"{stem}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    kept = [m for m in manifest if m["kept"]]
    print(f"export: kept {len(kept)} / {len(manifest)} candidates")
    print("  reasons:", dict(collections.Counter(m["reason"] for m in manifest)))
    print("  types:", dict(collections.Counter(m["doc_type"] for m in kept)))
    print("  status:", dict(collections.Counter(m["eff_status_code"] for m in kept)))
    print("  repeal links from applicationNote:", sum(1 for m in kept if m.get("revoked_by")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("stage", choices=["select", "fetch", "export", "all"])
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--limit", type=int, default=None, help="fetch at most N records")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.stage in ("select", "all"):
        select(args.delay)
    if args.stage in ("fetch", "all"):
        fetch(args.delay, args.limit)
    if args.stage in ("export", "all"):
        export()


if __name__ == "__main__":
    main()
