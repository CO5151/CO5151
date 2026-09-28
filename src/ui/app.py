"""LegalPilot-VN: Autonomous Multi-Agent Legal Compliance Web Interface.

Interactive Streamlit interface connected directly to the Google ADK Multi-Agent Pipeline:
LegalOrchestrator -> LawGraphAgent -> ClaimAuditorAgent -> DrafterAgent
"""

from __future__ import annotations

import streamlit as st

from src.agents.orchestrator import LegalOrchestrator
from src.memory.state_models import EnterpriseProfile

st.set_page_config(
    page_title="LegalPilot-VN | Google ADK Multi-Agent Legal Compliance",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ LegalPilot-VN (Theme 9)")
st.caption(
    "Google ADK Multi-Agent System: Subgoal Planning ➔ LawGraph Retrieval ➔ Claim Auditor Oracle ➔ Re-Routing ➔ Verifiable Compliance Dossier"
)

# ------------------------------------------------------------------------------
# Sidebar: Enterprise Profile & Agent Options
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("🏢 Hồ sơ Doanh nghiệp (Enterprise Profile)")
    company_name = st.text_input("Tên doanh nghiệp", value="Fintech Global Payment Co., Ltd (FDI)")
    entity_type = st.selectbox(
        "Loại hình doanh nghiệp",
        [
            "Doanh nghiệp FDI",
            "Công ty Cổ phần (JSC)",
            "Công ty TNHH (LLC)",
            "Tổ chức tín dụng / Fintech",
        ],
    )
    capital = st.number_input(
        "Vốn điều lệ (VNĐ)", value=35_000_000_000, step=5_000_000_000, format="%d"
    )
    headcount = st.number_input("Số lượng lao động", value=45, step=5)
    foreign_ratio = st.slider(
        "Tỷ lệ sở hữu nước ngoài", min_value=0.0, max_value=1.0, value=0.45, step=0.05
    )

    st.divider()
    st.header("⚙️ Cấu hình Tác tử (ADK Config)")
    enable_traversal = st.checkbox("Selective Edge Traversal (Lọc đồ thị)", value=True)
    enable_auditor = st.checkbox(
        "Claim Auditor Oracle (Kiểm định văn bản hết hiệu lực)", value=True
    )
    enable_reroute = st.checkbox("Automated Re-routing Loop (Tự động chuyển hướng)", value=True)

    st.divider()
    st.subheader("💡 Kịch bản kiểm thử nhanh")
    if st.button("Kịch bản 1: Cấp phép Ví điện tử FDI", use_container_width=True):
        st.session_state["query_input"] = (
            "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024"
        )
    if st.button("Kịch bản 2: Phạt vượt đèn đỏ xe máy", use_container_width=True):
        st.session_state["query_input"] = "Mức phạt vượt đèn đỏ xe máy theo quy định mới nhất"
    if st.button("Kịch bản 3: Giấy phép chuyên gia ngoại", use_container_width=True):
        st.session_state["query_input"] = (
            "Điều kiện xin cấp giấy phép lao động cho chuyên gia nước ngoài"
        )

# ------------------------------------------------------------------------------
# Main Query Input
# ------------------------------------------------------------------------------
default_query = st.session_state.get(
    "query_input",
    "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024",
)

query = st.text_area(
    "Nhập câu hỏi hoặc tình huống pháp lý cần tư vấn tuân thủ:",
    value=default_query,
    height=100,
)

col_run, col_clear = st.columns([1, 6])
with col_run:
    run_btn = st.button("🚀 Chạy kiểm định đa tác tử", type="primary", use_container_width=True)

if run_btn and query:
    profile = EnterpriseProfile(
        company_name=company_name,
        entity_type=entity_type,
        charter_capital=float(capital),
        sector_code="6419",
        headcount=int(headcount),
        foreign_ownership_ratio=foreign_ratio,
    )

    with st.spinner(
        "Đang điều phối các Tác tử Google ADK (Planning ➔ LawGraph ➔ Claim Auditor ➔ Re-Routing ➔ Drafter)..."
    ):
        orchestrator = LegalOrchestrator()
        state = orchestrator.run(query=query, enterprise_profile=profile)

    # --------------------------------------------------------------------------
    # Metrics Row
    # --------------------------------------------------------------------------
    st.success("✅ Quy trình thẩm định hoàn tất!")
    audit_report = state.audit_report
    grounding_rate_val = audit_report.grounding_rate if audit_report else 0.0
    is_fully_verified = audit_report.is_fully_verified if audit_report else False

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="Grounding Rate (Xác thực)",
            value=f"{grounding_rate_val * 100:.1f}%",
            delta="100% Active" if is_fully_verified else "Cảnh báo",
        )
    with m2:
        st.metric(
            label="Trạng thái kiểm định",
            value="HỢP LỆ HOÀN TOÀN" if is_fully_verified else "CẦN LƯU Ý",
        )
    with m3:
        st.metric(
            label="Chuyển hướng (Re-route)",
            value=f"{state.retry_count} lần" if state.retry_count > 0 else "Không",
            delta="Đã loại bỏ luật bãi bỏ" if state.retry_count > 0 else "Chuẩn",
        )
    with m4:
        st.metric(
            label="Mã phiên (Session ID)",
            value=state.session_id,
        )

    # --------------------------------------------------------------------------
    # Result Tabs
    # --------------------------------------------------------------------------
    tab_dossier, tab_trace, tab_clauses = st.tabs(
        [
            "📋 Hồ sơ Tư vấn Tuân thủ (Compliance Dossier)",
            "🔍 Nhật ký Điều phối Đa tác tử (Agent Trace)",
            "⚖️ Danh mục Căn cứ & Hiệu lực (Statute Matrix)",
        ]
    )

    with tab_dossier:
        st.markdown(f"```text\n{state.final_compliance_dossier}\n```")

    with tab_trace:
        st.subheader("Nhật ký chi tiết các bước thực thi của Google ADK:")

        st.markdown("#### 1. Planning Worker (LegalOrchestrator)")
        for step in state.plan_steps:
            st.write(f"- {step}")

        st.markdown("#### 2. Retrieval Worker (LawGraphAgent)")
        st.write(
            f"Đã tìm thấy **{len(state.retrieved_clauses)}** điều khoản pháp luật quy phạm phù hợp."
        )

        st.markdown("#### 3. Verification Oracle (ClaimAuditorAgent)")
        if audit_report:
            st.write(f"- **Tổng số luận điểm:** {audit_report.total_claims}")
            st.write(f"- **Số luận điểm hợp lệ:** {audit_report.grounded_claims}")
            feedback = audit_report.auditor_feedback or audit_report.critique_feedback
            if feedback:
                st.warning(f"**Cảnh báo của Auditor:** {feedback}")
            else:
                st.info("Tất cả các căn cứ đều còn hiệu lực thi hành và có nội dung xác thực.")
        else:
            st.info("Chưa có báo cáo thẩm định từ Auditor.")

        if state.retry_count > 0:
            st.markdown("#### 4. Re-routing Loop (Tự động khắc phục lỗi)")
            st.write(
                "Tác tử đã phát hiện văn bản bãi bỏ, kích hoạt nhánh Re-route, loại bỏ căn cứ lỗi và hoàn thiện hồ sơ với các văn bản mới nhất."
            )

    with tab_clauses:
        st.subheader("Bảng căn cứ pháp lý đã qua kiểm duyệt:")
        clause_data = []
        for c in state.retrieved_clauses:
            clause_data.append(
                {
                    "Số hiệu VB": c.get("doc_id"),
                    "Tên văn bản": c.get("title"),
                    "Điều khoản": c.get("article"),
                    "Trạng thái": c.get("status"),
                    "Ngày hiệu lực": c.get("effective_date"),
                }
            )
        st.dataframe(clause_data, use_container_width=True)

st.divider()
st.caption(
    "LegalPilot-VN | Nhóm G4 - CO5151 Advanced Agentic AI | Google ADK Architecture | ĐH Bách Khoa TP.HCM (HCMUT)"
)
