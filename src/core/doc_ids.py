"""Mã văn bản pháp luật: chuẩn hoá để cùng một văn bản chỉ có MỘT khoá.

Vì sao cần: graph từng chứa cả `52/2024/ND-CP` và `52/2024/NĐ-CP` cho cùng một
nghị định. Hai node = hai tập điều khoản rời nhau, nên truy vấn chỉ thấy một nửa.

Dùng hàm này ở MỌI chỗ ghi doc_id vào graph, và ở chỗ so sánh/khử trùng.
"""

from __future__ import annotations

import re
import unicodedata

_SUFFIX = {
    "ND-CP": "ND-CP",
    "TT-NHNN": "TT-NHNN",
    "QH": "QH",
}


def canonical_doc_id(raw: str | None) -> str:
    """'52/2024/NĐ-CP' -> '52/2024/ND-CP'. Idempotent, an toàn với chuỗi rỗng."""
    if not raw:
        return ""
    s = unicodedata.normalize("NFD", str(raw).strip())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))  # bỏ dấu
    s = s.replace("Đ", "D").replace("đ", "d")
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", "", s)
    s = s.upper()
    # 'BỘ LUẬT' -> 'BO LUAT' sau khi bỏ dấu; giữ nguyên dạng có khoảng trắng cho tên luật
    return s


def is_doc_code(raw: str | None) -> bool:
    """True nếu là số hiệu văn bản (dạng 52/2024/ND-CP), False nếu là tên luật."""
    return bool(re.fullmatch(r"\d+/\d{4}/[A-Z0-9\-]+", canonical_doc_id(raw)))
