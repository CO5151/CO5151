# CO5151 Seminar S1-7: Agent Design Patterns Demo Package

> **Group G4 (LegalPilot-VN) — Semester 261, HCMUT-VNU**  
> **Faculty Advisor:** Dr. Le Xuan Bach  
> **Authors:** Dang Lam Tung (Lead) · Nguyen Trung Phong · Vu Viet Hung  

---

## 1. Overview of the Demo Package (`seminar-s1-7/demo/`)

This directory houses the live empirical demo and interactive workbench for the **Vietnamese Law Graph (LegalPilot-VN)** compliance challenge:

```
seminar-s1-7/demo/
├── web/                               # Interactive Dark-Mode Web Workbench
│   ├── index.html                     # Semantic HTML5 UI with Tabbed Panels & SVG Canvases
│   ├── styles.css                     # Pure Vanilla CSS (Glassmorphism & animations)
│   └── app.js                         # State management, StateGraph DAG & Memory Inspector
├── demo_agent_design_lawgraph.py      # Multi-scenario CLI benchmark with real SQLite persistence
├── demo_orchestration_trace.py        # Terminal trace comparison script
├── serve_demo.py                      # Standalone zero-dependency Python HTTP server
└── run_demo.sh                        # One-click launcher script
```

---

## 2. Key Interactive Features in the Demo

1. **3-Way Comparative Race (`Tab 1`)**:
   - Simulated step budget for **1. Deterministic Workflow** ($760$ tokens, $1.0\times$), **2. Monolithic ReAct Agent** ($8,950$ tokens, $11.8\times$), and **3. Orchestrator-Workers with Checkpointing** ($2,410$ tokens, $3.2\times$). These are illustrative, not API-measured; the measured 10-run mean is Workflow 849 ($1.0\times$), ReAct 6,313 ($7.4\times$), and Multi-Agent 2,760 ($3.3\times$).
2. **Graph Workflow (`Tab 2`)**:
   - Interactive LangGraph StateGraph DAG: Entry $\to$ Planning $\to$ Isolated Retrieval Worker $\to$ External Deterministic Oracle (`vbpl_verify_oracle`) $\to$ **Differential Rollback Arc** $\to$ Drafter Worker $\to$ SQLite Memory $\to$ Exit.
3. **Live Multi-Tier Memory Visualizer (`Tab 3`)**:
   - **Working Memory (`LegalAgentState`)**: Inspects `EnterpriseProfile`, `plan_steps`, `retrieved_clauses` (active vs expired), and `audit_report`.
   - **Differential Memory Diff**: Proves that upon rollback, Subgoal B & `EnterpriseProfile` are preserved in memory without being re-executed.
   - **SQLite Checkpoint Table**: Live view of snapshots stored in `data/enterprise_compliance.db`.
4. **Statutory Law Knowledge Graph (`Tab 4`)**:
   - Visualizes relations between decrees (`supersedes`, `amends`, `revoked_by`).
5. **Trade-off Matrix (`Tab 5`) & Compliance Dossier (`Tab 6`)**.

---

## 3. How to Run

### Mode 1: Interactive Web Workbench
```bash
./seminar-s1-7/demo/run_demo.sh 1
# Or directly:
python3 seminar-s1-7/demo/serve_demo.py
```
Open **`http://localhost:8765`** in your browser.

### Mode 2: Multi-Scenario CLI Benchmark
```bash
# Scenario 1: FDI E-Wallet License 2024 (Decree 101/2012 -> 52/2024)
python3 seminar-s1-7/demo/demo_agent_design_lawgraph.py --scenario fintech

# Scenario 2: Traffic Light Violation (Decree 100/2019 -> 168/2024)
python3 seminar-s1-7/demo/demo_agent_design_lawgraph.py --scenario traffic

# Scenario 3: Foreign Labor Permit (Decree 152/2020 -> 70/2023)
python3 seminar-s1-7/demo/demo_agent_design_lawgraph.py --scenario labor
```
