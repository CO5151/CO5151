# LegalPilot-VN (`src/`) Source Code Architecture & Execution Guide

> **Core Engine for Vietnamese Legal Agentic Compliance & Retrieval**  
> Implemented with **Google ADK (Agent Development Kit)**, **Temporal-Guided Selective Traversal**, and **Claim Auditor Verification Oracles**.

---

## 1. Directory & Module Overview

```
src/
├── agents/                     # Google ADK Multi-Agent System
│   ├── base.py                 # ADKAgent, ADKRunner, ToolDefinition, AgentResult
│   ├── orchestrator.py         # LegalOrchestrator (Planning -> Dispatch -> Audit -> Re-route)
│   ├── lawgraph.py             # LawGraphAgent (Statutory retrieval worker)
│   ├── claim_auditor.py        # ClaimAuditorAgent (Verification oracle detecting revoked laws)
│   └── drafter.py              # DrafterAgent (Compliance dossier synthesizer & disclaimer)
│
├── tools/                      # Google ADK Compliant Tool Wrappers
│   ├── statutory_retriever.py  # retrieve_statutory_provisions & STATUTORY_RETRIEVER_TOOL
│   └── validity_checker.py     # check_statute_validity & VALIDITY_CHECKER_TOOL
│
├── evaluation/                 # SBV-LawGraph Benchmark Evaluation Suite (ACIIDS 2026)
│   ├── metrics.py              # P@k, R@k, F1@k, F2@k, Hit@k, MRR, Noise Ratio, Grounding Rate
│   ├── baselines.py            # 4 Baselines (Naive RAG, Static 1-Hop Graph, ReAct, LegalPilot)
│   ├── evaluator.py            # SBVLawGraphEvaluator (100 QA dataset runner & cost calculator)
│   └── report.py               # Markdown and LaTeX summary table generators
│
├── knowledge/                  # Dual Knowledge Store (Graph + Dense Vectors)
│   ├── ingestion.py            # PDF/HTML statutory parser, chunker & schema mapper
│   ├── neo4j_client.py         # Neo4j Graph DB connection & Cypher queries
│   ├── qdrant_client.py        # Qdrant vector DB semantic search & embeddings
│   └── selective_traversal.py  # Temporal-guided Selective Edge Traversal engine
│
├── memory/                     # State Management & Durable Storage
│   ├── state_models.py         # Pydantic v2 schemas for LegalAgentState, AtomicClaim, etc.
│   └── sqlite_manager.py       # SQLite database manager for audit trails & session history
│
├── security/                   # Safety Guardrails & Access Control
│   ├── guardrails.py           # Input / output validation & sensitive content filtering
│   ├── sanitizer.py            # Unicode normalization & prompt injection sanitizer
│   └── token_gate.py           # Human-in-the-loop authorization gate for high-risk actions
│
├── core/                       # Core Utilities & Configurations
│   ├── config.py               # Pydantic Settings & YAML configuration loader
│   ├── exceptions.py           # Custom exception hierarchy
│   └── logger.py               # Structured logging configuration
│
└── ui/                         # User Interface
    └── app.py                  # Interactive Streamlit compliance dashboard
```

---

## 2. Installation & Prerequisites

### Prerequisites
- **Python**: 3.10 to 3.13 (Recommended: Python 3.12 / 3.13)
- **Database Services (Optional for Live Graph/Vector mode)**:
  - Docker & Docker Compose (for Neo4j 5.x and Qdrant 1.11+)

### A. Environment Setup

