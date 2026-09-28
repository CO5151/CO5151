"""Orchestrator Agent and Pipeline for LegalPilot-VN (Theme 9).

Coordinates the multi-agent execution loop following Google ADK:
1. Orchestrator decomposes query into legal subgoals.
2. LawGraphAgent retrieves candidate provisions from statutory catalog.
3. ClaimAuditorAgent checks validity against external ground-truth (re-routing if revoked).
4. DrafterAgent synthesizes the verified compliance dossier.
5. SQLiteMemoryManager persists audit trace and state for durable execution.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.agents.base import ADKAgent, ADKRunner
from src.agents.claim_auditor import ClaimAuditorAgent
from src.agents.drafter import DrafterAgent
from src.agents.lawgraph import LawGraphAgent
from src.core.logger import logger
from src.memory.sqlite_manager import SQLiteMemoryManager
from src.memory.state_models import AuditHistoryRecord, AuditReport, EnterpriseProfile, LegalAgentState


class LegalOrchestrator(ADKAgent):
    """Central orchestrator managing multi-agent state transitions and recovery loops."""

    def __init__(
        self,
        memory_manager: SQLiteMemoryManager | None = None,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            name="LegalOrchestrator",
            description="Điều phối đa tác tử pháp luật Việt Nam (Planning -> Retrieval -> Audit -> Recovery -> Dossier).",
            role="orchestrator",
            tools=[],
        )
        self.memory_manager = memory_manager or SQLiteMemoryManager("data/enterprise_compliance.db")
        self.max_retries = max_retries

        # Initialize sub-agents
        self.lawgraph_agent = LawGraphAgent()
        self.auditor_agent = ClaimAuditorAgent(memory_manager=self.memory_manager)
        self.drafter_agent = DrafterAgent()

        # Initialize ADK Runner
        self.runner = ADKRunner([self.lawgraph_agent, self.auditor_agent, self.drafter_agent])

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Executes orchestration via standard ADK interface."""
        if isinstance(input_data, str):
            query = input_data
            profile = context.get("enterprise_profile")
        elif isinstance(input_data, dict):
            query = input_data.get("query", "")
            profile = input_data.get("enterprise_profile")
        else:
            query = str(input_data)
            profile = None
        return self.run(query=query, enterprise_profile=profile)

    def plan_subgoals(self, query: str) -> tuple[list[str], list[str]]:
        """Decomposes user query into logical legal subgoals and search keywords."""
        q_lower = query.lower()
        subgoals: list[str] = []
        keywords: list[str] = []

        if "ví điện tử" in q_lower or "thanh toán" in q_lower or "fintech" in q_lower:
            subgoals = [
                "Subgoal 1: Xác định điều kiện cấp phép cung ứng dịch vụ Ví điện tử",
                "Subgoal 2: Kiểm tra tỷ lệ sở hữu tối đa và điều kiện cho nhà đầu tư nước ngoài",
            ]
            keywords = ["ví điện tử", "thanh toán không dùng tiền mặt", "điều kiện cung ứng", "nhà đầu tư nước ngoài"]
        elif "đèn đỏ" in q_lower or "giao thông" in q_lower or "xe máy" in q_lower:
            subgoals = [
                "Subgoal 1: Tra cứu mức xử phạt vi phạm hành vi vượt đèn đỏ",
                "Subgoal 2: Xác định hình thức xử phạt bổ sung (tước giấy phép lái xe)",
            ]
            keywords = ["vượt đèn đỏ", "mô tô", "xe gắn máy", "đèn tín hiệu", "xử phạt"]
        elif "lao động" in q_lower or "chuyên gia" in q_lower:
            subgoals = [
                "Subgoal 1: Điều kiện cấp giấy phép lao động cho chuyên gia nước ngoài",
            ]
            keywords = ["lao động nước ngoài", "giấy phép lao động", "chuyên gia"]
        else:
            subgoals = ["Subgoal: Tra cứu và đối soát văn bản quy phạm pháp luật áp dụng"]
            keywords = [w for w in q_lower.split() if len(w) > 3]

        return subgoals, keywords

    def run(
        self,
        query: str,
        enterprise_profile: EnterpriseProfile | None = None,
        session_id: str | None = None,
    ) -> LegalAgentState:
        """Executes the full legal agentic orchestration loop."""
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        logger.info(f"LegalOrchestrator: Starting pipeline for session {session_id}")

        state = LegalAgentState(
            session_id=session_id,
            user_query=query,
            enterprise_profile=enterprise_profile,
        )

        # 1. Planning phase
        subgoals, keywords = self.plan_subgoals(query)
        state.plan_steps = subgoals
        state.current_step = 1

        # 2. Retrieval phase (Worker 1: LawGraph via ADK Runner)
        retrieval_res = self.runner.dispatch(
            "LawGraphAgent",
            {"subgoals": subgoals, "keywords": keywords},
        )
        retrieved = retrieval_res.data if retrieval_res.success else []
        state.retrieved_clauses = retrieved
        state.current_step = 2

        # 3. Audit phase (Worker 2: Claim Auditor - Verification Oracle via ADK Runner)
        audit_res = self.runner.dispatch("ClaimAuditorAgent", retrieved)
        audit_report: AuditReport = (
            audit_res.data
            if audit_res.success and audit_res.data
            else AuditReport(total_claims=0, grounded_claims=0, grounding_rate=0.0, is_fully_verified=False)
        )
        state.audit_report = audit_report
        state.current_step = 3

        # 4. Error recovery / Re-routing loop (if revoked documents are found)
        active_clauses = [c for c in retrieved if c.get("status") == "active"]
        if not audit_report.is_fully_verified and state.retry_count < self.max_retries:
            logger.warning("LegalOrchestrator: Revoked document detected! Triggering Re-route edge...")
            state.retry_count += 1

            # Prune revoked clauses and enforce active replacement
            revoked_docs = [c.cited_statute for c in audit_report.unsupported_claims]
            logger.info(f"LegalOrchestrator: Pruning revoked documents: {revoked_docs}")

            # If all retrieved clauses were revoked, attempt successor traversal from catalog
            if not active_clauses and audit_report.unsupported_claims:
                for uc in audit_report.unsupported_claims:
                    old_doc_info = LawGraphAgent.STATUTE_CATALOG.get(uc.cited_statute)
                    if old_doc_info and old_doc_info.get("revoked_by"):
                        successor_id = old_doc_info["revoked_by"]
                        logger.info(f"LegalOrchestrator: Following revocation chain to successor: {successor_id}")
                        successor_doc = LawGraphAgent.STATUTE_CATALOG.get(successor_id)
                        if successor_doc:
                            for art in successor_doc.get("articles", []):
                                active_clauses.append(
                                    {
                                        "doc_id": successor_doc["doc_id"],
                                        "title": successor_doc["title"],
                                        "status": successor_doc["status"],
                                        "effective_date": successor_doc["effective_date"],
                                        "article": art["article"],
                                        "article_title": art["title"],
                                        "content": art["content"],
                                    }
                                )

            # Re-audit with active verified clauses
            re_audit_res = self.runner.dispatch("ClaimAuditorAgent", active_clauses)
            audit_report = (
                re_audit_res.data
                if re_audit_res.success and re_audit_res.data
                else AuditReport(total_claims=0, grounded_claims=0, grounding_rate=0.0, is_fully_verified=False)
            )
            state.audit_report = audit_report
            state.retrieved_clauses = active_clauses

        # 5. Drafting phase (Worker 3: Drafter via ADK Runner)
        draft_res = self.runner.dispatch(
            "DrafterAgent",
            {
                "query": query,
                "verified_clauses": active_clauses,
                "audit_report": audit_report,
                "profile": enterprise_profile,
            },
        )
        dossier = draft_res.data if draft_res.success and draft_res.data else ""
        state.candidate_draft = dossier
        state.final_compliance_dossier = dossier
        state.is_completed = True
        state.current_step = 4

        # 6. Persistent Memory / Audit logging (SQLite)
        try:
            record = AuditHistoryRecord(
                session_id=session_id,
                query=query,
                compliance_matrix_path="memory/dossier_active",
                auditor_score=audit_report.grounding_rate,
            )
            self.memory_manager.log_audit_history(record)
            logger.info(f"LegalOrchestrator: Audit record logged to SQLite for session {session_id}")
        except Exception as e:
            logger.warning(f"Could not persist audit record: {e}")

        return state


if __name__ == "__main__":
    orchestrator = LegalOrchestrator()
    profile = EnterpriseProfile(
        company_name="Fintech Global Payment Co., Ltd (FDI)",
        entity_type="Doanh nghiệp FDI",
        charter_capital=35_000_000_000.0,
        sector_code="6419",
        headcount=45,
        foreign_ownership_ratio=0.45,
    )

    test_query = "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024"
    print("\n" + "=" * 80)
    print("CHẠY PIPELINE TÁC TỬ PHÁP LUẬT VIỆT NAM (LEGALPILOT-VN AGENT PIPELINE)")
    print("=" * 80)

    result_state = orchestrator.run(test_query, enterprise_profile=profile)
    print("\n" + str(result_state.final_compliance_dossier))
    print("\n[Audit Status]:", "100% Grounded" if result_state.audit_report.is_fully_verified else "Warning")
    print("[Session ID]:", result_state.session_id)
