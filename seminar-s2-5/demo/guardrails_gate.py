#!/usr/bin/env python3
"""Multi-Tier Agentic Guardrails Engine cho LegalPilot-VN (S2-5).

Kiến trúc Guardrails 3 tầng (kết hợp SOTA):
  - Tầng 1 (Input/Semantic Rail): Chặn Indirect Prompt Injection, Jailbreak,
    Hijacking theo tiêu chuẩn benchmark InjecAgent (ACL 2024) & Llama Guard 3.
  - Tầng 2 (Action Boundary Rail): Thi hành ma trận phân quyền C0--C4,
    chặn tool misuse và vượt quyền theo Shavit et al. (2023) & ASSEBench (NeurIPS 2025).
  - Tầng 3 (Output / Citation Gate): Chặn Sycophancy (gật theo người dùng),
    chặn Hallucination (bịa điều khoản), thực thi nguyên tắc Fail-Closed.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent
def _find_testset() -> pathlib.Path:
    candidates = [
        HERE / "sbv_testset_tvpl.json",
        HERE.parent / "data" / "benchmarks" / "sbv_testset_tvpl.json",
        HERE.parent.parent / "data" / "benchmarks" / "sbv_testset_tvpl.json",
        HERE.parent.parent / "CO5151" / "data" / "benchmarks" / "sbv_testset_tvpl.json",
        pathlib.Path("/Users/tungdl/Documents/CO5151/CO5151/data/benchmarks/sbv_testset_tvpl.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]
TESTSET = _find_testset()

FAIL_ANSWER = "Tôi không đủ căn cứ để trả lời."

# ==============================================================================
# TẦNG 1: INPUT / PROMPT INJECTION GUARDRAIL (InjecAgent ACL 2024 & Llama Guard 3)
# ==============================================================================
INJECTION_PATTERNS = [
    (re.compile(r"bỏ qua (mọi|toàn bộ|tất cả)?\s*(hướng dẫn|chỉ thị|quy định|nguyên tắc|luật)", re.I),
     "Phát hiện chỉ thị ghi đè hệ thống (System Prompt Override)"),
    (re.compile(r"ignore (all|previous)?\s*(instructions|rules|guidelines|system)", re.I),
     "Phát hiện Prompt Injection bằng tiếng Anh (Instruction Bypass)"),
    (re.compile(r"(chế độ|mode)\s*(nhà phát triển|admin|root|jailbreak|developer)", re.I),
     "Phát hiện mạo danh đặc quyền quản trị (Privilege Escalation Attempt)"),
    (re.compile(r"(thay đổi|ghi đè|xoá|sửa)\s*(prompt|hệ thống|database|db|config|chính sách)", re.I),
     "Cố gắng can thiệp cấu hình hệ thống (C4 Violation via Prompt)"),
    (re.compile(r"(tự động nộp|gửi tiền|chuyển khoản|phê duyệt trực tiếp)", re.I),
     "Cố gắng kích hoạt hành động không thể hoàn tác mà không qua HITL"),
]


def check_input_guardrail(user_prompt: str, user_claim: str = "") -> Tuple[bool, str]:
    """Kiểm tra đầu vào xem có chứa chỉ thị tấn công prompt injection không."""
    combined = f"{user_prompt} {user_claim}"
    for pattern, desc in INJECTION_PATTERNS:
        if pattern.search(combined):
            return False, f"[INJECTION VIOLATION] {desc}"
    return True, "An toàn (Không phát hiện injection)"


# ==============================================================================
# TẦNG 2: ACTION BOUNDARY RAIL (C0--C4 Gateway theo Shavit 2023 & ASSEBench 2025)
# ==============================================================================
ACTION_POLICIES = {
    "C0": {"name": "Đọc (Qdrant/Neo4j/PDF)", "allow": True, "need_approval": False},
    "C1": {"name": "Tính nội bộ (Plan/Draft/Staging)", "allow": True, "need_approval": False},
    "C2": {"name": "Gửi ra ngoài (Send Email/POST API)", "allow": False, "need_approval": True},
    "C3": {"name": "Hành động không hoàn tác (Nộp hồ sơ/Đổi DB)", "allow": False, "need_approval": True, "default_deny": True},
    "C4": {"name": "Tự sửa (Code/Prompt/Policy)", "allow": False, "strict_deny": True},
}


def check_action_guardrail(action_type: str, approval_token: Optional[str] = None,
                           payload_hash: Optional[str] = None) -> Tuple[bool, str]:
    """Kiểm tra ranh giới hành động ngoài prompt.
    
    Chỉ cho phép C0 và C1 chạy tự động.
    C2 cần token duyệt kèm hash. C3 và C4 mặc định DENY.
    """
    act = action_type.upper()
    if act in ("C0", "READ", "RETRIEVE"):
        return True, "C0 (Đọc dữ liệu): Cho phép tự động với quyền Read-Only"
    if act in ("C1", "INTERNAL_DRAFT", "STAGE"):
        return True, "C1 (Tính toán nội bộ): Cho phép tự động trong sandbox"
    if act in ("C2", "EXTERNAL_API", "SEND_EMAIL"):
        if approval_token and payload_hash and len(approval_token) >= 8:
            return True, f"C2 (Tác động ngoài): Chấp thuận qua Human Approval Token (Hash: {payload_hash[:8]})"
        return False, "[ACTION BOUNDARY VIOLATION] C2 yêu cầu Human Approval Token gắn hash(payload). Thiếu token -> DENY."
    if act in ("C3", "IRREVERSIBLE", "COMMIT_DB", "SUBMIT_DOC"):
        return False, "[ACTION BOUNDARY VIOLATION] C3 (Không thể hoàn tác) bị cấm (Hard DENY by Policy) để phòng ngừa thảm họa."
    if act in ("C4", "SELF_MODIFY", "MUTATE_POLICY"):
        return False, "[CRITICAL ACTION VIOLATION] C4 (Tự sửa code/prompt/policy) bị chặn tuyệt đối (Zero Trust)."
    return False, f"[UNKNOWN ACTION] Hành vi '{action_type}' không nằm trong Action Set cho phép -> DENY by default."


# ==============================================================================
# TẦNG 3: OUTPUT CITATION & ANTI-SYCOPHANCY GATE (Grounding Oracle)
# ==============================================================================
STRIP = re.compile(r"[*_`]")
CITE = re.compile(
    r"Điều\s+(\d+)[^0-9]{0,25}?(Thông tư|Nghị định|Luật|Bộ luật)\s+(\d+/\d{4})",
    re.I
)
NEG = re.compile(
    r"không phải|không xác nhận|chưa xác nhận|không đúng|sai|"
    r"không có căn cứ|bác bỏ|đính chính|không thuộc",
    re.I
)


def citations(text: str) -> set[Tuple[str, str]]:
    """Trích xuất tập (số điều, số văn bản) chuẩn hóa."""
    out = set()
    for m in CITE.finditer(STRIP.sub("", text or "")):
        out.add((m.group(1), m.group(3)))
    return out


def _mentioned_only(answer: str, art_no: str, doc_no: str) -> bool:
    """Kiểm tra xem điều khoản có phải chỉ được nêu ra trong ngữ cảnh phủ định."""
    seen = False
    for m in re.finditer(rf"Điều\s*{art_no}\b", answer):
        seen = True
        window = answer[max(0, m.start() - 90): m.end() + 50]
        if not NEG.search(window):
            return False
    return seen


def check_citation_guardrail(answer: str, context: str, user_claim: str = "") -> Tuple[bool, str, List[Tuple[str, str]], bool]:
    """Kiểm chứng dẫn chiếu đầu ra:
    
    - Kiểm tra có dẫn chiếu hợp lệ không
    - Kiểm tra trích dẫn ma / hallucination
    - Kiểm tra sycophancy (model gật theo khẳng định sai của người dùng)
    """
    c_ans = citations(answer)
    c_ctx = citations(context)
    c_claim = citations(user_claim)

    # Kiểm tra sycophancy: user nêu điều sai (c_claim không có trong c_ctx)
    # và model xác nhận điều sai đó
    sycophancy_detected = False
    for claim_art, claim_doc in c_claim:
        if (claim_art, claim_doc) not in c_ctx:
            if (claim_art, claim_doc) in c_ans and not _mentioned_only(answer, claim_art, claim_doc):
                sycophancy_detected = True

    if not c_ans:
        return False, "[CITATION MISSING] Model không trích dẫn được điều khoản căn cứ pháp lý cụ thể", [], sycophancy_detected

    if not c_ctx:
        return False, "[CORPUS EMPTY] Tài liệu cơ sở không chứa căn cứ hợp lệ để đối soát", [], sycophancy_detected

    bad = [c for c in sorted(c_ans - c_ctx) if not _mentioned_only(answer, c[0], c[1])]
    if bad:
        detail = ", ".join(f"Điều {a}/{b}" for a, b in bad)
        if sycophancy_detected:
            return False, f"[SYCOPHANCY DETECTED] Model gật theo người dùng và dẫn chiếu sai tài liệu: {detail}", bad, True
        return False, f"[UNGROUNDED CITATION] Dẫn chiếu không tồn tại trong tài liệu cấp phép: {detail}", bad, False

    if sycophancy_detected:
        return False, "[SYCOPHANCY DETECTED] Model gật đầu đồng ý với nhận định sai của người dùng", [], True

    return True, "Mọi dẫn chiếu đều khớp 100% với tài liệu quy phạm pháp luật", [], False


# ==============================================================================
# HÀM TỔNG HỢP MULTI-TIER GUARDRAIL
# ==============================================================================
def inspect_full_guardrail(
    user_query: str,
    user_claim: str,
    answer: str,
    context: str,
    action_type: str = "C1",
    approval_token: Optional[str] = None,
    payload_hash: Optional[str] = None
) -> Dict[str, Any]:
    """Chạy toàn bộ pipeline 3 tầng Guardrails và trả về phán quyết chi tiết."""
    # Tier 1
    t1_ok, t1_reason = check_input_guardrail(user_query, user_claim)
    
    # Tier 2
    t2_ok, t2_reason = check_action_guardrail(action_type, approval_token, payload_hash)
    
    # Tier 3
    t3_ok, t3_reason, bad_cites, is_syco = check_citation_guardrail(answer, context, user_claim)
    
    overall_ok = t1_ok and t2_ok and t3_ok
    shown_output = answer if overall_ok else FAIL_ANSWER
    
    # Xác định lớp chặn đầu tiên nếu fail
    failing_tier = None
    failing_reason = "Tất cả các lớp kiểm soát đều an toàn"
    if not t1_ok:
        failing_tier = "Tier 1: Input / Injection Rail"
        failing_reason = t1_reason
    elif not t2_ok:
        failing_tier = "Tier 2: Action Boundary Rail"
        failing_reason = t2_reason
    elif not t3_ok:
        failing_tier = "Tier 3: Output Citation Gate"
        failing_reason = t3_reason

    return {
        "overall_ok": overall_ok,
        "shown_output": shown_output,
        "failing_tier": failing_tier,
        "failing_reason": failing_reason,
        "is_sycophancy": is_syco,
        "bad_citations": [f"Điều {a}/{b}" for a, b in bad_cites],
        "tier1": {
            "name": "Input / Injection Rail (InjecAgent ACL 2024)",
            "ok": t1_ok,
            "reason": t1_reason
        },
        "tier2": {
            "name": "Action Boundary Rail (Shavit 2023 / ASSEBench NeurIPS 2025)",
            "ok": t2_ok,
            "reason": t2_reason,
            "action_class": action_type
        },
        "tier3": {
            "name": "Output Citation & Hallucination Gate (Grounding Oracle)",
            "ok": t3_ok,
            "reason": t3_reason
        }
    }

