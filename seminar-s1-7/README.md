# CO5151 — Seminar S1-7: Agent Design Patterns & Orchestration
## Group G4 (Semester 261, HCMUT-VNU)
**Faculty Advisor:** Dr. Le Xuan Bach  
**Presenting Group:** Dang Lam Tung (Lead) · Nguyen Trung Phong · Vu Viet Hung  
**Seminar Date:** Wednesday, October 21, 2026 (Submission Deadline: 23:59 Sunday, October 18, 2026)

---

## 1. Submission Package Checklist (4 Mandatory Email Attachments)

Subject line: `[CO5151][G4] Seminar S1-7`

1. **`slides_s1_7.pdf`**: Exactly 22 slides in Academic English. Designed with prompt/outline style, balanced equal time (~9.5 mins) & equal weightage across all 3 members.
2. **`annotated_bibliography_en.pdf`**: Exactly ONE PAGE (4 Core Readings + 4 Extension Papers, exactly 1 critical reflection sentence per paper).
3. **`src/` & Live Pipeline Demo**: Production Multi-Agent Pipeline (`python3 -m src.agents.orchestrator`) and Streamlit UI (`streamlit run src/ui/app.py`), proving the necessity of External Ground-Truth Verifiers and State Checkpointing.
4. **`ai_use_statement_en.pdf`**: Transparent AI-use declaration in compliance with HCMUT academic integrity policies.

---

## 2. Equal Time & Intellectual Weightage Breakdown (30 Minutes Total)

Each member presents **exactly 6 substantive slides** (~9.5 minutes), covering foundational theory, systems design, and critical empirical papers:

| Member | Time | Assigned Scope & Primary Literature | Content Slides |
| :--- | :---: | :--- | :--- |
| **Nguyen Trung Phong**<br>*(Member)* | **9.5 mins** | **Block 1: Primitives, Simplicity First \& Extension 1**<br>• Workflows vs. Autonomous Agents (Fixed code paths vs. Model control)<br>• Why Anthropic argues: *"Start Simple"* ($P = p^n$ compounding error)<br>• Building Blocks: Prompt Chaining \& Semantic Routing (Buys vs. Costs)<br>• **Extension 1 (Wang et al., 2022)**: *Self-Consistency* (Sampling $\neq$ Refinement)<br>• **Decision Framework**: When to stick with simple code (3-question test) | **Slides 5–9**<br>*(5 slides)* |
| **Vu Viet Hung**<br>*(Member)* | **9.5 mins** | **Block 2: Dynamic Orchestration, Systems \& Extension 2**<br>• **Orchestrator-Workers vs. One Long Context** *(Teacher's mandatory question)*<br>• Evaluator-Optimizer \& Lead/Subagent Split (Anthropic 2025: $3-8\times$ cost/latency)<br>• **LangGraph \& Durable Execution**: State Graphs, Checkpointing \& Fault Recovery<br>• **Extension 2 (Huang et al., 2023)**: Fallacy of Intrinsic Self-Correction<br>• Comprehensive Architectural Trade-Off Matrix (All 6 Patterns) | **Slides 10–14**<br>*(5 slides)* |
| **Dang Lam Tung**<br>*(Group Lead)* | **11 mins** | **Block 3: G4 Architecture, Deep Verification \& Live Demo**<br>• **Architecture: Orchestrator Coordinating Sub-Agents** (Slide 15): D1 Multi-Agent System<br>• **External Verification & Oracles** (Slide 16): Ground-truth oracles vs. model self-critique (OpenAI 2025)<br>• **Extension 3 (Lightman et al., 2023)** (Slide 17): *Let's Verify* (PRM vs. ORM step scoring)<br>• **Extension 4 (Zelikman et al., 2022)** (Slide 18): *STaR* (Bootstrap loop via ground-truth filter)<br>• **Feedback Signal Synthesis Matrix** (Slide 19): Comparing signal origins across 4 techniques<br>• **Live Project Verification Trace** (Slide 20): Intercept of revoked Decree 101/2012 $\to$ 52/2024<br>• **50-Query Benchmark Results & Frontiers** (Slide 21): Empirical gains from external verifiers | **Slides 15–21**<br>*(7 slides)* |
| **Shared** | **1.5 mins** | Title (Slide 1), Roadmap (Slide 2), Deadlines (Slide 3), Lit Map (Slide 4), Conclusion \& Committee Q&A (Slide 22) | **Slides 1–4, 22** |

---

## 3. Live Project Execution Trace & Benchmark Demo

We execute the live multi-agent verification pipeline from our actual project codebase:

### A. Run CLI Multi-Agent Orchestration Trace
```bash
python3 -m src.agents.orchestrator
```
This demonstrates:
1. **Dynamic Task Decomposition**: User query split across specialized legal workers.
2. **External MCP Ground-Truth Verifier**: Intercepts revoked statutes (e.g., Decree 101/2012 on 50B capital) via live status lookup (`vbpl_verify_status`).
3. **State Checkpointing & Re-Routing**: Intercepts the revoked decree, rolls state back, and re-routes to current Decree 52/2024 with 100% compliance.
4. **Contrast with Chatty Swarms / Naive Prompting**: Eliminates conversational sycophancy where subagents flatter and accept each other's hallucinations.

### B. Run Interactive Web Visual Dashboard
```bash
streamlit run src/ui/app.py
```
Open `http://localhost:8501` to test interactive legal queries, inspect step-by-step agent execution traces, and view active vs. revoked law status tables in real time.
