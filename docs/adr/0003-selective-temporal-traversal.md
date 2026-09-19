# ADR-0003: Selective Temporal Traversal for Legal Validity and Amendment Resolution

* **Status**: Accepted
* **Date**: 2026-09-19
* **Authors**: LegalPilot-VN Engineering Team

---

## Context

Vietnamese regulatory frameworks evolve rapidly through amending decrees and circulars. For example:
* **Decree 152/2020/ND-CP** originally regulated foreign workers in Vietnam (effective February 15, 2021).
* **Decree 70/2023/ND-CP** amended and supplemented key articles of Decree 152/2020/ND-CP (such as Article 1, Article 3, Article 9) effective September 18, 2023.

A naive RAG retrieval system querying "foreign worker eligibility" might retrieve the older 2020 clause because of high semantic similarity, providing outdated or illegal compliance advice.

---

## Decision

We implement a **Selective Edge Traversal Engine** (`SelectiveTraversalEngine`) operating on Neo4j:

1. **Temporal Filtering**:
   * Every legal query specifies a target assessment date (defaults to the current date).
   * A document or article is considered valid only if: `effective_date <= target_date` AND (`expiration_date IS NULL` OR `expiration_date > target_date`).

2. **Amendment Resolution**:
   * When an article or document is identified, the engine inspects incoming and outgoing `AMENDS` and `SUPERSEDES` edges.
   * If an amending document is active on the target date, the engine prioritizes the amending clause.
   * If an article was repealed by a subsequent decree, the engine flags it as expired or repealed and blocks it from being presented as active law.

```
 [Decree 152/2020/ND-CP] ◄────── [AMENDS] ────── [Decree 70/2023/ND-CP]
 (Effective: 2021-02-15)                          (Effective: 2023-09-18)
          │                                                │
          ▼                                                ▼
   Old Requirement                                  Active Requirement
   (Outdated if date >= 2023-09-18)                 (Active if date >= 2023-09-18)
```

---

## Consequences

### Positive
* **Zero Outdated Advice**: Guarantees that users are advised based on the law that is active as of their specified date.
* **Traceable Lineage**: Provides a clear audit path showing the historical progression of a legal requirement from its original enactment to its latest amendment.

### Negative / Trade-offs
* **Graph Traversal Cost**: Adds Cypher traversal hops on top of initial vector retrieval.
* **Parser Accuracy Dependency**: Requires accurate extraction of `AMENDS` and `SUPERSEDES` relationships during document ingestion.
