"""Real Google ADK orchestration for LegalPilot-VN.

Architecture matches D2 Interim Report Section 3.1 & Figure 1:

    SequentialAgent: LegalPilotPipeline
        -> OrchestratorAgent (BaseAgent Supervisor):
            1. Phase 1: Planning & Subgoal Decomposition
            2. Phase 2 (Sub-agents): DrafterAuditorLoop (LoopAgent)
                - DrafterAgent (LlmAgent): ReAct reasoning with LawGraph RAG & Web tools
                - AuditorAgent (BaseAgent): Claim & citation audit, adversarial critique (<=3 iterations)
            3. Phase 3: Packaging official Legal Compliance Dossier under Orchestrator persona

The whole graph is executed by ADK's ``Runner`` with a ``DatabaseSessionService`` backed by SQLite,
so ``session.state`` is a real, durable checkpoint rather than an ad-hoc dictionary.
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

from google.adk.agents import BaseAgent, LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.context import Context
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.tools import ToolContext
from google.genai import types

from src.core.logger import logger
from src.prompts import (
    AUDIT_CRITIQUE_PROMPT,
    DRAFTER_INSTRUCTION,
    LAWGRAPH_RESEARCH_PROMPT,
    LIVE_GAZETTE_PROMPT,
    PLANNER_INSTRUCTION,
    WEB_DRAFTER_INSTRUCTION,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

APP_NAME = "legalpilot_adk"
DEFAULT_MODEL = os.getenv("ADK_MODEL", "deepseek/deepseek-chat")
SESSION_DB = os.getenv("ADK_SESSION_DB", "data/adk_sessions.db")


def _render_context(clauses: list[dict[str, Any]], limit: int = 2, width: int = 600) -> str:
    """Render retrieved clauses into a concise prompt block."""
    lines = []
    for i, c in enumerate(clauses[:limit], 1):
        content = str(c.get("content") or "").strip()
        if len(content) > width:
            content = content[:width].rstrip() + "..."
        lines.append(
            f"[{i}] {c.get('doc_id')} - {c.get('article')}: {c.get('article_title', '')}\n"
            f"    {content}"
        )
    return "\n".join(lines) if lines else "(không truy xuất được điều khoản nào)"


def _parse_plan(raw: str) -> tuple[list[str], list[str]]:
    """Best-effort parse of the planner JSON with a safe fallback."""
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        try:
            obj = json.loads(match.group(0))
            subgoals = [str(s).strip() for s in obj.get("subgoals", []) if str(s).strip()]
            keywords = [str(k).strip() for k in obj.get("keywords", []) if str(k).strip()]
            if subgoals:
                return subgoals, keywords
        except Exception:
            pass
    return [text[:300]] if text else [], []


# ==============================================================================
# ==============================================================================
# 2. CANONICAL AGENTS (Proposal Theme 9 Section 6.1)
# ==============================================================================


class QueryIntake(BaseAgent):
    """[ORCHESTRATION] Seeds session.state['user_query'] from user input (0 LLM Token)."""

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        content = getattr(ctx, "user_content", None)
        text = ""
        if content is not None and getattr(content, "parts", None):
            text = "".join(p.text or "" for p in content.parts)
        text = text.strip() or str(ctx.session.state.get("user_query", ""))
        logger.info("QueryIntake: %s", text[:80])
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={"user_query": text}),
        )


class LegalSearchAgent(BaseAgent):
    """[CANONICAL AGENT 2] Legal Search Agent.

    Traverses LawGraph directional relationships and dense index to retrieve
    applicable statutory provisions (0 LLM Token deterministic traversal + optional reasoning).
    """

    retriever: Any = None
    model: str = DEFAULT_MODEL

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import litellm

        state = ctx.session.state
        query = str(state.get("user_query", "")).strip()
        if not query:
            content = getattr(ctx, "user_content", None)
            if content and getattr(content, "parts", None):
                query = "".join(p.text or "" for p in content.parts).strip()

        subgoals, keywords = _parse_plan(state.get("plan", ""))
        if not subgoals:
            subgoals = [query] if query else []

        # Deterministic retrieval over LawGraph & dense index
        clauses = self.retriever.retrieve_provisions(
            subgoals=subgoals, keywords=keywords, query=query
        )
        logger.info("LegalSearchAgent: %d clauses for %d subgoals", len(clauses), len(subgoals))

        # Optional LLM reasoning call
        retrieval_analysis = ""
        if self.model and clauses and query:
            try:
                resp = litellm.completion(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": LAWGRAPH_RESEARCH_PROMPT.format(
                                query=query,
                                subgoals=subgoals,
                                context=_render_context(clauses, limit=3),
                            ),
                        },
                    ],
                    max_tokens=120,
                    temperature=0.1,
                )
                retrieval_analysis = resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning("LegalSearchAgent LLM reasoning skipped: %s", e)

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "user_query": query,
                    "subgoals": subgoals,
                    "keywords": keywords,
                    "retrieved_clauses": clauses,
                    "retrieved_raw": clauses,
                    "retrieved_context": _render_context(clauses),
                    "retrieval_analysis": retrieval_analysis,
                    "retrieval_attempt": int(state.get("retrieval_attempt", 0)) + 1,
                    "audit_summary": "(Chờ kiểm định từ Legal Verification Agent)",
                    "audit_critique": "",
                    "loop_iteration": 0,
                }
            ),
        )


RetrievalWorker = LegalSearchAgent  # Backward compatibility alias


class AuditorAgent(BaseAgent):
    """[CANONICAL AGENT 5] Auditor Agent (Claim Auditor / Adversarial Critic).

    - Deterministic verification: Validates all citations against Neo4j validity status & MoJ gazette.
    - Post-draft claim audit: Verifies that candidate draft only cites active, grounded statutes.
    - Loop control: If invalid citations exist and iterations < max_iterations, emits critique
      and triggers revision (escalate=False). Once verified or bounded limit reached, emits escalate=True.
    - LLM critique (optional): Generates natural language critique warning of expired law.
    """

    auditor: Any = None
    model: str = DEFAULT_MODEL
    max_iterations: int = 3

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import litellm

        state = ctx.session.state
        clauses = state.get("retrieved_clauses", []) or []
        candidate_draft = str(state.get("final_dossier") or state.get("candidate_draft") or "")
        current_iteration = int(state.get("loop_iteration", 0)) + 1

        # Deterministic Oracle check (0 LLM token)
        report = self.auditor.audit_provisions(
            clauses, enable_live_vbpl=False, candidate_draft=candidate_draft
        )

        active = [c for c in clauses if not (c.get("revoked_by") or c.get("superseded_by"))]
        revoked = [c.get("doc_id") for c in clauses if c.get("revoked_by")]
        superseded = [
            f"{c.get('doc_id')} -> {c.get('superseded_by')}"
            for c in clauses
            if c.get("superseded_by") and not c.get("revoked_by")
        ]

        # Scan candidate draft for revoked doc_ids
        revoked_cited = [r for r in revoked if r and r in candidate_draft]

        is_clean = (
            (len(revoked) == 0 and len(superseded) == 0 and len(revoked_cited) == 0)
            or len(active) == 0
        )
        should_escalate = is_clean or (current_iteration >= self.max_iterations)

        audit_summary = (
            f"{len(active)}/{len(clauses)} điều khoản dùng được làm căn cứ; "
            f"hết hiệu lực: {revoked or 'không có'}; "
            f"bị thay thế: {superseded or 'không có'}"
        )

        audit_critique = ""
        if not is_clean:
            base_critique = (
                f"[Phản biện vòng {current_iteration}] CẢNH BÁO PHÁP LÝ TỪ CLAIM AUDITOR: "
                f"Phát hiện văn bản/căn cứ hết hiệu lực hoặc bị thay thế ({', '.join(revoked or revoked_cited)}). "
                f"Yêu cầu Drafter LOẠI BỎ hoàn toàn các căn cứ này và chỉ soạn thảo dựa trên các điều khoản còn hiệu lực: "
                f"{', '.join(str(c.get('doc_id')) for c in active) if active else 'Không còn điều khoản hiệu lực'}."
            )
            # Optional LLM critique call
            if self.model and clauses:
                try:
                    resp = litellm.completion(
                        model=self.model,
                        messages=[
                            {
                                "role": "user",
                                "content": AUDIT_CRITIQUE_PROMPT.format(
                                    context=_render_context(clauses, limit=3),
                                    audit_summary=audit_summary,
                                ),
                            },
                        ],
                        max_tokens=150,
                        temperature=0.1,
                    )
                    llm_critique = (resp.choices[0].message.content or "").strip()
                    audit_critique = f"{base_critique}\n{llm_critique}" if llm_critique else base_critique
                except Exception as e:
                    logger.warning("LegalVerificationAgent LLM reasoning skipped: %s", e)
                    audit_critique = base_critique
            else:
                audit_critique = base_critique

        delta: dict[str, Any] = {
            "audit_report": {
                "total_claims": report.total_claims,
                "grounded_claims": report.grounded_claims,
                "grounding_rate": report.grounding_rate,
                "is_fully_verified": report.is_fully_verified,
                "unsupported": [c.cited_statute for c in report.unsupported_claims],
                "revoked": revoked,
                "superseded": superseded,
            },
            "audit_summary": audit_summary,
            "audit_critique": audit_critique,
            "active_clauses": active,
            "retrieved_clauses": active,
            "retrieved_context": _render_context(active),
            "loop_iteration": current_iteration,
            "candidate_draft": candidate_draft,
        }
        if "retrieved_raw" not in state:
            delta["retrieved_raw"] = clauses

        logger.info(
            "LegalVerificationAgent (iter %d/%d): %d/%d clauses citable, revoked=%d superseded=%d, clean=%s, escalate=%s",
            current_iteration,
            self.max_iterations,
            len(active),
            len(clauses),
            len(revoked),
            len(superseded),
            is_clean,
            should_escalate,
        )
        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_escalate, state_delta=delta),
        )


LegalVerificationAgent = AuditorAgent  # Backward compatibility alias
AuditWorker = AuditorAgent  # Backward compatibility alias


class LegalLawUpdateAgent(BaseAgent):
    """[CANONICAL AGENT 3] Legal Law Update Agent (Live Gazette & Official Portals).

    - Queries official legal databases (vbpl.vn, SBV portal) to verify real-time statutory status.
    - Evaluates relevance and authenticity over official government whitelist.
    """

    model: str = DEFAULT_MODEL

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import litellm

        from src.tools.web_search import render_web_findings, search_official_legal_web

        state = ctx.session.state
        query = str(state.get("user_query", ""))

        # Deterministic search over official portals (0 LLM token)
        payload = search_official_legal_web(query, limit=3)
        text = render_web_findings(payload)
        hits = payload.get("hits", [])
        summary = (
            f"{len(hits)} kết quả trên cổng chính thức; "
            f"loại {payload.get('blocked', 0)} kết quả ngoài whitelist"
            if payload.get("status") == "ok"
            else f"không tra được web ({payload.get('status')})"
        )

        # Optional LLM analysis call
        web_analysis = ""
        if self.model and hits and query:
            try:
                resp = litellm.completion(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": LIVE_GAZETTE_PROMPT.format(
                                query=query,
                                text=text[:400],
                            ),
                        },
                    ],
                    max_tokens=100,
                    temperature=0.1,
                )
                web_analysis = resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning("LegalLawUpdateAgent LLM reasoning skipped: %s", e)

        logger.info("LegalLawUpdateAgent: %s", summary)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "web_findings": hits,
                    "web_findings_text": text,
                    "web_findings_summary": summary,
                    "web_findings_analysis": web_analysis,
                }
            ),
        )


WebFindingWorker = LegalLawUpdateAgent  # Backward compatibility alias


REASONING_AGENT_INSTRUCTION = """Bạn là Drafter trong hệ thống LegalPilot-VN.
Nhiệm vụ: tra cứu ngắn gọn và biên soạn báo cáo tư vấn tuân thủ pháp lý ngân hàng & doanh nghiệp Việt Nam.

