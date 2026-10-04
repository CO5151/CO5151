# CO5151 — Seminar S1-7: Agent Design Patterns & Orchestration
## Group G4 (Semester 261, HCMUT-VNU)
**Faculty Advisor:** Dr. Le Xuan Bach  
**Presenting Group:** Dang Lam Tung (Lead) · Nguyen Trung Phong · Vu Viet Hung  
**Seminar Date:** Wednesday, October 21, 2026 (Submission Deadline: 23:59 Sunday, October 18, 2026)

---

## 1. Official Syllabus Literature Alignment (Zero Fabricated Readings)

### Core Reading (Mandatory Foundation)
- **Anthropic (Dec 2024)**: *Building Effective Agents* (Workflows vs. autonomous agents, simplicity-first thesis, prompt chaining, routing, orchestrator-workers, evaluator-optimizer).

### Extension Readings (Presenting Group Deep Dive)
1. **Anthropic (Feb 2025)**: *How We Built Our Multi-Agent Research System* (Lead/subagent decomposition, context isolation, $3\times-8\times$ token multiplier and latency overhead).
2. **OpenAI (Feb 2025)**: *A Practical Guide to Building Agents* (Model-directed tool calling loops, schemas, guardrails, and structured evals).
3. **LangGraph Documentation (2024–2025)**: *State Graphs, Checkpointing, and Human-in-the-Loop* (Cyclic state graphs, durable execution, failure recovery).

---

## 2. Submission Package Checklist (4 Mandatory Email Attachments)

Subject line: `[CO5151][G4] Seminar S1-7`

1. **`slides_s1_7.pdf`**: Exactly 22 slides in Academic English, strictly answering all 6 syllabus questions with balanced time (~9.5 mins each) across all 3 members.
2. **`annotated_bibliography_en.pdf`**: Exactly ONE PAGE (1 Core Reading + 3 Extension Readings, exactly 1 critical reflection sentence per reading).
3. **`demo_orchestration_trace.py` & `src/`**: Empirical orchestration benchmark script comparing Workflow ($1\times$), Monolithic Agent ($11.7\times$), and Orchestrator-Workers ($3.2\times$) with durable checkpoint recovery.
4. **`ai_use_statement_en.pdf`**: Transparent AI-use declaration in compliance with HCMUT academic integrity policies.

---

## 3. Equal Time & Intellectual Weightage Breakdown (30 Minutes Total)

| Member | Time | Assigned Scope & Primary Literature | Content Slides |
| :--- | :---: | :--- | :--- |
| **Nguyen Trung Phong**<br>*(Member)* | **9.5 mins** | **Block 1: Primitives, Simplicity First & Workflows**<br>• Workflows vs. Autonomous Agents (Fixed code paths vs. Model control)<br>• Why Anthropic argues: *"Start Simple"* ($P = p^n$ compounding error trap)<br>• Concrete Patterns 1 & 2: Prompt Chaining & Semantic Routing (Buys vs. Costs)<br>• Concrete Pattern 3: Evaluator-Optimizer (Feedback loop, costs, and sycophancy)<br>• Simplicity-First Decision Framework: When simple code is enough | **Slides 5–9**<br>*(5 slides)* |
| **Vu Viet Hung**<br>*(Member)* | **9.5 mins** | **Block 2: Dynamic Orchestration & Systems Architecture**<br>• **Orchestrator-Workers vs. One Long Context** (Context isolation vs attention dilution)<br>• **Anthropic (2025) Lead/Subagent Reality**: $3\times-8\times$ token cost multiplier & latency<br>• **OpenAI (2025) Practical Guide**: Tool loops, guardrails & evaluation harnesses<br>• **LangGraph State Graphs**: Cyclic graphs, state schemas, and reducers<br>• **Durable Execution & Checkpointing**: Failure recovery and human-in-the-loop | **Slides 10–14**<br>*(5 slides)* |
| **Dang Lam Tung**<br>*(Group Lead)* | **11 mins** | **Block 3: G4 Project Architecture, Defense & Live Trace**<br>• **Comprehensive Trade-Off Matrix**: Comparing all patterns across cost/latency/reliability<br>• **G4 Architecture (LegalPilot-VN)**: Orchestrator-Worker with LangGraph State Checkpoint<br>• **Design Decision Made vs. Alternative Rejected**: Why G4 rejected ReAct / naive chain<br>• **External Ground-Truth Verification Oracles**: Non-LLM status lookup (`vbpl_verify_status`)<br>• **Durable Execution in Action**: Intercepting revoked Decree 101/2012 $\to$ 52/2024 via checkpoint<br>• **Empirical Benchmark Trace**: Validating Anthropic's $3.2\times$ cost ratio<br>• **Production Guidelines & Defense Preparation**: Lessons learned from industry | **Slides 15–21**<br>*(7 slides)* |
| **Shared** | **1.5 mins** | Title (Slide 1), Roadmap (Slide 2), Deadlines (Slide 3), Literature Roadmap (Slide 4), Conclusion & Defense (Slide 22) | **Slides 1–4, 22** |

---

## 4. Run Live Trace Demo & Benchmark

Run the empirical benchmark trace script directly:
```bash
python3 seminar-s1-7/demo_orchestration_trace.py
```

Or run the production orchestrator in the main repository:
```bash
python3 -m src.agents.orchestrator
```
