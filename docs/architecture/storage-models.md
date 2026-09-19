# Storage Models & Schemas

LegalPilot-VN uses three storage systems: Neo4j (graph), Qdrant (vectors), and SQLite (memory). This document defines the exact schema and data models for each.

---

## 1. Neo4j Knowledge Graph Schema

The Neo4j database models the structure of Vietnamese legislation and the inter-document legal relationships.

### Node Labels & Properties

#### `Document`
Represents an official legal enactment (Law, Decree, Circular, Decision).
* `doc_id` (String, Unique): Normalized identifier, e.g. `"152/2020/ND-CP"`.
* `title` (String): Full legal title.
* `doc_type` (String): `"Nghị định"`, `"Thông tư"`, `"Luật"`, etc.
* `issuer` (String): Issuing authority, e.g. `"Chính phủ"`.
* `issue_date` (String, YYYY-MM-DD): Signing date.
* `effective_date` (String, YYYY-MM-DD): Enforcement start date.
* `expiration_date` (String, YYYY-MM-DD, Optional): Null if currently active.
* `status` (String): `"in_force"`, `"expired"`, or `"partially_amended"`.

#### `Article`
Represents a legal article (Điều).
* `article_id` (String, Unique): e.g. `"152/2020/ND-CP:Article_1"`.
* `doc_id` (String): Parent document identifier.
* `article_number` (String): e.g. `"1"`, `"2"`.
* `title` (String): Article heading, e.g. `"Phạm vi điều chỉnh"`.
* `content` (String): Full text of the article.

#### `Clause`
Represents a clause or sub-clause (Khoản / Điểm).
* `clause_id` (String, Unique): e.g. `"152/2020/ND-CP:Article_1:Clause_1"`.
* `article_id` (String): Parent article identifier.
* `clause_number` (String): e.g. `"1"`, `"2"`.
* `content` (String): Full text of the clause.

### Relationship Types

| Relationship | From Node | To Node | Description |
|---|---|---|---|
| `CONTAINS` | `Document` | `Article` | Hierarchical ownership |
| `CONTAINS` | `Article` | `Clause` | Hierarchical ownership |
| `AMENDS` | `Document` | `Document` / `Article` | Modifies or supplements target entity |
| `SUPERSEDES` | `Document` | `Document` / `Article` | Repeals target entity |
| `GUIDES` | `Document` | `Document` | Implements higher-level law (Decree guides Law) |
| `REFERS_TO` | `Document` | `Document` | General statutory citation |

---

## 2. Qdrant Vector Collection

* **Collection Name**: `vietnamese_legal_clauses`
* **Distance Metric**: Cosine
* **Vector Dimension**: 768 (or configurable via `VECTOR_DIMENSION`)

### Point Payload Structure

```json
{
  "id": "e4d74f26-06be-5722-b924-a745778b77a1",
  "vector": [0.024, -0.012, "..."],
  "payload": {
    "doc_id": "152/2020/ND-CP",
    "article_id": "152/2020/ND-CP:Article_1",
    "clause_id": "152/2020/ND-CP:Article_1:Clause_1",
    "article_number": "1",
    "clause_number": "1",
    "doc_type": "Nghị định",
    "issuer": "Chính phủ",
    "title": "Nghị định quy định về người lao động nước ngoài...",
    "status": "in_force",
    "effective_date": "2021-02-15",
    "expiration_date": null,
    "text": "[Nghị định 152/2020/ND-CP - ...] [Điều 1: Phạm vi điều chỉnh] [Khoản 1]: Nghị định này quy định...",
    "raw_clause": "Nghị định này quy định..."
  }
}
```

---

## 3. SQLite Memory Database

Stored at `data/legalpilot_memory.db`.

### Tables

#### `sessions`
* `session_id` (TEXT, PRIMARY KEY): Unique UUID.
* `title` (TEXT): Auto-generated conversation title.
* `mode` (TEXT): Consultation mode (`compliance`, `research`, `drafting`).
* `created_at` (TIMESTAMP)
* `updated_at` (TIMESTAMP)

#### `messages`
* `message_id` (TEXT, PRIMARY KEY): Unique UUID.
* `session_id` (TEXT, FOREIGN KEY -> sessions.session_id)
* `role` (TEXT): `"user"`, `"assistant"`, `"system"`.
* `content` (TEXT): Message text.
* `tokens` (INTEGER): Estimated token count.
* `created_at` (TIMESTAMP)

#### `compliance_audits`
* `audit_id` (TEXT, PRIMARY KEY): Unique UUID.
* `session_id` (TEXT, FOREIGN KEY -> sessions.session_id)
* `scenario_summary` (TEXT): Summary of the enterprise scenario audited.
* `compliance_score` (REAL): Risk score from 0.0 to 1.0.
* `violations_json` (TEXT): JSON array of identified violations.
* `citations_json` (TEXT): JSON array of supporting legal citations.
* `created_at` (TIMESTAMP)

#### `token_usage`
* `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
* `session_id` (TEXT)
* `model` (TEXT): LLM model name.
* `prompt_tokens` (INTEGER)
* `completion_tokens` (INTEGER)
* `total_tokens` (INTEGER)
* `created_at` (TIMESTAMP)
