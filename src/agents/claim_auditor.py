"""Claim Auditor Agent: Verifies legal claims and detects revoked/superseded statutes.

Acts as an external verification oracle to eliminate hallucinations and citation errors,
producing a structured AuditReport with grounding scores and critique feedback.
Compliant with Google ADK.
"""

from __future__ import annotations

from typing import Any

from src.agents.base import ADKAgent
from src.core.logger import logger
from src.memory.sqlite_manager import SQLiteMemoryManager
from src.memory.state_models import AtomicClaim, AuditReport


class ClaimAuditorAgent(ADKAgent):
    """Agent responsible for verification and citation auditing of candidate drafts."""

    def __init__(self, memory_manager: SQLiteMemoryManager | None = None) -> None:
        from src.tools.validity_checker import VALIDITY_CHECKER_TOOL

        super().__init__(
            name="ClaimAuditorAgent",
            description="Kiểm định tính xác thực của căn cứ pháp lý, phát hiện các điều khoản/văn bản đã hết hiệu lực.",
            role="verifier",
            tools=[VALIDITY_CHECKER_TOOL],
        )
        self.memory_manager = memory_manager

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes verification audit via standard ADK interface."""
        if isinstance(input_data, list):
            clauses = input_data
        elif isinstance(input_data, dict):
            clauses = input_data.get("clauses", [])
        else:
            clauses = []
        return self.audit_provisions(clauses)

    def audit_provisions(self, clauses: list[dict[str, Any]]) -> AuditReport:
        """Audits retrieved provisions to ensure every cited document is active and valid."""
        logger.info(f"ClaimAuditorAgent: Auditing {len(clauses)} candidate clauses...")

        claims: list[AtomicClaim] = []
        unsupported: list[AtomicClaim] = []

        for idx, clause in enumerate(clauses):
            doc_id = clause.get("doc_id", "UNKNOWN")
            status = clause.get("status", "unknown")
            revoked_by = clause.get("revoked_by")
            article = clause.get("article", "")

            # Check if active
            is_active = (status == "active") and (revoked_by is None)
            content_str = str(clause.get("content") or "")
            is_grounded = is_active and len(content_str) > 10

            note = None
            if not is_active:
                note = f"NGUY CƠ PHÁP LÝ: {doc_id} đã HẾT HIỆU LỰC"
                if revoked_by:
                    note += f" (đã bị bãi bỏ bởi {revoked_by})"

            claim = AtomicClaim(
                claim_id=f"claim_{idx+1:03d}",
                text=f"Căn cứ {doc_id} ({article}): {clause.get('article_title', '')}",
                cited_statute=doc_id,
                cited_article=article,
                is_grounded=is_grounded,
                is_statute_active=is_active,
                auditor_notes=note,
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
            grounding_rate=round(grounding_rate, 4),
            is_fully_verified=is_fully_verified,
            unsupported_claims=unsupported,
            auditor_feedback=feedback,
        )

        logger.info(
            f"ClaimAuditorAgent: Verification complete. Grounding Rate: {report.grounding_rate * 100:.1f}%, "
            f"Fully Verified: {report.is_fully_verified}"
        )
        return report
