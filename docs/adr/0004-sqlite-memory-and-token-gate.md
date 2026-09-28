# ADR-0004: Embedded SQLite Enterprise Memory and Tiered Token Gating

* **Status**: Accepted
* **Date**: 2026-09-19
* **Authors**: LegalPilot-VN Engineering Team

---

## Context

Multi-turn legal consultations require maintaining context across multiple messages, persisting audit logs of compliance decisions, and tracking token expenditures.

At the same time, enterprise users must be protected from unexpected cloud LLM cost spikes and malicious prompt injection attacks attempting to flood the context window.

---

## Decision

We adopt a two-layer control and persistence strategy:

1. **Embedded SQLite Enterprise Memory (`SQLiteMemoryManager`)**:
   * Uses an embedded SQLite database (`data/legalpilot_memory.db`) requiring zero external server infrastructure.
   * Maintains structured relational tables:
     * `sessions`: Conversation session metadata and active mode.
     * `messages`: Full message history with role, content, and token counts.
     * `compliance_audits`: Immutable record of compliance evaluations, risk scores, and citations.
     * `token_usage`: Per-request token consumption metrics for cost tracking.

2. **Tiered Token Gate (`TokenGate`)**:
   * Inspects incoming user prompts before they reach any agent or LLM.
   * Enforces hard token limits per turn to prevent denial-of-service or context buffer overflows.
   * Truncates or rejects payloads exceeding tier thresholds.

```
 [User Prompt]
       │
       ▼
  [TokenGate] ── (Exceeds Limit?) ──► [Reject / Truncate]
       │ (Pass)
       ▼
 [Multi-Agent Execution]
       │
       ▼
 [SQLite Memory] ──► Persist Message, Session State & Token Metrics
```

---

## Consequences

### Positive
* **Zero Infrastructure Overhead**: SQLite is embedded directly in the Python runtime, simplifying local setup and testing.
* **Auditability**: Every compliance check and its corresponding input parameters are persistently saved for compliance auditing.
* **Cost Predictability**: The token gate prevents runaway LLM usage from unbounded user inputs.

### Negative / Trade-offs
* **Single-Node Limitation**: Standard SQLite does not support active-active distributed writes across multiple container instances. For horizontal multi-node scaling in the future, SQLite can be replaced with PostgreSQL or replicated via Litestream.
