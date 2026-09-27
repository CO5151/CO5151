#!/usr/bin/env python3
"""
CO5151 -- Advanced Agentic AI | Nhóm G4
SEMINAR S1-7: AGENT DESIGN PATTERNS & ORCHESTRATION
Mã nguồn Trace Demo: So sánh 3 mẫu thiết kế điều phối trên tình huống Pháp lý thực tế

Kịch bản: Doanh nghiệp có vốn đầu tư nước ngoài xin cấp phép dịch vụ Ví điện tử (Tháng 10/2024).
Thách thức: Nghị định 101/2012/NĐ-CP đã bị bãi bỏ hoàn toàn bởi Nghị định 52/2024/NĐ-CP từ 01/07/2024.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# ANSI Colors for Rich Console Output
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
DIM = "\033[2m"

@dataclass
class ExecutionMetrics:
    total_tokens: int = 0
    wall_clock_ms: float = 0.0
    turns: int = 0
    errors_caught: int = 0
    status: str = "PENDING"

@dataclass
class AgentState:
    query: str
    active_subgoals: List[str] = field(default_factory=list)
    extracted_clauses: Dict[str, Any] = field(default_factory=dict)
    audit_findings: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    final_output: Optional[str] = None

# =====================================================================
# SIMULATED TOOLS (MCP SERVERS)
# =====================================================================
def tool_vbpl_verify_status(doc_id: str) -> Dict[str, Any]:
    """MCP Tool: Tra cứu trạng thái hiệu lực thời gian thực trên Cổng vbpl.vn"""
    time.sleep(0.08)  # simulate API latency
    if "101/2012" in doc_id:
        return {
            "doc_id": "101/2012/ND-CP",
            "status": "HẾT HIỆU LỰC TOÀN BỘ",
            "revoked_by": "52/2024/ND-CP",
            "effective_date_end": "01/07/2024",
            "is_valid": False
        }
    elif "52/2024" in doc_id:
        return {
            "doc_id": "52/2024/ND-CP",
            "status": "CÒN HIỆU LỰC",
            "effective_date_start": "01/07/2024",
            "capital_requirement_vnd": 50_000_000_000,
            "is_valid": True
        }
    return {"doc_id": doc_id, "status": "UNKNOWN", "is_valid": False}


# =====================================================================
# PATTERN 1: NAIVE CHAINING (Tuyến tính - Không có kiểm tra)
# =====================================================================
def run_pattern_naive_chaining(query: str) -> ExecutionMetrics:
    print(f"\n{BOLD}{CYAN}=== [PATTERN 1] NAIVE PROMPT CHAINING ==={RESET}")
    start = time.time()
    metrics = ExecutionMetrics()

    print(f"  {DIM}[Step 1] Router phân tích intent: 'Cấp phép ví điện tử'{RESET}")
    metrics.total_tokens += 180
    metrics.turns += 1

    print(f"  {DIM}[Step 2] Extraction Worker: Trích xuất điều kiện vốn từ vector DB...{RESET}")
    # Naive extraction hits old popular chunk ND 101/2012
    extracted = "Nghị định 101/2012/NĐ-CP quy định vốn tối thiểu 50 tỷ đồng."
    metrics.total_tokens += 350
    metrics.turns += 1

    print(f"  {DIM}[Step 3] Response Generator: Xuất báo cáo hồ sơ pháp lý...{RESET}")
    metrics.total_tokens += 220
    metrics.turns += 1

    metrics.wall_clock_ms = (time.time() - start) * 1000
    metrics.status = f"{RED}FAILED (Viện dẫn luật bãi bỏ - Fatal Semantic Error){RESET}"

    print(f"  {RED}✖ Hậu quả:{RESET} Hệ thống tư vấn dẫn chiếu NĐ 101/2012 (đã bãi bỏ). Hồ sơ nộp NHNN sẽ bị trả về ngay lập tức!")
    return metrics


# =====================================================================
# PATTERN 2: CHATTY MULTI-AGENT SWARM (AutoGen Style - Tự do tranh luận)
# =====================================================================
def run_pattern_chatty_swarm(query: str) -> ExecutionMetrics:
    print(f"\n{BOLD}{MAGENTA}=== [PATTERN 2] CHATTY MULTI-AGENT SWARM (FREE CHAT) ==={RESET}")
    start = time.time()
    metrics = ExecutionMetrics()

    print(f"  {DIM}[Agent Drafter]: Tôi đề xuất căn cứ NĐ 101/2012 vì có 10 năm tiền lệ áp dụng.{RESET}")
    metrics.total_tokens += 1200
    metrics.turns += 1

    print(f"  {DIM}[Agent Auditor]: Tôi thấy tài liệu 2024 có nhắc tới NĐ 52, bạn nghĩ sao?{RESET}")
    metrics.total_tokens += 1800
    metrics.turns += 1

    print(f"  {DIM}[Agent Drafter]: NĐ 101 phổ biến hơn trong dữ liệu mẫu, NĐ 52 chỉ là sửa đổi nhỏ.{RESET}")
    metrics.total_tokens += 2400
    metrics.turns += 1

    # Sycophancy trap occurs
    print(f"  {YELLOW}⚠ [Agent Auditor - Sycophancy Trap]: Đồng ý với Drafter, ta giữ nguyên NĐ 101 để tránh rủi ro thay đổi schema.{RESET}")
    metrics.total_tokens += 3200
    metrics.turns += 1
    metrics.errors_caught = 0

    metrics.wall_clock_ms = (time.time() - start) * 1000 + 450
    metrics.status = f"{YELLOW}DEGRADED (Sycophancy Trap + Token Explosion){RESET}"

    print(f"  {YELLOW}✖ Hậu quả:{RESET} Tốn 8.600+ tokens nhưng hai agent tự thỏa hiệp sai lầm do thiếu Ground-truth tool!")
    return metrics


# =====================================================================
# PATTERN 3: GRAPH-STATE ORCHESTRATOR (LangGraph + MCP Tool Loop)
# =====================================================================
def run_pattern_state_graph(query: str) -> ExecutionMetrics:
    print(f"\n{BOLD}{GREEN}=== [PATTERN 3] CONTROLLED GRAPH-STATE MACHINE (G4 ARCHITECTURE) ==={RESET}")
    start = time.time()
    state = AgentState(query=query)
    metrics = ExecutionMetrics()

    print(f"  {CYAN}[Node: Orchestrator / Planner]{RESET} Tiếp nhận hồ sơ $\\to$ Phân rã 2 Sub-goals:")
    print(f"    Sub-goal 1: Điều kiện Vốn tối thiểu")
    print(f"    Sub-goal 2: Tỷ lệ sở hữu nước ngoài (Room ngoại)")
    metrics.total_tokens += 420
    metrics.turns += 1

    # Loop 1: Draft worker fetches candidate
    print(f"\n  {BLUE}[Node: Drafter Worker]{RESET} Truy xuất candidate cho Sub-goal 1...")
    state.extracted_clauses["doc_id"] = "101/2012/ND-CP"
    print(f"    -> Đề xuất: Nghị định 101/2012/NĐ-CP (Vốn 50 tỷ)")
    metrics.total_tokens += 380
    metrics.turns += 1

    # Auditor calls Ground-truth MCP Tool
    print(f"\n  {MAGENTA}[Node: Claim Auditor (Context B Isolated)]{RESET} Đối soát với nguồn tin cậy...")
    print(f"    -> Gọi MCP Tool: {BOLD}vbpl_verify_status('101/2012/ND-CP'){RESET}")
    tool_res = tool_vbpl_verify_status("101/2012/ND-CP")
    
    if not tool_res["is_valid"]:
        metrics.errors_caught += 1
        print(f"    {RED}✖ PHÁT HIỆN LỖI PHÁP LÝ NGHIÊM TRỌNG:{RESET} {tool_res['doc_id']} đã bị {tool_res['revoked_by']} bãi bỏ!")
        print(f"    -> Kích hoạt {BOLD}Re-route Edge{RESET} (Vòng lặp sửa sai {state.retry_count + 1}/{state.max_retries})...")
        state.retry_count += 1
        metrics.total_tokens += 410
        metrics.turns += 1

    # Loop 2: Recovery Re-plan
    print(f"\n  {CYAN}[Node: Orchestrator Re-route]{RESET} Thay thế nguồn tri thức bằng NĐ 52/2024/NĐ-CP...")
    state.extracted_clauses["doc_id"] = "52/2024/ND-CP"
    metrics.total_tokens += 320
    metrics.turns += 1

    # Re-verify
    print(f"  {MAGENTA}[Node: Claim Auditor]{RESET} Kiểm định lại với MCP Tool: {BOLD}vbpl_verify_status('52/2024/ND-CP'){RESET}")
    tool_res_2 = tool_vbpl_verify_status("52/2024/ND-CP")
    if tool_res_2["is_valid"]:
        print(f"    {GREEN}✔ XÁC THỰC THÀNH CÔNG:{RESET} NĐ 52/2024/NĐ-CP Đang có hiệu lực! Vốn: 50.000.000.000 VNĐ.")
        metrics.total_tokens += 280
        metrics.turns += 1

    print(f"\n  {GREEN}[Node: Dossier Synthesizer]{RESET} Xuất hồ sơ tuân thủ đã kiểm chứng 100% căn cứ pháp lý.")
    metrics.total_tokens += 350
    metrics.turns += 1
    metrics.wall_clock_ms = (time.time() - start) * 1000
    metrics.status = f"{GREEN}SUCCESS (100% Grounded & Audited){RESET}"

    return metrics


# =====================================================================
# MAIN BENCHMARK REPORT
# =====================================================================
def main():
    query = "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024"
    print(f"{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}CO5151 SEMINAR S1-7 -- ORCHESTRATION TRACE BENCHMARK DEMO{RESET}")
    print(f"Truy vấn thử nghiệm: {CYAN}\"{query}\"{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")

    m1 = run_pattern_naive_chaining(query)
    m2 = run_pattern_chatty_swarm(query)
    m3 = run_pattern_state_graph(query)

    print(f"\n\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}{'BẢNG TỔNG HỢP SO SÁNH TRACE METRICS GIỮA CÁC PATTERNS':^80}{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    print(f"{'Tiêu Chí Đo Lường':<26} | {'1. Naive Chain':<20} | {'2. Chatty Swarm':<20} | {'3. StateGraph (G4)':<20}")
    print(f"{'-'*26}-+-{'-'*20}-+-{'-'*20}-+-{'-'*20}")
    print(f"{'Độ chính xác pháp lý':<26} | {RED+'0% (Dẫn luật bãi bỏ)'+RESET:<29} | {YELLOW+'15% (Sycophancy)'+RESET:<29} | {GREEN+'100% (Grounded)'+RESET:<29}")
    print(f"{'Tổng Token tiêu thụ':<26} | {str(m1.total_tokens)+' tokens':<20} | {str(m2.total_tokens)+' tokens':<20} | {str(m3.total_tokens)+' tokens':<20}")
    print(f"{'Số bước thực thi':<26} | {str(m1.turns)+' turns':<20} | {str(m2.turns)+' turns':<20} | {str(m3.turns)+' turns':<20}")
    print(f"{'Số lỗi chặn đứng (Caught)':<26} | {str(m1.errors_caught):<20} | {str(m2.errors_caught):<20} | {GREEN+str(m3.errors_caught)+' fatal error'+RESET:<29}")
    print(f"{'Cơ chế Circuit Breaker':<26} | {'Không hỗ trợ':<20} | {'Không (Dễ vô tận)':<20} | {GREEN+'Max 2 retries (FSM)'+RESET:<29}")
    print(f"{BOLD}{'='*80}{RESET}\n")

if __name__ == "__main__":
    main()
