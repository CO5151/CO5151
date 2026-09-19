# Data Flow Architecture

This document describes how data flows through LegalPilot-VN during both **Document Ingestion** and **User Query Processing**.

---

## 1. Document Ingestion Flow

The ingestion pipeline converts raw legal documents into synchronized graph nodes and vector embeddings.

```
 [Raw Document (.txt / .html)]
               │
               ▼
   [Format Dispatcher]
        │              │
   (.html)           (.txt)
        ▼              ▼
 [BeautifulSoup]  [Regex Parser]
   DOM Parser       Hierarchy
        │              │
        └───────┬──────┘
                ▼
      (0 articles parsed?)
         ├── Yes ──► [Gemini LLM Fallback] (Structured JSON)
         └── No  ──┐
                   ▼
       [Parsed Legal Hierarchy]
       • Doc ID, Title, Issuer
       • Articles (Điều)
       • Clauses (Khoản)
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
  [Neo4j Upsert]      [Contextual Chunking]
  • Document Node     • Prepend parent doc & article info
  • Article Nodes     • Generate dense vector embeddings
  • Clause Nodes      • Upsert to Qdrant collection
  • AMENDS / GUIDES
```

### Steps in Ingestion:
1. **Format Detection**: Dispatches `.html` documents to `parse_html_document` and `.txt` documents to `parse_legal_document`.
2. **Fallback Parsing**: If regex or DOM parsing yields 0 articles, `llm_fallback_parse_document` activates Gemini to parse non-standard text into a strict JSON schema.
3. **Cross-Reference Extraction**: Finds relationships (`AMENDS`, `SUPERSEDES`, `GUIDES`, `REFERS_TO`) through regex and hyperlink targets.
4. **Graph Upsert**: Creates nodes and structural edges (`CONTAINS`) in Neo4j with unique constraint guarantees.
5. **Contextual Vector Chunking**: Prepopulates each clause with its statutory breadcrumb (`[Doc_Type Doc_ID - Title] [Điều X: Title] [Khoản Y]: Content`) before indexing in Qdrant.

---

## 2. User Query & Retrieval Flow

When a user submits a question or compliance scenario, the system executes a secure, multi-agent evaluation pipeline.

```
 [User Question]
       │
       ▼
 [Sanitizer & Token Gate] ── (Violations?) ──► [Reject / Block]
       │ (Pass)
       ▼
 [Lead Counsel Agent]
       │
       ├─────────────────────────────────────────┐
       ▼                                         ▼
 [Legal Research Agent]               [Compliance Auditor]
       │                                         │
       ├─► 1. Qdrant Semantic Search             │
       │      Retrieve top-k relevant clauses   │
       │                                         │
       └─► 2. Neo4j Selective Traversal          │
              Check effective_date               │
              Resolve AMENDS / SUPERSEDES        │
              Return active law only             │
       │                                         │
       └────────────────► Context ──────────────►│
                                                 │
                                                 ▼
                                        [Evaluate Facts]
                                        • Check conditions
                                        • Compute risk score
                                                 │
                                                 ▼
                                      [Drafting Assistant]
                                        • Format response
                                        • Attach citations
                                                 │
                                                 ▼
                                        [SQLite Memory]
                                        (Save session & turn)
                                                 │
                                                 ▼
                                      [Verified Legal Advice]
```

### Key Retrieval Rules:
* **Temporal Precedence**: If Decree 70/2023 amends Article 1 of Decree 152/2020, the traversal engine replaces the 2020 clause with the 2023 clause.
* **Strict Grounding**: The Drafting Assistant is instructed to reference only the retrieved and validated clauses.
* **Audit Persistence**: Every check is assigned an audit ID and stored in SQLite for compliance records.
