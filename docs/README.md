# LegalPilot-VN Documentation

Welcome to the documentation for **LegalPilot-VN**, an autonomous multi-agent RAG system for Vietnamese legal compliance and statutory verification.

This folder contains architecture specifications, design decision records, and development guides. Everything is written to be concise, practical, and human-friendly.

---

## Documentation Map

```
docs/
├── README.md                          # This index
├── adr/                               # Architecture Decision Records
│   ├── README.md                      # ADR directory and status log
│   ├── 0001-multi-agent-adk.md        # ADR 0001: Multi-agent orchestration via Google ADK
│   ├── 0002-dual-storage-graph-vector.md # ADR 0002: Dual storage (Neo4j Graph + Qdrant Vector)
│   ├── 0003-selective-temporal-traversal.md # ADR 0003: Selective temporal traversal for legal validity
│   └── 0004-sqlite-memory-and-token-gate.md # ADR 0004: SQLite memory and token gating
├── architecture/                      # System architecture and design
│   ├── overview.md                    # High-level architecture and component map
│   ├── data-flow.md                   # Ingestion and query-retrieval data flows
│   └── storage-models.md              # Neo4j schema, Qdrant vectors, and SQLite tables
└── development/                       # Engineering and contribution guides
    ├── getting-started.md             # Local setup, environment, and run.sh commands
    ├── workflows.md                   # Ingestion CLI, test runs, and daily workflows
    └── conventions.md                 # Code style, typing, zero em-dash rule, and commits
```

---

## Quick Navigation

### 1. Architecture Decision Records (`adr/`)
If you want to know **why** the system is built the way it is, start here.
* [ADR Index](adr/README.md): Overview of all architectural decisions.
* [ADR-0001: Google ADK Orchestration](adr/0001-multi-agent-adk.md): Why we use a specialized multi-agent hierarchy instead of a single prompt.
* [ADR-0002: Dual Storage Strategy](adr/0002-dual-storage-graph-vector.md): Why vector search alone fails in legal RAG and how Neo4j fixes it.
* [ADR-0003: Selective Temporal Traversal](adr/0003-selective-temporal-traversal.md): How we resolve amendments and repeals across decree versions.
* [ADR-0004: SQLite Memory and Token Gate](adr/0004-sqlite-memory-and-token-gate.md): How we track sessions, audit compliance, and guard LLM budget.

### 2. Architecture (`architecture/`)
If you want to understand **how** the system fits together, explore these guides.
* [Architecture Overview](architecture/overview.md): System context, core subsystems, and high-level diagram.
* [Data Flow](architecture/data-flow.md): Step-by-step walkthrough of document ingestion and user query processing.
* [Storage Models](architecture/storage-models.md): Complete schemas for Neo4j (graph), Qdrant (vectors), and SQLite (memory).

### 3. Development (`development/`)
If you are writing code or running the project locally, check these guides.
* [Getting Started](development/getting-started.md): 5-minute setup with Docker, Python virtual environment, and `./run.sh`.
* [Workflows](development/workflows.md): Running batch ingestion, running tests, and launching the Streamlit UI.
* [Conventions](development/conventions.md): Code standards, Ruff/Mypy expectations, commit rules, and formatting guidelines.

---

## Core System Principles

1. **Strict Grounding Over Creativity**: In legal matters, hallucination is dangerous. Every claim must trace back to a specific Article (Điều) and Clause (Khoản).
2. **Temporal Correctness**: Laws change. The system must always identify whether a clause is active, amended, or repealed as of a given date.
3. **Defense in Depth**: Sanitization, prompt-injection defense, and token gating run before any LLM call to keep execution safe and cost-effective.