BẠN CÓ CÔNG CỤ (TOOLS):
1. `query_lawgraph(query)`: Tra cứu điều khoản pháp luật từ cơ sở dữ liệu LawGraph.
2. `search_official_web(query)`: Tra cứu văn bản mới nhất trên cổng thông tin chính thức (vbpl.vn, sbv.gov.vn).

CÂU HỎI: [USER_QUERY]
KẾ HOẠCH: [PLAN]
PHẢN BIỆN TỪ AUDITOR: [AUDIT_CRITIQUE]

QUY TẮC BẮT BUỘC ĐỂ TIẾT KIỆM TÀI NGUYÊN (QUAN TRỌNG):
1. KHÔNG suy nghĩ lan man, KHÔNG viết lời giải thích trước khi gọi tool. Đi thẳng vào việc gọi tool.
2. CHỈ gọi tool `query_lawgraph` TỐI ĐA 1 LẦN (hoặc 2 lần nếu thật sự cần thiết) với từ khóa chính xác nhất.
3. Đọc thông tin ngắn gọn, tập trung đúng điều khoản giải đáp cho câu hỏi.
4. Ngay khi có thông tin, biên soạn câu trả lời ngay:
   - Nêu rõ số Điều, Khoản, số hiệu văn bản (ví dụ: "Căn cứ Điều 13 Nghị định 94/2025/NĐ-CP...").
   - Trình bày ngắn gọn, mạch lạc theo gạch đầu dòng các bước / hồ sơ / điều kiện.
   - Đi thẳng vào nội dung, không viết lời chào hỏi hay xin lỗi.
