"""Cổng kiểm định trước khi ghi một văn bản vào LawGraph.

Đây là tầng 5 trong `docs/PLAN_AUTO_INGEST.md`. Mục đích: không cho dữ liệu xấu
vào graph đang phục vụ. Mọi kiểm tra ở đây là **tất định** — không dùng LLM —
nên chạy được trong CI và không bao giờ "thương lượng" với dữ liệu.

Vì sao cần: graph từng chứa Điều có tiêu đề "Quy định tại 52/2024/ND-CP" và nội
dung lặp lại, khiến truy xuất trả về điều khoản rỗng nghĩa. Đó là lỗi không thể
phát hiện bằng mắt khi corpus lớn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.core.doc_ids import canonical_doc_id, is_doc_code

MIN_ARTICLE_CHARS = 200          # dưới ngưỡng này coi là rỗng nghĩa
MIN_STRUCTURE_RATIO = 0.8        # % số Điều bóc được so với số Điều trong raw
MAX_DUPLICATE_CONTENT = 2        # cùng một nội dung lặp ở >=3 điều là bất thường

_ARTICLE_HEAD = re.compile(r"^\s*Điều\s+\d+\s*[\.:]", re.M)


@dataclass
class Issue:
    code: str
    message: str
    severity: str = "error"      # error = chặn publish | warn = cho qua, ghi log


@dataclass
class ValidationReport:
    doc_id: str
    passed: bool = True
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "passed": self.passed,
            "issues": [
                {"code": i.code, "message": i.message, "severity": i.severity}
                for i in self.issues
            ],
            "stats": self.stats,
        }


def _add(rep: ValidationReport, code: str, message: str, severity: str = "error") -> None:
    rep.issues.append(Issue(code, message, severity))
    if severity == "error":
        rep.passed = False


def count_articles_in_raw(raw_text: str) -> int:
    """Đếm số 'Điều N.' ở đầu dòng trong văn bản gốc."""
    return len(_ARTICLE_HEAD.findall(raw_text or ""))


def validate_document(
    doc: dict[str, Any],
    *,
    known_doc_ids: set[str] | None = None,
    raw_text: str | None = None,
    allow_replace: bool = False,
) -> ValidationReport:
    """Kiểm tra một văn bản đã bóc trước khi publish.

    Args:
        doc: {"doc_id", "title", "articles": [{"article_number", "title", "content"}],
              "cross_refs": [{"target_doc_id", ...}], "effective_date", "status"}
        known_doc_ids: các doc_id đã có trong graph (đã chuẩn hoá).
        raw_text: toàn văn gốc, dùng để đối chiếu số Điều.
        allow_replace: True khi đây là bản cập nhật có chủ đích.
    """
    known = {canonical_doc_id(x) for x in (known_doc_ids or set())}
    doc_id_raw = doc.get("doc_id", "")
    doc_id = canonical_doc_id(doc_id_raw)
    rep = ValidationReport(doc_id=doc_id)

    # V1. Mã văn bản hợp lệ
    if not doc_id:
        _add(rep, "V1_EMPTY_DOC_ID", "Thiếu số hiệu văn bản")
        return rep
    if not is_doc_code(doc_id):
        _add(rep, "V1_BAD_DOC_ID", f"'{doc_id_raw}' không phải số hiệu văn bản hợp lệ")

    # V2. Trùng mã
    if doc_id in known and not allow_replace:
        _add(rep, "V2_DUPLICATE_DOC", f"{doc_id} đã có trong graph")

    arts = doc.get("articles") or []
    rep.stats["articles"] = len(arts)

    # V3. Không có điều khoản nào
    if not arts:
        _add(rep, "V3_NO_ARTICLES", "Văn bản không bóc được điều khoản nào")
        return rep

    # V4. Tiêu đề placeholder / nội dung rỗng nghĩa
    doc_title = (doc.get("title") or "").strip().lower()
    placeholder = 0
    short = 0
    bodies: dict[str, int] = {}
    for a in arts:
        title = (a.get("title") or "").strip().lower()
        content = (a.get("content") or "").strip()
        if title in {doc_title, doc_id.lower()} or title.startswith("quy định tại "):
            placeholder += 1
        if len(content) < MIN_ARTICLE_CHARS:
            short += 1
        key = " ".join(content.split())[:160]
        if key:
            bodies[key] = bodies.get(key, 0) + 1

    rep.stats["placeholder_titles"] = placeholder
    rep.stats["short_articles"] = short
    if placeholder:
        _add(rep, "V4_PLACEHOLDER_TITLE",
             f"{placeholder}/{len(arts)} điều có tiêu đề placeholder")
    if short:
        _add(rep, "V4_SHORT_CONTENT",
             f"{short}/{len(arts)} điều ngắn hơn {MIN_ARTICLE_CHARS} ký tự", severity="warn")
    duplicated = sum(1 for c in bodies.values() if c > MAX_DUPLICATE_CONTENT)
    if duplicated:
        _add(rep, "V4_DUPLICATED_CONTENT",
             f"{duplicated} nội dung bị lặp ở hơn {MAX_DUPLICATE_CONTENT} điều")

    # V5. Đủ cấu trúc so với văn bản gốc
    if raw_text is not None:
        expected = count_articles_in_raw(raw_text)
        rep.stats["articles_in_raw"] = expected
        if expected and len(arts) < MIN_STRUCTURE_RATIO * expected:
            _add(rep, "V5_INCOMPLETE_STRUCTURE",
                 f"bóc được {len(arts)}/{expected} điều (< {int(MIN_STRUCTURE_RATIO*100)}%)")

    # V6. Dẫn chiếu chéo trỏ tới văn bản không tồn tại
    dangling = [
        r.get("target_doc_id")
        for r in (doc.get("cross_refs") or [])
        if canonical_doc_id(r.get("target_doc_id")) not in known | {doc_id}
    ]
    if dangling:
        _add(rep, "V6_DANGLING_CROSS_REF",
             f"dẫn chiếu tới văn bản không có trong graph: {', '.join(str(x) for x in dangling[:3])}",
             severity="warn")

    # V7. Thiếu ngày hiệu lực
    if not (doc.get("effective_date") or "").strip():
        _add(rep, "V7_MISSING_EFFECTIVE_DATE", "Thiếu ngày có hiệu lực", severity="warn")

    return rep
