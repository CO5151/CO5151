# ADR-0002: Dual Storage Architecture: Neo4j Knowledge Graph + Qdrant Vector Store

* **Status**: Accepted
* **Date**: 2026-09-19
* **Authors**: LegalPilot-VN Engineering Team

---

## Context

Standard RAG systems rely exclusively on dense vector similarity search over text chunks. In the legal domain, this approach fails on three critical fronts:

1. **Hierarchical Loss**: A clause (Khoản) cannot be interpreted without its parent Article (Điều) and document title. Naive chunking loses statutory context.
2. **Relational Blindness**: Legal texts reference each other constantly ("pursuant to Decree X", "repeals Article Y of Circular Z"). Vector search cannot reliably traverse these references.
3. **Keyword Rigidity**: Legal terminology in Vietnamese is precise. Dense embeddings alone sometimes confuse related but distinct legal terms.

---

## Decision

We implement a **Dual Storage Architecture** pairing a graph database with a vector database:

1. **Neo4j Knowledge Graph**:
   * Stores the structural hierarchy: `(:Document) -> [:CONTAINS] -> (:Article) -> [:CONTAINS] -> (:Clause)`.
   * Stores inter-document legal relationships: `AMENDS`, `SUPERSEDES`, `GUIDES`, and `REFERS_TO`.
   * Serves as the authority for relationship traversal, hierarchy reconstruction, and temporal status checking.

2. **Qdrant Vector Store**:
   * Stores dense vector embeddings of individual clauses.
   * Chunks are enriched with prepended statutory context: `[Document Type Doc_ID - Title] [Article num: Title] [Clause num]: Content`.
   * Serves as the high-speed semantic retrieval engine for natural language inquiries.

```
                  [Legal Document Ingestion]
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       [Neo4j Graph]                   [Qdrant Vectors]
  • Document Hierarchy            • Dense Embeddings
  • AMENDS / SUPERSEDES           • Contextual Chunks
  • GUIDES / REFERS_TO            • Semantic Similarity Search
              │                               │
              └───────────────┬───────────────┘
                              ▼
                [Hybrid Legal Retrieval Engine]
```

---

## Consequences

### Positive
* **Exact Context**: Retrieved clauses always carry their exact parent article and decree metadata.
* **Citation Accuracy**: The system can traverse from an amended clause to its latest amendment in the graph.
* **Hybrid Search**: Allows filtering by graph properties (such as active documents only) before or after vector similarity search.

### Negative / Trade-offs
* **Infrastructure Footprint**: Developers and deployments must run both Neo4j and Qdrant containers.
* **Synchronization Requirement**: Ingestion must upsert into both databases atomically or handle partial sync failures.
