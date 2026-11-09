"""Orchestrator Supervisor for LegalPilot-VN (Theme 9 - Slide Pitch D1 Architecture).

Implements the official 1 Orchestrator + 2 Sub-Agents architecture:
1. Orchestrator (Supervisor):
   - Manages shared state, short-term session, and loop counter <= 3.
   - Manages long-term memory (SQLite: enterprise_profile, audit_history).
   - Coordinates the 2 Sub-Agents: DrafterAgent and ClaimAuditorAgent.
2. 2 Sub-Agents:
   - DrafterAgent: Synthesizes candidate compliance dossier; requests re-retrieval if needed.
   - ClaimAuditorAgent: Adversarial critic auditing legal provisions and candidate claims;
     directly calls Tools (RAG Database Neo4j/Qdrant + Live VBPL Web Crawl).
3. Tools Layer:
   - RAG Database (Neo4j, Qdrant): Graph & dense retrieval.
   - Web Crawl Tool: Live VBPL status check.
   - Memory Write Tool: export_dossier.
4. Human Gate:
   - Pre-export approval checkpoint before persisting to immutable audit history.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.agents.base import ADKAgent, ADKRunner
from src.agents.claim_auditor import ClaimAuditorAgent
from src.agents.drafter import DrafterAgent
from src.agents.lawgraph import LawGraphAgent
from src.core.exceptions import SecurityViolationError
from src.core.doc_ids import canonical_doc_id
from src.core.logger import logger
from src.security import SecurityGuardrails
from src.security.answer_gate import (ABSTAIN_MSG, allowed_from_clauses,
                                       extract_citations, gate_answer,
                                       strip_citations, unsupported_citations)
from src.core.statute_status import is_active_status
from src.memory.sqlite_manager import SQLiteMemoryManager
from src.memory.state_models import (
    AuditHistoryRecord,
    AuditReport,
    EnterpriseProfile,
    LegalAgentState,
)
from src.prompts import SUBGOAL_PLANNING_PROMPT


class LegalOrchestrator(ADKAgent):
    """Central Orchestrator Supervisor coordinating Drafter & Auditor Sub-Agents."""

    def __init__(
        self,
        memory_manager: SQLiteMemoryManager | None = None,
        max_retries: int = 2,
    ) -> None:
        super().__init__(
            name="LegalOrchestrator",
            description="Orchestrator điều phối 2 Sub-Agents (Drafter, Auditor) kèm Tầng Công cụ và Human Gate theo Slide Pitch D1.",
            role="orchestrator",
            tools=[],
        )
        self.memory_manager = memory_manager or SQLiteMemoryManager("data/enterprise_compliance.db")
        self.max_retries = max_retries

        # Tầng Công Cụ (Tools Layer): RAG Database (Neo4j, Qdrant)
        self.rag_tool = LawGraphAgent()
        self.lawgraph_agent = self.rag_tool  # backward-compatibility alias

        # 2 Sub-Agents (Theo Slide Pitch D1):
        self.auditor_agent = ClaimAuditorAgent(memory_manager=self.memory_manager)
        self.drafter_agent = DrafterAgent()

        # Runner managing sub-agents and tools
        self.runner = ADKRunner([self.rag_tool, self.auditor_agent, self.drafter_agent])

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
        enable_live_vbpl = context.get("enable_live_vbpl", True)
        if isinstance(input_data, dict) and "enable_live_vbpl" in input_data:
            enable_live_vbpl = input_data["enable_live_vbpl"]
        return self.run(query=query, enterprise_profile=profile, enable_live_vbpl=enable_live_vbpl)

    def plan_subgoals(self, query: str) -> tuple[list[str], list[str]]:
        """Decomposes user query into logical legal subgoals and search keywords using LLM."""
        try:
            import json

            from src.agents.base import GoogleAgent, get_default_model, invoke_adk_agent

            planner_agent = GoogleAgent(
                name="LegalPlannerAgent",
                model=get_default_model(),
                instruction='Bạn là Legal Planning Agent. Phân tích câu hỏi pháp lý và chỉ trả về DUY NHẤT một khối JSON thuần túy (không kèm giải thích hay markdown code block) theo định dạng: {"subgoals": ["...", "..."], "keywords": ["...", "..."]}',
            )
            prompt = SUBGOAL_PLANNING_PROMPT.format(query=query)
            raw = invoke_adk_agent(planner_agent, prompt).strip()
            import re

            match = re.search(r"\{.*\}", raw, flags=re.S)
            if match:
                parsed = json.loads(match.group(0))
                subgoals = [
                    str(s).strip()
                    for s in (
                        parsed.get("subgoals")
                        or parsed.get("sub_goals")
                        or parsed.get("Subgoals")
                        or []
                    )
                    if str(s).strip()
                ]
                keywords = [
                    str(k).strip()
                    for k in (parsed.get("keywords") or parsed.get("Keywords") or [])
                    if str(k).strip()
                ]
                if subgoals and keywords:
                    return subgoals, list(dict.fromkeys(keywords))
        except Exception as e:
            logger.warning("Google ADK planning failed, using dynamic NLP extraction: %s", e)

        # Dynamic regex and token extraction (NO hardcoded topic strings)
        import re

        statute_patterns = re.findall(r"\d+/\d+/[A-ZĐa-zđ\-_]+", query)
        clean_terms = [
            w.lower() for w in re.findall(r"\b[\w\-]+\b", query, flags=re.UNICODE) if len(w) > 2
        ]
        keywords = list(dict.fromkeys(statute_patterns + clean_terms[:8]))
        subgoals = [
            f"Xác định quy định pháp lý điều chỉnh cho yêu cầu: {query}",
            f"Tra cứu căn cứ và điều kiện áp dụng liên quan đến: {' '.join(clean_terms[:6])}",
        ]
        return subgoals, keywords

    def run(
        self,
        query: str,
        enterprise_profile: EnterpriseProfile | None = None,
        session_id: str | None = None,
        enable_live_vbpl: bool = True,
    ) -> LegalAgentState:
        """Executes the full legal agentic orchestration loop."""
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        logger.info(f"LegalOrchestrator: Starting pipeline for session {session_id}")

        state = LegalAgentState(
            session_id=session_id,
            user_query=query,
            enterprise_profile=enterprise_profile,
        )

        # 0. Cổng an toàn đầu vào (S2-5 guardrails) — chạy TRƯỚC khi tốn token.
        guard = SecurityGuardrails()
        try:
            verdict = guard.evaluate_query(query)
        except SecurityViolationError as exc:
            logger.warning("Guardrail chặn truy vấn: %s", exc)
            state.guardrail_verdicts.append(
                {"status": "refused", "message": str(exc), "vector_id": getattr(exc, "vector_id", None)}
            )
            state.answer_status = "refused"
            state.answer_message = str(exc)
            state.final_compliance_dossier = str(exc)
            state.is_completed = True
            return state

        state.guardrail_verdicts.append(verdict)
        if verdict.get("status") == "refused":
            state.answer_status = "refused"
            state.answer_message = verdict.get("message")
            state.final_compliance_dossier = verdict.get("message")
            state.is_completed = True
            return state
        if verdict.get("status") == "requires_human_token":
            state.human_confirmation_needed = True
            state.answer_status = "needs_human"
            state.answer_message = verdict.get("message")

        # 1. Planning phase
        subgoals, keywords = self.plan_subgoals(query)
        state.plan_steps = subgoals
        state.current_step = 1

        # 2. Retrieval phase (Worker 1: LawGraph via ADK Runner)
        retrieval_res = self.runner.dispatch(
            "LawGraphAgent",
            {"subgoals": subgoals, "keywords": keywords, "query": query},
        )
        retrieved = retrieval_res.data if retrieval_res.success else []
        state.retrieved_clauses = retrieved
        state.current_step = 2

        # Không có điều khoản nào -> KHÔNG đoán. Đây là nhánh "không đủ kiến thức".
        if not retrieved:
            logger.warning("Không truy xuất được điều khoản nào — trả về không đủ căn cứ.")
            state.answer_status = "insufficient_evidence"
            state.answer_message = ABSTAIN_MSG
            state.final_compliance_dossier = ABSTAIN_MSG
            state.is_completed = False
            return state

        # 3. Closed-Loop Drafter-Auditor Reflection & Backtracking (Proposal Section 3.1 & 3.2)
        # Drafter produces candidate draft -> Claim Auditor audits -> Backtrack if unverified
        active_clauses = list(retrieved)
        pruned_docs: set[str] = set()
        top3_checked = False
        verified_map: dict[str, dict[str, Any]] = {}
        critique_feedback: str | None = None
        audit_report = AuditReport(
            total_claims=0, grounded_claims=0, grounding_rate=0.0, is_fully_verified=False
        )
        candidate_dossier = ""

        attempts = 0
        while attempts <= self.max_retries:
            attempts += 1
            state.retry_count = attempts - 1
            state.current_step = 3

            # Step A: Drafter synthesizes candidate compliance draft
            draft_res = self.runner.dispatch(
                "DrafterAgent",
                {
                    "query": query,
                    "verified_clauses": active_clauses,
                    "audit_report": audit_report if audit_report.total_claims > 0 else None,
                    "profile": enterprise_profile,
                    "critique_feedback": critique_feedback,
                },
            )
            candidate_dossier = draft_res.data if draft_res.success and draft_res.data else ""
            if attempts == 1:
                state.candidate_draft = candidate_dossier

            # Step B: Claim Auditor audits candidate draft and provisions (Validation Bottleneck)
            audit_res = self.runner.dispatch(
                "ClaimAuditorAgent",
                {
                    "clauses": active_clauses,
                    "enable_live_vbpl": enable_live_vbpl,
                    "draft": candidate_dossier,
                },
            )
            audit_report = (
                audit_res.data
                if audit_res.success and audit_res.data
                else AuditReport(
                    total_claims=0, grounded_claims=0, grounding_rate=0.0, is_fully_verified=False
                )
            )
            state.audit_report = audit_report
            for v in audit_report.live_verifications:
                verified_map[v["doc_id"]] = v
            state.live_verifications = list(verified_map.values())

            # Step B2: Cổng dẫn chiếu chạy NGAY TRONG vòng lặp. Bị chặn thì trả
            # phản hồi cho drafter sửa, chứ không đầu hàng ngay: trước đây cổng chỉ
            # chạy sau vòng lặp nên một câu trích sai làm mất cả câu trả lời.
            gate_now_ok, gate_now_reason, _ = gate_answer(
                candidate_dossier, allowed_from_clauses(active_clauses)
            )
            if not gate_now_ok and attempts <= self.max_retries:
                logger.warning("Gate chặn bản nháp (lượt %d): %s", attempts, gate_now_reason)

                # Tự chữa lành: nếu dẫn chiếu trỏ tới điều khoản CÓ THẬT trong
                # graph mà chưa được truy xuất, lấy nó vào ngữ cảnh rồi kiểm lại.
                # Nếu điều đó KHÔNG tồn tại -> đúng là bịa, không cứu.
                allowed_now = allowed_from_clauses(active_clauses)
                missing = [c for c in extract_citations(candidate_dossier) if c not in allowed_now]
                recovered: list[dict[str, Any]] = []
                if missing:
                    try:
                        recovered = LawGraphAgent().fetch_articles(
                            [(doc, num) for num, doc in missing]
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("fetch_articles lỗi: %s", exc)
                if recovered:
                    have = {(str(re.sub(r"\D", "", c.get("article", ""))), canonical_doc_id(c.get("doc_id", "")))
                            for c in active_clauses}
                    added = [
                        r for r in recovered
                        if (str(re.sub(r"\D", "", r.get("article", ""))), canonical_doc_id(r.get("doc_id", ""))) not in have
                    ]
                    if added:
                        active_clauses.extend(added)
                        logger.info("Đã xác thực thêm %d điều khoản từ graph.", len(added))
                        critique_feedback = (
                            f"{critique_feedback or ''}\n[BỔ SUNG CĂN CỨ] Đã đối chiếu thêm các điều khoản "
                            "sau từ cơ sở dữ liệu; chỉ trích dẫn chúng nếu thật sự liên quan."
                        ).strip()
                        continue

                critique_feedback = (
                    f"{critique_feedback or ''}\n[CỔNG KIỂM CHỨNG] {gate_now_reason}. "
                    "Chỉ được trích dẫn các điều khoản nằm trong danh sách đã cung cấp; "
                    "tuyệt đối không viện dẫn văn bản khác."
                ).strip()
                continue

            # Step B3: bản nháp phải trích ít nhất MỘT căn cứ trong top-3 đã truy
            # xuất. Đo trên 100 câu: điều khoản chuẩn nằm trong top-3 tới 87%,
            # nhưng chỉ 80% câu trả lời trích đúng -> model bỏ qua căn cứ tốt nhất.
            if not top3_checked and len(active_clauses) >= 3:
                top3_checked = True
                top3 = {(str(re.sub(r"\D", "", c.get("article", ""))), canonical_doc_id(c.get("doc_id", "")))
                        for c in active_clauses[:3]}
                if not (extract_citations(candidate_dossier) & top3):
                    logger.info("Bản nháp không trích căn cứ top-3 — yêu cầu xem lại.")
                    critique_feedback = (
                        f"{critique_feedback or ''}\n[ƯU TIÊN CĂN CỨ] Bản nháp chưa trích điều khoản nào "
                        "trong các căn cứ liên quan nhất đã cung cấp. Hãy xem lại và dùng đúng căn cứ "
                        "xếp hạng cao nhất cho từng kết luận."
                    ).strip()
                    if attempts <= self.max_retries:
                        continue

            # Step C: Verification Gate (Every claim grounded in active law?)
            if audit_report.is_fully_verified:
                logger.info(
                    "LegalOrchestrator: Drafter-Auditor critique passed (100% grounded in active law)."
                )
                break

            # Step D: Backtrack loop if unverified claims / repealed clauses found
            if attempts <= self.max_retries:
                logger.warning(
                    "LegalOrchestrator: Auditor flagged invalid claims at attempt %d. Triggering BacktrackLoop...",
                    attempts,
                )
                critique_feedback = audit_report.auditor_feedback

                # Prune revoked clauses and enforce active replacement
                revoked_docs = [c.cited_statute for c in audit_report.unsupported_claims]
                pruned_docs.update(revoked_docs)
                logger.info("LegalOrchestrator: Pruning revoked documents: %s", revoked_docs)

                # Prune revoked clauses from active set
                active_clauses = [
                    c
                    for c in active_clauses
                    if c.get("doc_id") not in revoked_docs
                    and is_active_status(c.get("status"), c.get("revoked_by"))
                ]

                # Follow revocation chain in catalog/graph to successor documents
                for uc in audit_report.unsupported_claims:
                    old_doc_info = LawGraphAgent.STATUTE_CATALOG.get(uc.cited_statute)
                    successor_id = old_doc_info.get("revoked_by") if old_doc_info else None
                    if not successor_id and uc.live_verification:
                        successor_id = uc.live_verification.get("metadata", {}).get("revoked_by")
                    if successor_id:
                        logger.info(
                            "LegalOrchestrator: Following revocation chain to successor: %s",
                            successor_id,
                        )
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

        state.active_clauses = active_clauses
        state.current_step = 4

        # 5. Cổng kiểm chứng đầu ra (S2-5): mọi dẫn chiếu phải có căn cứ.
        allowed = allowed_from_clauses(active_clauses)

        # Ghi nhận dẫn chiếu tới điều khoản không tồn tại, nhưng KHÔNG huỷ cả câu
        # trả lời: thử chặn cứng ở bước này làm abstain 3% -> 27% và gt_hit 93% ->
        # 73%. Giữ câu trả lời, đánh dấu để người duyệt kiểm.
        # Kiểm MỌI dẫn chiếu với graph, không chỉ những cái ngoài `allowed`.
        # Lỗi cũ: catalog fallback có thể đưa vào active_clauses những điều không
        # tồn tại trong graph; cổng thấy "nằm trong allowed" nên cho qua, nhưng
        # đó vẫn là dẫn chiếu không có căn cứ.
        all_cites = sorted(extract_citations(candidate_dossier))
        fabricated: list[tuple[str, str]] = []
        if all_cites:
            try:
                found_all = LawGraphAgent().fetch_articles([(d, n) for n, d in all_cites])
            except Exception:  # noqa: BLE001
                found_all = []
            status_of = {
                (str(re.sub(r"\D", "", r.get("article", ""))), canonical_doc_id(r.get("doc_id", ""))):
                str(r.get("status", "")).lower()
                for r in found_all
            }
            ACTIVE = ("active", "in_force", "in-force")
            # Không tồn tại HOẶC văn bản đã hết hiệu lực => không được dùng làm căn cứ.
            fabricated = [c for c in all_cites if status_of.get(c) not in ACTIVE]
            if fabricated and candidate_dossier:
                # Bóc dẫn chiếu bịa, giữ phần nội dung còn lại thay vì huỷ cả câu.
                cleaned = strip_citations(candidate_dossier, fabricated)
                if cleaned and extract_citations(cleaned):
                    candidate_dossier = cleaned
                detail = ", ".join(f"Điều {a} {d}" for a, d in fabricated)
                logger.warning("Bản nháp trích điều khoản không tồn tại: %s", detail)
                state.guardrail_verdicts.append(
                    {"status": "answer_gate", "ok": False,
                     "reason": f"có dẫn chiếu tới điều khoản không tồn tại: {detail}"}
                )

        revoked_pairs: set[tuple[str, str]] = set()
        for doc in pruned_docs:
            for c in retrieved:
                if c.get("doc_id") == doc:
                    import re as _re
                    num = _re.sub(r"\D", "", str(c.get("article", "")))
                    if num:
                        revoked_pairs.add((num, canonical_doc_id(doc)))
        gate_ok, gate_reason, bad_cites = gate_answer(candidate_dossier, allowed, revoked_pairs)
        state.guardrail_verdicts.append(
            {"status": "answer_gate", "ok": gate_ok, "reason": gate_reason}
        )

        if not gate_ok:
            logger.warning("Answer gate chặn bản nháp: %s", gate_reason)
            state.answer_status = "insufficient_evidence"
            state.answer_message = ABSTAIN_MSG
            state.final_compliance_dossier = ABSTAIN_MSG     # hiển thị cho người dùng
            state.candidate_draft = candidate_dossier       # giữ lại để hậu kiểm
            state.is_completed = False
        else:
            state.final_compliance_dossier = candidate_dossier
            if "khác điều" in gate_reason:
                # Đúng văn bản nhưng trích điều chưa truy xuất: vẫn trả lời, nhưng
                # đánh dấu để người duyệt kiểm lại. Chặn cứng ở đây làm mất utility.
                state.answer_status = "unverified"
                state.human_confirmation_needed = True
                state.is_completed = True
            elif audit_report.is_fully_verified and not fabricated:
                state.answer_status = "ok"
                state.is_completed = True
            else:
                # Có dẫn chiếu hợp lệ nhưng auditor chưa xác nhận hết -> cần người duyệt.
                state.answer_status = "unverified"
                state.human_confirmation_needed = True
                state.is_completed = True

        # 6. Persistent Memory / Audit logging (SQLite)
        try:
            record = AuditHistoryRecord(
                session_id=session_id,
                query=query,
                compliance_matrix_path="memory/dossier_active",
                auditor_score=audit_report.grounding_rate,
            )
            self.memory_manager.log_audit_history(record)
            logger.info(
                f"LegalOrchestrator: Audit record logged to SQLite for session {session_id}"
            )
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
    print(
        "\n[Audit Status]:",
        "100% Grounded"
        if (result_state.audit_report and result_state.audit_report.is_fully_verified)
        else "Warning",
    )
    print("[Session ID]:", result_state.session_id)
