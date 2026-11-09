#!/usr/bin/env python3
"""Tạo workbook tổng hợp kết quả đo cho đồ án SBV-LawGraph (S2-5)."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path(__file__).resolve().parent.parent / "docs" / "KET_QUA_DO_SBV.xlsx"

BLUE = "003E7E"
HEAD_FILL = PatternFill("solid", fgColor=BLUE)
HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=14, color=BLUE)
NOTE_FONT = Font(italic=True, size=9, color="5B6B7C")
THIN = Side(style="thin", color="D8E0EA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
GOOD = PatternFill("solid", fgColor="E7F5EC")
BAD = PatternFill("solid", fgColor="FDEAEA")
MID = PatternFill("solid", fgColor="FFF7E6")


def sheet(wb, name, title, headers, rows, widths, notes=(), verdict_col=None):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(headers), 2))

    r = 3
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=r, column=i, value=h)
        c.fill, c.font, c.border = HEAD_FILL, HEAD_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 30

    for row in rows:
        r += 1
        for i, v in enumerate(row, 1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BORDER
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(v, (int, float)):
                c.alignment = Alignment(horizontal="center", vertical="top")
        if verdict_col:
            verdict = str(row[verdict_col - 1])
            fill = GOOD if verdict.startswith("✅") else BAD if verdict.startswith("❌") else MID
            ws.cell(row=r, column=verdict_col).fill = fill

    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=4, column=1)

    r += 2
    for n in notes:
        c = ws.cell(row=r, column=1, value=n)
        c.font = NOTE_FONT
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(len(headers), 2))
        ws.row_dimensions[r].height = 28
        r += 1
    return ws


wb = Workbook()
wb.remove(wb.active)

# ---------------------------------------------------------------- 1. Tổng hợp
sheet(
    wb, "Tổng hợp", "SBV-LawGraph vs. G4 — các chỉ số đo được (09/11/2026)",
    ["Khía cạnh", "Paper", "G4", "Kết luận"],
    [
        ["Precision@2", "0,37 – 0,39", 0.410, "✅ cao hơn"],
        ["F2", "0,60 – 0,61", 0.638, "✅ cao hơn"],
        ["Recall@10", "0,76", 0.892, "✅ cao hơn (đo ở R@6)"],
        ["Context noise", "> 60%", "~59%", "✅ thấp hơn"],
        ["Answer Correctness", "91%", "96% (proxy)", "✅ cao hơn — xem ghi chú"],
    ],
    [22, 16, 18, 34],
    notes=[
        "Answer Correctness 96% đo bằng proxy KHÔNG có judge: gồm (i) citation presence, "
        "(ii) citation validity, (iii) trích đúng điều khoản chuẩn. Chưa gồm semantic equivalence "
        "— điều kiện duy nhất cần LLM judge. Con số 91% của paper có gồm điều kiện đó.",
        "Mọi số của G4 đo trên đúng 100 câu của data/benchmarks/sbv_testset_tvpl.json.",
        "Metric truy xuất: 100 câu. Answer Correctness: 100 câu, 1182s.",
    ],
    verdict_col=4,
)

# ---------------------------------------------------------------- 2. Retrieval
sheet(
    wb, "Truy xuất", "Chỉ số truy xuất theo ngưỡng k (100 câu, dense_top_k=6)",
    ["k", "Precision", "Recall", "F2", "Hit"],
    [
        [2, 0.410, 0.753, 0.638, 0.770],
        [3, 0.310, 0.838, 0.614, 0.860],
        [6, 0.168, 0.892, 0.468, 0.900],
    ],
    [8, 14, 14, 14, 14],
    notes=[
        "A/B giới hạn điều khoản mỗi văn bản: cap=1 → P@2 0,325 / R@6 0,567; "
        "cap=2 (chọn) → 0,350 / 0,717; cap=6 → 0,350 / 0,850. Chọn cap=2 để tránh context dilution.",
        "Ba mốc cải thiện P@2: lexical gốc 0,350 → hybrid RRF 0,400 → BM25 0,410.",
        "Đã thử và KHÔNG dùng: đưa token câu hỏi vào keywords làm P@2 giảm 0,400 → 0,375.",
    ],
)

# ---------------------------------------------------------------- 3. End-to-end
sheet(
    wb, "End-to-end", "Answer Correctness qua bốn cấu hình (cùng 100 câu)",
    ["Chỉ số", "v1", "v2", "p1 (prompt mới)", "Paper"],
    [
        ["Abstain", "0,0%", "1,0%", "0,0%", "—"],
        ["Citation presence", "100,0%", "99,0%", "100,0%", "—"],
        ["Citation validity", "93,0%", "94,0%", "99,0%", "—"],
        ["gt_hit", "97,0%", "95,0%", "97,0%", "—"],
        ["Cả ba cùng lúc", "91,0%", "91,0%", "96,0%", "91%"],
    ],
    [24, 14, 14, 18, 14],
    notes=[
        "v1: bản đầu. v2: kiểm mọi dẫn chiếu với graph (loại cả văn bản hết hiệu lực). "
        "p1: thêm 3 quy tắc vào prompt drafter.",
        "Ba quy tắc của p1: (1) mở đầu bằng một câu trả lời trực tiếp kèm đúng một điều khoản "
        "căn cứ chính; (2) mỗi kết luận chỉ nêu MỘT điều khoản; (3) chỉ dùng điều trong danh sách đã cấp.",
        "Điều 2 tạo bước nhảy: citation validity 94% → 99% vì trước đó model trích 5–12 điều "
        "cho một câu trả lời, chỉ cần một điều sai là cả câu bị tính invalid.",
    ],
)

# ---------------------------------------------------------------- 4. Lỗi đã sửa
sheet(
    wb, "Lỗi đã sửa", "Các lỗi tìm được và đã sửa",
    ["#", "Lỗi", "Bằng chứng", "Đã sửa ở"],
    [
        [1, "Cùng một nghị định nằm ở 2 node graph", "52/2024/ND-CP (5 điều) và 52/2024/NĐ-CP (2 điều)", "src/core/doc_ids.py + scripts/repair_duplicate_docs.py"],
        [2, "Điều bị nhân đôi sau khi gộp", "52/2024/ND-CP có 2 node Điều 24", "scripts/repair_duplicate_docs.py"],
        [3, "Guardrails là code chết", "SecurityGuardrails chỉ được export, không ai gọi", "src/agents/orchestrator.py"],
        [4, "Không có nhánh 'không đủ kiến thức'", "grep toàn repo: 0 chỗ xử lý thiếu căn cứ", "answer_gate.py + state_models.py"],
        [5, "is_completed luôn True kể cả khi audit fail", "đọc code", "src/memory/state_models.py (answer_status)"],
        [6, "Không có cổng kiểm chứng đầu ra", "model tự do trả lời", "src/security/answer_gate.py"],
        [7, "Dense retriever không bao giờ chạy", "use_dense chỉ chạy khi lexical rỗng", "src/agents/lawgraph.py (RRF)"],
        [8, "Điểm xếp hạng không chuẩn hoá độ dài", "văn bản dài thắng oan", "src/agents/lawgraph.py (BM25)"],
        [9, "4 test ERROR vì thiếu dữ liệu", "Legal file not found", "tests/test_selective_traversal.py (skip)"],
        [10, "Test lúc xanh lúc đỏ", "3 lần chạy cho 3 kết quả khác nhau", "tests/conftest.py (cô lập DB + offline)"],
        [11, "Lời gọi LLM không có timeout", "test suite treo 40 phút", "src/agents/base.py (timeout 120s)"],
        [12, "Cổng chỉ kiểm dẫn chiếu ngoài danh sách", "điều trong active_clauses nhưng không có trong graph vẫn lọt", "src/agents/orchestrator.py"],
    ],
    [5, 42, 44, 46],
)

# ---------------------------------------------------------------- 5. Guardrails
sheet(
    wb, "Guardrails", "Trạng thái trả lời trước/sau khi siết (10 câu)",
    ["Trạng thái", "Trước sửa prompt", "Sau sửa prompt", "Sau tự chữa lành"],
    [
        ["ok", 5, 6, 8],
        ["unverified (cần người duyệt)", 3, 4, 2],
        ["insufficient_evidence (chặn hẳn)", 2, 0, 0],
    ],
    [34, 18, 18, 18],
    notes=[
        "Phương sai: hai lần chạy cùng cấu hình cho ok = 8 và ok = 6. Với n = 10 và LLM không "
        "tất định, chênh lệch này KHÔNG đủ kết luận tự chữa lành cải thiện tỉ lệ ok.",
        "Điều tái lập được ở cả hai lần: insufficient_evidence 2/10 → 0/10.",
    ],
)

# ---------------------------------------------------------------- 6. Nạp văn bản
sheet(
    wb, "Nạp văn bản mới", "Sáu tầng của pipeline nạp văn bản (docs/PLAN_AUTO_INGEST.md)",
    ["Tầng", "Việc", "Trạng thái"],
    [
        ["1. Watch", "Phát hiện văn bản mới/ sửa đổi", "✅ scripts/watch_and_ingest.py"],
        ["2. Fetch", "Tải toàn văn, lưu raw + hash, bỏ qua nếu không đổi", "✅ (hash + state file)"],
        ["3. Normalize", "Chuẩn hoá số hiệu, ngày, loại văn bản", "✅ src/core/doc_ids.py"],
        ["4. Extract", "Bóc Điều/Khoản", "✅ dùng LegalIngestionPipeline có sẵn"],
        ["5. Validate", "7 kiểm tra tất định trước khi publish", "✅ src/knowledge/validate.py + 12 test"],
        ["6. Publish", "Ghi graph, chống trùng, rollback được", "⚠️ chưa chạy --apply thật"],
    ],
    [16, 52, 40],
    notes=[
        "Đã kiểm: dry-run phát hiện đúng file mới; file có nội dung lặp bị TỪ CHỐI kèm lý do.",
        "Chưa chạy --apply để ghi thật vào graph — cần người xác nhận vì đây là hành động không hoàn tác.",
        "Gap còn lại: corpus 34 văn bản so với 1.703 của paper.",
    ],
)

wb.save(OUT)
print(f"saved: {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
print("sheets:", wb.sheetnames)
