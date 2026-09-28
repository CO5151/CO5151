# Architecture Decision Records (ADRs)

This directory contains lightweight Architecture Decision Records (ADRs) for LegalPilot-VN.

Each record documents an important architectural decision, the context behind it, alternative options considered, and the resulting trade-offs.

---

## Decision Log

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](0001-multi-agent-adk.md) | Multi-Agent Orchestration with Google Agent Development Kit (ADK) | Accepted | 2026-09-19 |
| [ADR-0002](0002-dual-storage-graph-vector.md) | Dual Storage Architecture: Neo4j Knowledge Graph + Qdrant Vector Store | Accepted | 2026-09-19 |
| [ADR-0003](0003-selective-temporal-traversal.md) | Selective Temporal Traversal for Legal Validity and Amendment Resolution | Accepted | 2026-09-19 |
| [ADR-0004](0004-sqlite-memory-and-token-gate.md) | Embedded SQLite Enterprise Memory and Tiered Token Gating | Accepted | 2026-09-19 |

---

## How We Write ADRs

We follow a simple, human-readable format:
1. **Title and Status**: Short descriptive name and lifecycle state (Proposed, Accepted, Superseded).
2. **Context**: What problem are we solving? What constraints exist in the Vietnamese legal domain?
3. **Decision**: What choice did we make?
4. **Consequences**: What benefits did we gain? What are the trade-offs or operational costs?
