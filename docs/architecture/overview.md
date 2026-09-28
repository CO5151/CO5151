# Architecture Overview

LegalPilot-VN is an autonomous multi-agent RAG system purpose-built for Vietnamese legal compliance, statutory verification, and automated drafting.

---

## High-Level System Architecture

```
                                  [User / Browser]
                                         │
                                         ▼
                            [Streamlit Web UI / API]
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │      Security & Guardrails    │
                         │  • Input Sanitizer            │
                         │  • Token Gate                 │
                         │  • Prompt Injection Shield    │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │   Google ADK Multi-Agent Core │
                         │                               │
                         │      [Lead Counsel Agent]     │
                         │        (Orchestration)        │
                         │         │    │    │           │
                         │   ┌─────┘    │    └─────┐     │
                         │   ▼          ▼          ▼     │
                         │ [Research] [Audit]   [Forms]  │
                         │   └─────┬────┴────┬─────┘     │
                         │         ▼         ▼           │
                         │      [Drafting Assistant]     │
                         └───────────────┬───────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
  ┌─────────────────────────────┐                 ┌─────────────────────────────┐
  │     Neo4j Knowledge Graph   │                 │     Qdrant Vector Store     │
  │  • Document Hierarchy       │                 │  • Dense Vector Embeddings  │
  │  • Temporal Validity Traversal│               │  • Context-Prepended Chunks │
  │  • AMENDS / SUPERSEDES edges │                │  • Fast Semantic Search     │
  └─────────────────────────────┘                 └─────────────────────────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                          ┌─────────────────────────────┐
                          │   SQLite Enterprise Memory  │
                          │  • Session State            │
                          │  • Compliance Audit Trails  │
                          │  • Token Usage & Telemetry  │
                          └─────────────────────────────┘
```

---

## Core Subsystems

### 1. Security & Guardrails (`src/security/`)
* **Sanitizer (`sanitizer.py`)**: Cleans input strings, strips harmful script tags, and normalizes Vietnamese text encoding.
* **Token Gate (`token_gate.py`)**: Checks user prompt length and token usage against system budgets before triggering LLM calls.
* **Guardrails (`guardrails.py`)**: Detects jailbreak attempts, prompt injection, and toxic inputs.

### 2. Multi-Agent Orchestrator (`src/agents/`)
Powered by Google Agent Development Kit (ADK):
* **Lead Counsel**: Analyzes the question, breaks it into structured steps, delegates tasks, and verifies the final answer.
* **Legal Research Agent**: Queries Neo4j and Qdrant to retrieve relevant statutory clauses and check their validity.
* **Compliance Auditor Agent**: Evaluates user facts against legal requirements and computes a compliance score.
* **Form Validator Agent**: Validates required documentation dossiers (e.g. Form 11/PLI under Decree 152/2020).
* **Drafting Assistant**: Drafts official compliance reports, explanation letters, or contract clauses.

### 3. Knowledge Layer (`src/knowledge/`)
* **Neo4j Client (`neo4j_client.py`)**: Manages the graph database representing legal documents, articles, clauses, and relationships.
* **Qdrant Client (`qdrant_client.py`)**: Manages collection lifecycle, vector upserts, and cosine similarity searches.
* **Ingestion Pipeline (`ingestion.py`)**: Parses raw legal text and HTML into structured hierarchies and generates contextualized chunks.
* **Selective Traversal Engine (`selective_traversal.py`)**: Resolves active legal validity by following `AMENDS` and `SUPERSEDES` relationships based on a target date.

### 4. Memory & Persistence (`src/memory/`)
* **SQLite Memory Manager (`sqlite_manager.py`)**: Embedded store tracking sessions, message turns, compliance audit trails, and token consumption metrics.

### 5. Web Interface (`src/ui/`)
* **Streamlit App (`app.py`)**: Responsive chat interface showing agent deliberation traces, statutory citations, and compliance audit reports.