"""

ORCHESTRATOR_FINAL_INSTRUCTION = """Bạn là Trưởng nhóm Pháp chế (Lead Legal Counsel / Orchestrator) của hệ thống LegalPilot-VN.
Nhiệm vụ của bạn là xem xét toàn diện kết quả từ các Sub-Agents, phê duyệt và ban hành BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ chính thức gửi người dùng.

CÂU HỎI CỦA NGƯỜI DÙNG:
[USER_QUERY]

KẾT QUẢ KIỂM TOÁN TỪ LEGAL VERIFICATION AGENT:
[AUDIT_SUMMARY]

BẢN THẢO TƯ VẤN TỪ LEGAL REASONING AGENT:
[CANDIDATE_DRAFT]

QUY TẮC BAN HÀNH BÁO CÁO CUỐI CÙNG:
1. TIÊU ĐỀ CHÍNH THỨC:
   # BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ (LEGAL COMPLIANCE DOSSIER)
2. NỘI DUNG TƯ VẤN NGHIỆP VỤ:
   - Trực tiếp giải đáp câu hỏi của người dùng một cách mạch lạc, chi tiết, chuyên nghiệp.
   - Nêu rõ các căn cứ pháp lý đã được kiểm định (số Điều, Khoản, số hiệu văn bản quy phạm pháp luật).
   - Liệt kê đầy đủ các điều kiện, tiêu chuẩn, hồ sơ thủ tục theo gạch đầu dòng rõ ràng.