1. **Clone and enter repository**:
   ```bash
   cd CO5151
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Set Up Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Configure `.env` keys if using external LLMs (Google Vertex AI, DeepSeek, OpenAI, or Ollama):
   ```env
   # Model Provider
   LLM_PROVIDER=deepseek_v3
   DEEPSEEK_API_KEY=your_deepseek_api_key
   # or GOOGLE_API_KEY / VERTEX_AI
   
   # Databases (Defaults configured in docker-compose.yml)
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=legalpilot_secret
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   ```

5. **Start Database Containers (Optional)**:
   ```bash
   docker compose up -d
   ```

---

## 3. How to Run Every Component

### A. Run the Multi-Agent Compliance Pipeline

Execute the end-to-end Google ADK agent loop:
```bash
python3 -m src.agents.orchestrator
```
**What happens**:
1. `LegalOrchestrator` decomposes user query into subgoals.
2. `LawGraphAgent` retrieves candidate provisions from the statutory catalog.
3. `ClaimAuditorAgent` verifies document validity and detects expired statutes (e.g. Decree 101/2012).
4. `LegalOrchestrator` triggers the re-routing loop, prunes revoked items, and resolves successors (Decree 52/2024).
5. `DrafterAgent` synthesizes a fully verified legal compliance dossier.
6. The session audit record is saved to SQLite (`data/enterprise_compliance.db`).

---

### B. Run the SBV-LawGraph Benchmark Evaluator

Run comparative benchmarking against the 100 SBV legal questions:
```bash
python3 -c "
from src.evaluation.evaluator import SBVLawGraphEvaluator
from src.evaluation.report import generate_markdown_report

evaluator = SBVLawGraphEvaluator('data/benchmarks/sbv_testset_tvpl.json')
results = evaluator.run_full_benchmark(save_path='data/benchmarks/benchmark_results.json')
print(generate_markdown_report(results))
"
```

**Estimate DeepSeek vs. Vertex AI compute costs for the 1,180-run evaluation suite**:
```bash
python3 -c "
from src.evaluation.evaluator import SBVLawGraphEvaluator
import json

cost_summary = SBVLawGraphEvaluator.estimate_suite_cost(pricing_provider='deepseek_v3', cache_hit_ratio=0.6)
print(json.dumps(cost_summary, indent=2))
"
```

---

### C. Run the Interactive Streamlit Web UI

Launch the visual compliance consultation dashboard:
```bash
streamlit run src/ui/app.py
```
Or use the convenience startup script:
```bash
./run.sh ui
```

---

### D. Ingest New Statutory Documents (PDF / HTML)

Parse raw legal documents into Neo4j graph nodes and Qdrant vector chunks:
```bash
# Ingest entire raw data folder:
python3 -m src.knowledge.ingestion --dir data/raw

# Or ingest a single document:
python3 -m src.knowledge.ingestion --file data/raw/52_2024_ND-CP.pdf
```
Or via `run.sh`:
```bash
./run.sh ingest data/raw
```

---

### E. Run the Automated Test Suite

Execute all 45 unit tests across agents, evaluation metrics, guardrails, and memory:
```bash
pytest tests/ -v
```

Run specific test modules:
```bash
# Test Multi-Agent Pipeline & Recovery:
pytest tests/test_agents.py -v

# Test Benchmark Metrics & Baselines:
pytest tests/test_evaluation.py -v

# Test Security Guardrails & Sanitizers:
pytest tests/test_guardrails.py -v
```

---

## 4. Programmatic API Usage (Python SDK)

You can import and use LegalPilot-VN components in any Python application:

```python
from src.agents.orchestrator import LegalOrchestrator
from src.memory.state_models import EnterpriseProfile

# 1. Initialize orchestrator
orchestrator = LegalOrchestrator()

# 2. Define enterprise profile
profile = EnterpriseProfile(
    company_name="Fintech Global Payment Co., Ltd (FDI)",
    entity_type="Doanh nghiệp FDI",
    charter_capital=35_000_000_000.0,
    sector_code="6419",
    headcount=45,
    foreign_ownership_ratio=0.45,
)

# 3. Execute compliance query
state = orchestrator.run(
    query="Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024",
    enterprise_profile=profile,
)

# 4. Access verified compliance dossier
print(state.final_compliance_dossier)
print(f"Grounding Score: {state.audit_report.grounding_rate * 100:.1f}%")
print(f"Is Verified: {state.audit_report.is_fully_verified}")
```

---

## 5. Key Design Principles

1. **Google ADK Compatibility**: All agents extend `ADKAgent` and use standard `ToolDefinition` interfaces for plug-and-play modularity.
2. **Temporal Correctness**: Claim Auditor acts as an external verification oracle to eliminate citations of revoked or expired legal instruments.
3. **Selective Traversal**: Avoids the >60% context dilution noise of static 1-hop expansions by pruning irrelevant cross-amendment edges.
4. **Durable State Management**: SQLite persists the full execution state and audit trail across all sessions.
