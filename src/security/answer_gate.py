"""Cổng kiểm chứng câu trả lời (output-side guardrail) cho LegalPilot-VN.

Đây là phần "thực thi ranh giới NGOÀI prompt" của seminar S2-5, áp vào chính
pipeline của nhóm:

  1. Mọi dẫn chiếu "Điều N <số hiệu văn bản>" trong bản nháp phải đối chiếu được
     với tập điều khoản đã thực sự truy xuất. Không khớp -> chặn.
  2. Không có dẫn chiếu nào -> chặn (không cho trả lời trống căn cứ).
  3. Khi bị chặn, hệ trả về câu "không đủ căn cứ" thay vì đoán.

Cổng là hàm thuần, tất định: cùng input luôn cùng output, không đọc "lời hứa"
của model, và không thể bị thuyết phục bằng prompt injection.
"""

from __future__ import annotations

import re

from src.core.doc_ids import canonical_doc_id

ABSTAIN_MSG = (
    "Tôi không đủ căn cứ để trả lời câu hỏi này dựa trên các văn bản hiện có "
    "trong cơ sở dữ liệu. Vui lòng cung cấp thêm văn bản hoặc liên hệ chuyên viên "
    "tuân thủ để được đối chiếu trực tiếp."
)

# "Điều 22 Nghị định 52/2024/NĐ-CP", "khoản 1 Điều 15 Thông tư 12/2022/TT-NHNN"
# Khoảng giữa "Điều N" và số hiệu văn bản KHÔNG được vượt qua một "Điều" khác:
# nếu không, câu "Điều 22, không phải Điều 99 Nghị định X" sẽ bị ghép sai thành
# cặp (22, X) và bỏ sót dẫn chiếu 99.
_CITE = re.compile(
    r"Điều\s+(\d+)(?:(?!Điều)[^\n]){0,40}?(\d{1,4}/\d{4}/[A-Za-zĐđ][A-Za-zĐđ\-]*)",
    re.I,
)
# Model có thể nhắc lại dẫn chiếu sai để bác nó -> không tính là khẳng định
_NEG = re.compile(
    r"không phải|không xác nhận|chưa xác nhận|không đúng|sai|bác bỏ|đính chính|không có căn cứ"
    # Nhắc một văn bản ĐỂ NÓI nó hết hiệu lực / bị thay thế không phải là trích dẫn nó
    # như căn cứ pháp lý. Thiếu nhóm này, cổng chặn oan các câu trả lời đúng.
    r"|hết hiệu lực|hết lực|bãi bỏ|thay thế|không còn hiệu lực|đã bị",
    re.I,
)


def _strip_md(text: str) -> str:
    return re.sub(r"[*_`]", "", text or "")


def extract_citations(text: str) -> set[tuple[str, str]]:
    """Tập (số điều, số hiệu văn bản) xuất hiện trong văn bản."""
    out: set[tuple[str, str]] = set()
    for m in _CITE.finditer(_strip_md(text)):
        out.add((m.group(1), canonical_doc_id(m.group(2))))
    return out


def allowed_from_clauses(clauses: list[dict]) -> set[tuple[str, str]]:
    """Tập dẫn chiếu hợp lệ từ các điều khoản đã truy xuất."""
    allowed: set[tuple[str, str]] = set()
    for c in clauses or []:
        doc = canonical_doc_id(c.get("doc_id", ""))
        art = str(c.get("article") or c.get("article_number") or "")
        num = re.sub(r"\D", "", art)
        if doc and num:
            allowed.add((num, doc))
    return allowed


def _only_negated(text: str, num: str, doc: str) -> bool:
    """True nếu mọi lần nhắc 'Điều <num> ... <doc>' đều nằm trong ngữ cảnh phủ định."""
    seen = False
    for m in _CITE.finditer(_strip_md(text)):
        if m.group(1) == num and canonical_doc_id(m.group(2)) == doc:
            seen = True
            window = text[max(0, m.start() - 100): m.end() + 60]
            if not _NEG.search(window):
                return False
    return seen


def gate_answer(
    answer: str,
    allowed: set[tuple[str, str]],
    revoked: set[tuple[str, str]] | None = None,
) -> tuple[bool, str, list]:
    """True = cho ra; False = chặn vì dẫn chiếu không có căn cứ.

    `revoked` là các văn bản đã bị loại trong vòng backtrack. Nhắc một văn bản
    đã bị bãi bỏ để nói "đã hết hiệu lực / được thay thế" là hợp lệ, miễn là
    câu trả lời vẫn còn ít nhất một căn cứ đang hiệu lực.

    Trả về (ok, lý do, danh sách dẫn chiếu sai).
    """
    if not (answer or "").strip():
        return False, "câu trả lời rỗng", []

    cites = extract_citations(answer)
    if not cites:
        return False, "không có dẫn chiếu nào trong câu trả lời", []

    revoked = revoked or set()
    bad = [c for c in sorted(cites - allowed - revoked)
           if not _only_negated(answer, c[0], c[1])]
    allowed_docs = {d for _, d in allowed}
    hard = [c for c in bad if c[1] not in allowed_docs]      # sai VĂN BẢN
    soft = [c for c in bad if c[1] in allowed_docs]          # đúng văn bản, khác điều

    if hard:
        detail = ", ".join(f"Điều {a} {d}" for a, d in hard)
        return False, f"dẫn chiếu tới văn bản không có trong ngữ cảnh: {detail}", hard

    if not (cites & allowed) and not soft:
        return False, "không có dẫn chiếu nào tới điều khoản còn hiệu lực", sorted(cites)

    if not (cites & allowed):
        detail = ", ".join(f"Điều {a} {d}" for a, d in soft)
        return False, f"chỉ trích điều không nằm trong ngữ cảnh ({detail})", soft

    if soft:
        detail = ", ".join(f"Điều {a} {d}" for a, d in soft)
        return True, f"có dẫn chiếu đúng văn bản nhưng khác điều đã truy xuất: {detail}", []

    return True, "mọi dẫn chiếu đều khớp điều khoản đã truy xuất", []


def unsupported_citations(answer: str, allowed: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Các dẫn chiếu không nằm trong `allowed` và không bị phủ định trong câu."""
    return [c for c in sorted(extract_citations(answer) - allowed)
            if not _only_negated(answer, c[0], c[1])]


def strip_citations(answer: str, bad: list[tuple[str, str]]) -> str:
    """Bóc bỏ đúng các dẫn chiếu không hợp lệ, giữ nguyên phần còn lại.

    Chỉ xoá cụm "Điều N ... <số hiệu>", không đụng tới nội dung câu. So khớp
    theo PHẦN SỐ HIỆU (vd '52/2024') vì văn bản có thể viết NĐ-CP hoặc ND-CP.
    """
    out = answer
    for num, doc in bad:
        head = "/".join(doc.split("/")[:2])          # '52/2024'
        if not head:
            continue
        pat = re.compile(
            rf"(?:theo\s+|căn cứ\s+|tại\s+|và\s+)?Điều\s+{num}\s*(?:của\s+)?"
            rf"(?:Thông tư|Nghị định|Luật|Bộ luật)?\s*(?:số\s*)?"
            rf"{re.escape(head)}[A-Za-zĐđ/\-]*[^,.;)\n]*",
            re.I,
        )
        out = pat.sub("", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\.\s*,", ".", out)          # "., " -> "."
    out = re.sub(r"([.;:])\s*,", r"\1", out)
    out = re.sub(r",\s*([.;:])", r"\1", out)
    out = re.sub(r"^[\s,.;:-]+", "", out)
    return out.strip()
