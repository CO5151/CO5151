"""Drafter Agent: Synthesizes verified compliance dossiers and legal advisories.

Constructs structured legal dossiers grounded strictly in audited statutory provisions,
adhering to administrative formatting and safety guardrail disclaimers. Compliant with Google ADK.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from src.agents.base import ADKAgent
from src.core.logger import logger
from src.prompts import LEGAL_DISCLAIMER

if TYPE_CHECKING:
    from src.memory.state_models import AuditReport, EnterpriseProfile

# Benchmark-only answer-length contract. When BENCH_CONCISE=1 the dossier is
# trimmed to the same budget the other three architectures are held to, so the
# comparison is not distorted by template length.
_CONCISE = bool(os.getenv("BENCH_CONCISE"))


class DrafterAgent(ADKAgent):
    """Agent responsible for assembling and formatting final compliance dossiers."""

    LEGAL_DISCLAIMER = LEGAL_DISCLAIMER

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
        verified_clauses = input_data.get("verified_clauses") or input_data.get("clauses", [])
        audit_report = input_data.get("audit_report")
        profile = input_data.get("profile")
        critique_feedback = input_data.get("critique_feedback")
        return self.synthesize_dossier(
            query,
            verified_clauses,
            audit_report,
            profile,
            critique_feedback=critique_feedback,
        )

    def synthesize_dossier(
        self,
        query: str,
        verified_clauses: list[dict[str, Any]],
        audit_report: AuditReport | None = None,
        profile: EnterpriseProfile | None = None,
        critique_feedback: str | None = None,
    ) -> str:
        """Assembles the final verified legal compliance dossier or provisional candidate draft."""
        logger.info(
            "DrafterAgent: Synthesizing compliance dossier (has_critique=%s)...",
            bool(critique_feedback),
        )

        lines: list[str] = [
            "=" * 78,
            "BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ (LEGAL COMPLIANCE DOSSIER)",
            "=" * 78,
            f"YÊU CẦU TRA CỨU: {query}",
        ]

        if profile:
            capital_str = (
                f"{profile.charter_capital:,.0f} VNĐ"
                if profile.charter_capital is not None
                else "Chưa xác định"
            )
            ratio_str = (
                f"{profile.foreign_ownership_ratio * 100:.1f}%"
                if profile.foreign_ownership_ratio is not None
                else "0.0%"
            )
            lines.extend(
                [
                    f"DOANH NGHIỆP: {profile.company_name} ({profile.entity_type})",
                    f"VỐN ĐIỀU LỆ HIỆN CÓ: {capital_str}",
                    f"TỶ LỆ SỞ HỮU NƯỚC NGOÀI: {ratio_str}",
                ]
            )

        grounding_str = (
            f"{audit_report.grounding_rate * 100:.1f}%"
            if audit_report is not None
            else "CHỜ KIỂM ĐỊNH (BẢN THẢO)"
        )
        status_str = (
            ("HỢP LỆ HOÀN TOÀN" if audit_report.is_fully_verified else "CẦN LƯU Ý")
            if audit_report is not None
            else "ĐANG ĐỐI SOÁT"
        )
        lines.extend(
            [
                f"TỶ LỆ XÁC THỰC CĂN CỨ (GROUNDING RATE): {grounding_str}",
                f"TRẠNG THÁI KIỂM ĐỊNH HIỆU LỰC: {status_str}",
                "-" * 78,
                "1. CĂN CỨ PHÁP LÝ ÁP DỤNG (ĐÃ ĐỐI SOÁT CƠ SỞ DỮ LIỆU VBQPPL):",
            ]
        )

        for idx, clause in enumerate(verified_clauses, start=1):
            content = str(clause.get("content") or "")
            if _CONCISE and len(content) > 400:
                content = content[:400].rstrip() + "..."
            lines.append(
                f"  [{idx}] {clause.get('title')} [{clause.get('doc_id')}] - {clause.get('article')}: {clause.get('article_title', '')}\n"
                f"      Nội dung: {content}\n"
                f"      Hiệu lực thi hành: Từ ngày {clause.get('effective_date')}"
            )

        llm_conclusion = ""
        if verified_clauses:
            try:
                from src.agents.base import GoogleAgent, get_default_model, invoke_adk_agent

                ctx = "\n".join(
                    [
                        f"- {c.get('title')} {c.get('article')}: {c.get('content')}"
                        for c in verified_clauses
                    ]
                )
                p_info = (
                    f"Doanh nghiệp: {profile.company_name}, Vốn hiện có: {profile.charter_capital:,.0f} VNĐ"
                    if profile and profile.charter_capital
                    else ""
                )
                drafter_adk = GoogleAgent(
                    name="LegalDrafterWorker",
                    model=get_default_model(),
                    instruction="Bạn là chuyên gia tư vấn tuân thủ pháp luật doanh nghiệp Việt Nam. Hãy đưa ra kết luận và khuyến nghị thực thi chuẩn xác, chuyên nghiệp dựa trên các điều khoản đã được đối soát.",
                )
                prompt = (
                    f"Dựa trên câu hỏi tra cứu:\n'{query}'\n"
                    f"và các căn cứ pháp lý đã được thẩm định còn hiệu lực:\n{ctx}\n"
                    f"{p_info}\n"
                    "Hãy đưa ra phần KẾT LUẬN & KHUYẾN NGHỊ THỰC THI (ngắn gọn, chính xác số liệu, chỉ rõ doanh nghiệp cần làm gì)."
                )
                if critique_feedback:
                    prompt += f"\nLƯU Ý PHẢN HỒI TỪ AUDITOR (CẦN SỬA ĐỔI / KHẮC PHỤC):\n{critique_feedback}\n"
                if _CONCISE:
                    prompt += (
                        "\nTRẢ LỜI NGẮN GỌN: tối đa 150 từ. Đi thẳng vào câu trả lời, "
                        "KHÔNG lặp lại câu hỏi, KHÔNG mục lục, KHÔNG dẫn nhập, "
                        "KHÔNG tuyên bố miễn trừ trách nhiệm."
                    )
                llm_conclusion = invoke_adk_agent(drafter_adk, prompt).strip()
            except Exception as e:
                logger.warning("Google ADK Drafter conclusion failed: %s", e)

        conclusion_lines = [
            "-" * 78,
            "2. KẾT LUẬN & KHUYẾN NGHỊ THỰC THI:",
        ]
        if llm_conclusion:
            conclusion_lines.append(llm_conclusion)
        else:
            conclusion_lines.extend(
                [
                    "  - Doanh nghiệp phải tuân thủ nghiêm ngặt các điều kiện quy định tại các văn bản còn hiệu lực trên.",
                    "  - Tuyệt đối không áp dụng các văn bản/điều khoản đã bị bãi bỏ theo cảnh báo của Claim Auditor.",
                ]
            )
        conclusion_lines.extend(
            [
                "-" * 78,
                self.LEGAL_DISCLAIMER,
                "=" * 78,
            ]
        )
        if _CONCISE:
            conclusion_lines = [
                "-" * 78,
                "2. KẾT LUẬN & KHUYẾN NGHỊ THỰC THI:",
                llm_conclusion or "  - Không đủ căn cứ để trả lời.",
            ]
        lines.extend(conclusion_lines)

        dossier = "\n".join(lines)
        return dossier
