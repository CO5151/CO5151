"""Claim Auditor Agent: Verifies legal claims and detects revoked/superseded statutes.

Acts as an external verification oracle to eliminate hallucinations and citation errors,
producing a structured AuditReport with grounding scores and critique feedback.
Compliant with Google ADK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.agents.base import ADKAgent
from src.core.logger import logger
from src.memory.state_models import AtomicClaim, AuditReport
from src.tools.gazette_tool import VERIFY_VBPL_STATUS_TOOL, verify_vbpl_status
from src.tools.validity_checker import VALIDITY_CHECKER_TOOL

if TYPE_CHECKING:
    from src.memory.sqlite_manager import SQLiteMemoryManager


class ClaimAuditorAgent(ADKAgent):
    """Agent responsible for verification and citation auditing of candidate drafts."""

    def __init__(self, memory_manager: SQLiteMemoryManager | None = None) -> None:
        super().__init__(
            name="ClaimAuditorAgent",
            description="Kiểm định tính xác thực của căn cứ pháp lý, phát hiện các điều khoản/văn bản đã hết hiệu lực.",
            role="verifier",
            tools=[VALIDITY_CHECKER_TOOL, VERIFY_VBPL_STATUS_TOOL],
        )
        self.memory_manager = memory_manager

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes verification audit via standard ADK interface."""
        if isinstance(input_data, list):
            clauses = input_data
            enable_live_vbpl = context.get("enable_live_vbpl", True)
        elif isinstance(input_data, dict):
            clauses = input_data.get("clauses", [])
            enable_live_vbpl = input_data.get(
                "enable_live_vbpl", context.get("enable_live_vbpl", True)
            )
        else:
            clauses = []
            enable_live_vbpl = context.get("enable_live_vbpl", True)
        return self.audit_provisions(clauses, enable_live_vbpl=enable_live_vbpl)

    def audit_provisions(
        self,
        clauses: list[dict[str, Any]],
        enable_live_vbpl: bool = True,
    ) -> AuditReport:
        """Audits retrieved provisions to ensure every cited document is active and valid."""
        logger.info(
            "ClaimAuditorAgent: Auditing %d candidate clauses (enable_live_vbpl=%s)...",
            len(clauses),
            enable_live_vbpl,
        )

        claims: list[AtomicClaim] = []
        unsupported: list[AtomicClaim] = []
        verified_docs: dict[str, dict[str, Any]] = {}

        for idx, clause in enumerate(clauses):
            doc_id = str(clause.get("doc_id", "UNKNOWN"))
            status = str(clause.get("status", "unknown"))
            revoked_by = clause.get("revoked_by")
            article = str(clause.get("article", ""))

            live_info: dict[str, Any] | None = None
            if enable_live_vbpl and doc_id != "UNKNOWN":
                doc_key = doc_id.strip().replace(" ", "").upper().replace("Đ", "D")
                if doc_key not in verified_docs:
                    try:
                        verified_docs[doc_key] = verify_vbpl_status(
                            doc_id, memory_manager=self.memory_manager
                        )
                    except Exception as e:
                        logger.warning(
                            "Live VBPL verification failed for %s (%s). Falling back.", doc_id, e
                        )
                live_info = verified_docs.get(doc_key)
                if live_info:
                    live_status = live_info.get("status", "unknown")
                    if live_status in ("expired", "not_in_force"):
                        status = live_status
                    elif status == "unknown" and live_info.get("is_in_force"):
                        status = "active"
                    if not revoked_by and live_info.get("metadata", {}).get("revoked_by"):
                        revoked_by = live_info["metadata"]["revoked_by"]

            # Check if active
            is_active = (status in ("active", "partially_expired")) and (revoked_by is None)
            content_str = str(clause.get("content") or "")
            is_grounded = is_active and len(content_str) > 10

            note = None
            if not is_active:
                note = f"NGUY CƠ PHÁP LÝ: {doc_id} đã HẾT HIỆU LỰC"
                if revoked_by:
                    note += f" (đã bị bãi bỏ bởi {revoked_by})"
                elif live_info and live_info.get("status") in ("expired", "not_in_force"):
                    src = live_info.get("source", "vbpl.vn")
                    note += f" (xác nhận từ {src})"

            claim = AtomicClaim(
                claim_id=f"claim_{idx + 1:03d}",
                text=f"Căn cứ {doc_id} ({article}): {clause.get('article_title', '')}",
                cited_statute=doc_id,
                cited_article=article,
                is_grounded=is_grounded,
                is_statute_active=is_active,
                auditor_notes=note,
                live_verification=live_info,
            )
            claims.append(claim)

            if not is_grounded:
                unsupported.append(claim)

        total = len(claims)
        grounded = sum(1 for c in claims if c.is_grounded)
        grounding_rate = (grounded / total) if total > 0 else 0.0

        is_fully_verified = len(unsupported) == 0 and total > 0

        feedback = None
        if not is_fully_verified:
            revoked_items = [c.cited_statute for c in unsupported if not c.is_statute_active]
            feedback = (
                f"Phát hiện căn cứ hết hiệu lực: {', '.join(revoked_items)}. "
                "Yêu cầu Orchestrator chuyển hướng tra cứu văn bản thay thế mới nhất."
            )

        report = AuditReport(
            total_claims=total,
            grounded_claims=grounded,
            claims=claims,
            grounding_rate=round(grounding_rate, 4),
            is_fully_verified=is_fully_verified,
            unsupported_claims=unsupported,
            auditor_feedback=feedback,
            live_verifications=list(verified_docs.values()),
        )

        logger.info(
            "ClaimAuditorAgent: Verification complete. Grounding Rate: %.1f%%, "
            "Fully Verified: %s, Verified Docs: %d",
            report.grounding_rate * 100,
            report.is_fully_verified,
            len(report.live_verifications),
        )
        return report
