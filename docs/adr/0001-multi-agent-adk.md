# ADR-0001: Multi-Agent Orchestration with Google Agent Development Kit (ADK)

* **Status**: Accepted
* **Date**: 2026-09-19
* **Authors**: LegalPilot-VN Engineering Team

---

## Context

Vietnamese legal compliance requires multiple distinct skills:
1. Understanding complex enterprise inquiries and breaking them into sub-tasks.
2. Accurate statutory retrieval across laws, decrees, and circulars.
3. Rigorous compliance auditing against company conditions (such as work permit eligibility).
4. Validation of mandatory application forms (such as Form No. 11/PLI).
5. Formal legal drafting and citation synthesis.

Attempting to handle all of this inside a single monolithic LLM prompt leads to frequent hallucinations, missed sub-rules, and fragile token management.

---

## Decision

We adopt a **specialized multi-agent architecture** orchestrated through the **Google Agent Development Kit (ADK)**:

* **Lead Counsel Agent (Coordinator)**: Serves as the primary contact point. It analyzes user intent, creates an execution plan, delegates to specialists, and synthesizes the final verified response.
* **Legal Research Agent (Worker)**: Interacts with the knowledge layer (Neo4j and Qdrant) to retrieve authoritative clauses, evaluate temporal validity, and trace cross-references.
* **Compliance Auditor Agent (Worker)**: Checks enterprise scenarios against legal requirements, flags violations, and computes compliance risk scores.
* **Form Validator Agent (Worker)**: Inspects required application dossiers, checklist items, and statutory forms.
* **Drafting Assistant Agent (Worker)**: Generates compliant document templates, response letters, and official explanations.

```
       [User Inquiry]
             │
             ▼
   [Lead Counsel Agent] (Orchestrator)
      │       │        │
      ├───────┼────────┤
      ▼       ▼        ▼
 [Research] [Audit] [Form Validator]
      │       │        │
      └───────┼────────┘
              ▼
   [Drafting Assistant]
              │
              ▼
   [Verified Legal Advice]
```

---

## Consequences

### Positive
* **Separation of Concerns**: Each agent has a focused prompt, specialized tools, and strict validation criteria.
* **Auditable Reasoning**: Every step of the decision chain is logged with clear sub-task inputs and outputs.
* **Reliability**: Research tasks are isolated from drafting tasks, preventing drafting hallucinations from polluting retrieval.

### Negative / Trade-offs
* **Latency**: Multi-agent coordination requires several sequential LLM calls, increasing overall turn time.
* **Orchestration Overhead**: Requires clean structured message schemas and fallback handling if a sub-agent fails.
