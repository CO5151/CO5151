"""Drafter Agent: Synthesizes verified compliance dossiers and legal advisories.

Constructs structured legal dossiers grounded strictly in audited statutory provisions,
adhering to administrative formatting and safety guardrail disclaimers. Compliant with Google ADK.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ADKAgent
from src.core.logger import logger
from src.memory.state_models import AuditReport, EnterpriseProfile


class DrafterAgent(ADKAgent):
    """Agent responsible for assembling and formatting final compliance dossiers."""

    LEGAL_DISCLAIMER = (
        "LƯU Ý MIỄN TRỪ TRÁCH NHIỆM PHÁP LÝ:\n"
        "Văn bản này được khởi tạo tự động bởi hệ thống AI hỗ trợ tuân thủ LegalPilot-VN (Theme 9). "
        "Báo cáo chỉ có giá trị tham vấn kỹ thuật tuân thủ hành chính, không thay thế cho ý kiến tư vấn "
        "chính thức của Luật sư được cấp chứng chỉ hành nghề hoặc văn bản hướng dẫn nghiệp vụ của cơ quan có thẩm quyền."
    )

    def __init__(self) -> None:
        super().__init__(
            name="DrafterAgent",
            description="Tổng hợp hồ sơ tư vấn tuân thủ pháp lý dựa trên các điều khoản đã kiểm định kèm miễn trừ trách nhiệm.",
            role="synthesizer",
            tools=[],
        )

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes dossier drafting via standard ADK interface."""
        query = input_data.get("query", "")
        verified_clauses = input_data.get("verified_clauses", [])
        audit_report = input_data.get("audit_report")
        profile = input_data.get("profile")
        return self.synthesize_dossier(query, verified_clauses, audit_report, profile)

    def synthesize_dossier(
        self,
        query: str,
        verified_clauses: list[dict[str, Any]],
        audit_report: AuditReport,
        profile: EnterpriseProfile | None = None,
    ) -> str:
        """Assembles the final verified legal compliance dossier."""
        logger.info("DrafterAgent: Synthesizing final compliance dossier...")

        lines: list[str] = [
            "=" * 78,
            "BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ (LEGAL COMPLIANCE DOSSIER)",
            "=" * 78,
            f"YÊU CẦU TRA CỨU: {query}",
        ]

        if profile:
            capital_str = f"{profile.charter_capital:,.0f} VNĐ" if profile.charter_capital is not None else "Chưa xác định"
            ratio_str = f"{profile.foreign_ownership_ratio * 100:.1f}%" if profile.foreign_ownership_ratio is not None else "0.0%"
            lines.extend(
                [
                    f"DOANH NGHIỆP: {profile.company_name} ({profile.entity_type})",
                    f"VỐN ĐIỀU LỆ HIỆN CÓ: {capital_str}",
                    f"TỶ LỆ SỞ HỮU NƯỚC NGOÀI: {ratio_str}",
                ]
            )

        lines.extend(
            [
                f"TỶ LỆ XÁC THỰC CĂN CỨ (GROUNDING RATE): {audit_report.grounding_rate * 100:.1f}%",
                f"TRẠNG THÁI KIỂM ĐỊNH HIỆU LỰC: {'HỢP LỆ HOÀN TOÀN' if audit_report.is_fully_verified else 'CẦN LƯU Ý'}",
                "-" * 78,
                "1. CĂN CỨ PHÁP LÝ ÁP DỤNG (ĐÃ ĐỐI SOÁT CƠ SỞ DỮ LIỆU VBQPPL):",
            ]
        )

        for idx, clause in enumerate(verified_clauses, start=1):
            lines.append(
                f"  [{idx}] {clause.get('title')} - {clause.get('article')}: {clause.get('article_title', '')}\n"
                f"      Nội dung: {clause.get('content')}\n"
                f"      Hiệu lực thi hành: Từ ngày {clause.get('effective_date')}"
            )

        lines.extend(
            [
                "-" * 78,
                "2. KẾT LUẬN & KHUYẾN NGHỊ THỰC THI:",
                "  - Doanh nghiệp phải tuân thủ nghiêm ngặt các điều kiện quy định tại các văn bản còn hiệu lực trên.",
                "  - Tuyệt đối không áp dụng các văn bản/điều khoản đã bị bãi bỏ theo cảnh báo của Claim Auditor.",
                "-" * 78,
                self.LEGAL_DISCLAIMER,
                "=" * 78,
            ]
        )

        dossier = "\n".join(lines)
        return dossier