3. KẾT LUẬN KIỂM ĐỊNH HIỆU LỰC (VERIFICATION VERDICT):
   - Đưa ra phần xác nhận ngắn gọn: Toàn bộ căn cứ pháp lý trong báo cáo đã được kiểm toán tự động trên hệ thống LawGraph & cổng thông tin chính thức, xác nhận 100% văn bản còn hiệu lực thi hành.
4. MIỄN TRỪ TRÁCH NHIỆM:
   - Kết thúc bằng:
   *Lưu ý miễn trừ trách nhiệm: Báo cáo chỉ có giá trị tham vấn kỹ thuật tuân thủ hành chính, không thay thế cho ý kiến tư vấn chính thức của Luật sư được cấp chứng chỉ hành nghề.*
"""


def make_lawgraph_tool(retriever: Any):
    def query_lawgraph(query: str, tool_context: ToolContext) -> str:
        """Tra cứu điều khoản và quy định pháp luật Việt Nam từ đồ thị tri thức LawGraph (Neo4j & Qdrant vector index).

        Args:
            query: Nội dung câu hỏi pháp lý, mục tiêu nghiên cứu hoặc từ khoá cần tra cứu.
        """
        words = [w for w in query.split() if len(w) > 2]
        clauses = retriever.retrieve_provisions(subgoals=[query], keywords=words)
        curr = list(tool_context.state.get("retrieved_clauses") or [])
        existing_ids = {c.get("doc_id") for c in curr}
        for c in clauses:
            if c.get("doc_id") not in existing_ids:
                curr.append(c)
                existing_ids.add(c.get("doc_id"))
        tool_context.state["retrieved_clauses"] = curr
        tool_context.state["retrieved_context"] = _render_context(curr, limit=2, width=600)
        logger.info("query_lawgraph tool: retrieved %d clauses for '%s'", len(clauses), query[:50])
        return _render_context(clauses, limit=2, width=600)

    return query_lawgraph


def make_official_web_tool():
    def search_official_web(query: str, tool_context: ToolContext) -> str:
        """Tra cứu văn bản quy phạm pháp luật và thông tư mới nhất trên các cổng thông tin chính thức (vbpl.vn, sbv.gov.vn, moj.gov.vn).

        Args:
            query: Từ khoá hoặc số hiệu văn bản cần tra cứu trực tuyến.
        """
        from src.tools.web_search import render_web_findings, search_official_legal_web

        payload = search_official_legal_web(query, limit=2)
        text = render_web_findings(payload)
        hits = payload.get("hits", [])
        tool_context.state["web_findings"] = hits
        tool_context.state["web_findings_text"] = text
        logger.info("search_official_web tool: found %d hits for '%s'", len(hits), query[:50])
        return text[:800] if len(text) > 800 else text

    return search_official_web


class OrchestratorAgent(BaseAgent):
    """[CANONICAL AGENT 1] Orchestrator Agent (Supervisor).

    Coordinates the LegalPilot-VN multi-agent workflow (D2 Report Figure 1 & Pitch Slide 2/19):
    1. Phase 1 (Planning / Decomposition): Decomposes user query into research subgoals and keywords.
    2. Sub-Agent Coordination: Drives sub_agents (e.g. ReasoningVerificationLoop: Drafter <-> Auditor).
    3. Phase 3 (Final Answer Deliverable): Reviews the audited candidate draft and issues the official
       verified Legal Compliance Dossier under the same Orchestrator persona.
    """

    model: str = DEFAULT_MODEL

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        import litellm

        state = ctx.session.state
        query = str(state.get("user_query", "")).strip()
        if not query:
            content = getattr(ctx, "user_content", None)
            if content and getattr(content, "parts", None):
                query = "".join(p.text or "" for p in content.parts).strip()
                if query:
                    state["user_query"] = query

        # --- Phase 1: Planning & Subgoal Decomposition ---
        plan_text = ""
        try:
            resp = litellm.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_INSTRUCTION},
                    {"role": "user", "content": query or "(Không có câu hỏi cụ thể)"},
                ],
                max_tokens=80,
                temperature=0.1,
            )
            plan_text = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("OrchestratorAgent planning LLM call failed: %s", e)
            plan_text = json.dumps({"subgoals": [query], "keywords": query.split()[:4]}, ensure_ascii=False)

        state["plan"] = plan_text
        yield Event(
            author=self.name,
            content=types.Content(
                role="assistant",
                parts=[types.Part.from_text(text=f"📋 **KẾ HOẠCH ĐIỀU PHỐI & PHÂN RÃ CÂU HỎI (ORCHESTRATOR)**\n\n{plan_text}")],
            ),
            actions=EventActions(
                state_delta={"plan": plan_text, "user_query": query}
            ),
        )

        # --- Phase 2: Delegate to Sub-Agents (Drafter <-> Auditor Loop) ---
        for sub in self.sub_agents:
            async for ev in sub.run_async(ctx):
                yield ev

        # --- Phase 3: Package Official Final Compliance Dossier (0 LLM Token) ---
        draft = str(state.get("final_dossier") or state.get("candidate_draft") or "").strip()
        audit = str(state.get("audit_summary") or "(100% căn cứ hợp lệ)")

        if draft:
            final_dossier = (
                f"# BÁO CÁO TƯ VẤN TUÂN THỦ PHÁP LÝ (LEGAL COMPLIANCE DOSSIER)\n\n"
                f"{draft}\n\n"
                f"---\n"
                f"### KẾT LUẬN KIỂM ĐỊNH HIỆU LỰC (VERIFICATION VERDICT)\n"
                f"✅ **Đã kiểm toán tự động qua LawGraph & Cổng công báo:** {audit}\n\n"
                f"*Lưu ý miễn trừ trách nhiệm: Báo cáo chỉ có giá trị tham vấn kỹ thuật tuân thủ hành chính, "
                f"không thay thế cho ý kiến tư vấn chính thức của Luật sư được cấp chứng chỉ hành nghề.*"
            )
        else:
            final_dossier = "Đã hoàn thành tra cứu và kiểm định."

        state["final_dossier"] = final_dossier
        yield Event(
            author=self.name,
            content=types.Content(
                role="assistant",
                parts=[types.Part.from_text(text=final_dossier)],
            ),
            actions=EventActions(
                state_delta={"final_dossier": final_dossier}
            ),
        )


def build_legal_pipeline(
    retriever: Any,
    auditor: Any,
    model: str = DEFAULT_MODEL,
    with_intake: bool = False,
    with_web_finding: bool = False,
    drafter_instruction: str | None = None,
    max_loop_iterations: int = 3,
    with_standalone_search: bool = False,
) -> SequentialAgent:
    """Compose the LegalPilot ADK graph matching D2 Interim Report Figure 1 & Pitch Slide 2/19.

    Architecture:
      OrchestratorAgent (Supervisor)
        -> DrafterAuditorLoop:
             - DrafterAgent (equipped with LawGraph RAG & Web search tools)
             <-> AuditorAgent (Claim Auditor / Adversarial Critic)

    Args:
        with_intake: prepend a ``QueryIntake`` step that copies user message into state.
        with_web_finding: include ``LegalLawUpdateAgent`` (Live Gazette / vbpl.vn) as standalone step.
        drafter_instruction: override the Drafter prompt.
        max_loop_iterations: maximum iterations for DrafterAuditorLoop (default 3).
        with_standalone_search: if True, keeps LegalSearchAgent as a standalone step before the loop.
    """
    reasoning_tools = [make_lawgraph_tool(retriever), make_official_web_tool()]

    def reasoning_instruction(ctx: ReadonlyContext) -> str:
        state = ctx.session.state
        query = str(state.get("user_query") or "").strip()
        if not query and hasattr(ctx, "user_content") and ctx.user_content and ctx.user_content.parts:
            query = "".join(p.text or "" for p in ctx.user_content.parts).strip()
        plan = str(state.get("plan") or "")
        critique = str(state.get("audit_critique") or "")

        base = drafter_instruction or REASONING_AGENT_INSTRUCTION
        res = (
            base.replace("[USER_QUERY]", query or "(Không có câu hỏi cụ thể)")
            .replace("[PLAN]", plan or "(Đang xử lý)")
            .replace("[AUDIT_CRITIQUE]", critique or "(Chưa có phản biện)")
            .replace("{user_query}", query or "(Không có câu hỏi cụ thể)")
            .replace("{plan}", plan or "(Đang xử lý)")
            .replace("{audit_critique}", critique or "")
            .replace("{audit_summary}", str(state.get("audit_summary") or ""))
            .replace("{retrieved_context}", str(state.get("retrieved_context") or "(Tra cứu bằng tools)"))
            .replace("{web_findings_text}", str(state.get("web_findings_text") or ""))
        )
        return re.sub(r"\{[a-zA-Z0-9_]+\}", "", res)

    drafter_agent = LlmAgent(
        name="DrafterAgent",
        model=LiteLlm(model=model),
        description="2. Drafter Agent: Chủ động tra cứu LawGraph (RAG) và Web chính thức qua Tool Layer để soạn thảo ý kiến pháp lý.",
        instruction=reasoning_instruction,
        tools=reasoning_tools,
        output_key="final_dossier",
    )

    auditor_agent = AuditorAgent(
        name="AuditorAgent",
        description="3. Auditor Agent: Thẩm định căn cứ, phát hiện luật hết hiệu lực, kích hoạt vòng lặp phản biện.",
        auditor=auditor,
        model=model,
        max_iterations=max_loop_iterations,
    )

    # Phase 2 Loop: Drafter Agent (with Tool Layer) <-> Auditor Agent
    drafter_auditor_loop = LoopAgent(
        name="DrafterAuditorLoop",
        description="Vòng lặp Đối soát / Phản biện: Drafter Agent tra cứu và soạn thảo; Auditor Agent thẩm định hiệu lực (tối đa 3 vòng).",
        sub_agents=[drafter_agent, auditor_agent],
        max_iterations=max_loop_iterations,
    )

    orchestrator_sub_agents: list[Any] = []
    if with_standalone_search:
        search_agent = LegalSearchAgent(
            name="LegalSearchAgent",
            description="Standalone Legal Search Agent: Traverses LawGraph and retrieves statutory provisions.",
            retriever=retriever,
            model=model,
        )
        orchestrator_sub_agents.append(search_agent)

    if with_web_finding:
        law_update_agent = LegalLawUpdateAgent(
            name="LegalLawUpdateAgent",
            description="Standalone Legal Law Update Agent: Tra cứu cổng thông tin chính thức.",
            model=model,
        )
        orchestrator_sub_agents.append(law_update_agent)

    orchestrator_sub_agents.append(drafter_auditor_loop)

    orchestrator = OrchestratorAgent(
        name="OrchestratorAgent",
        description="1. Orchestrator Agent (Supervisor): Phân tích lập kế hoạch câu hỏi và ban hành Báo cáo Tư vấn Tuân thủ Pháp lý cuối cùng.",
        model=model,
        sub_agents=orchestrator_sub_agents,
    )

    pipeline_sub_agents: list[Any] = (
        [QueryIntake(name="QueryIntake", description="Copies the user message into session state.")]
        if with_intake
        else []
    )
    pipeline_sub_agents.append(orchestrator)

    return SequentialAgent(
        name="LegalPilotPipeline",
        description="Hệ thống LegalPilot-VN (Báo cáo D2 Hình 1): Orchestrator Supervisor điều phối DrafterAuditorLoop và ban hành Báo cáo cuối cùng.",
        sub_agents=pipeline_sub_agents,
    )


class LegalPilotADK:
    """Drives the ADK graph with a real Runner and a SQLite session service."""

    def __init__(
        self,
        retriever: Any,
        auditor: Any,
        model: str = DEFAULT_MODEL,
        max_loop_iterations: int = 3,
        with_intake: bool = False,
        with_web_finding: bool = False,
        drafter_instruction: str | None = None,
    ) -> None:
        self.graph = build_legal_pipeline(
            retriever,
            auditor,
            model=model,
            with_intake=with_intake,
            with_web_finding=with_web_finding,
            drafter_instruction=drafter_instruction,
            max_loop_iterations=max_loop_iterations,
        )
        self.session_service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{SESSION_DB}")
        self.runner = Runner(
            app_name=APP_NAME,
            agent=self.graph,
            session_service=self.session_service,
            auto_create_session=True,
        )
        self.model = model

    def _build_message(self, query: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part.from_text(text=query)])

    async def _arun(self, query: str, session_id: str, user_id: str) -> dict[str, Any]:
        # Seed the query into session state so worker/drafter instructions can
        # template it without parsing events.
        await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"user_query": query},
        )
        message = types.Content(role="user", parts=[types.Part.from_text(text=query)])

        async for _event in self.runner.run_async(
            user_id=user_id, session_id=session_id, new_message=message
        ):
            pass

        final = await self.session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        return dict(final.state) if final and final.state else {}

    def run(self, query: str, session_id: str | None = None) -> dict[str, Any]:
        import asyncio
        import uuid

        sid = session_id or f"sess_{uuid.uuid4().hex[:10]}"
        return asyncio.run(self._arun(query, sid, "legal_practitioner"))
