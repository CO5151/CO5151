# Cheatsheet: Inspect Ingested Data in Neo4j and Qdrant

Read-only commands for checking what ingestion actually wrote. None of the queries below modify data. For how the data got there, see [sbv-corpus-crawl.md](sbv-corpus-crawl.md).

| Tool | URL | Login |
| :--- | :--- | :--- |
| Neo4j Browser | http://localhost:7474 | Connect URL `bolt://localhost:7687`, user `NEO4J_USER`, password `NEO4J_PASSWORD` from `.env` (defaults in `.env.example`) |
| Qdrant dashboard | http://localhost:6333/dashboard | none |

Start both first: `docker compose up -d neo4j qdrant`.

---

## 1. Python Inspector (one command per question)

```bash
source .venv/bin/activate
python scripts/inspect_ingested_data.py summary                         # counts, status mix, vector config
python scripts/inspect_ingested_data.py doc 40/2024/TT-NHNN             # one document end to end
python scripts/inspect_ingested_data.py doc 40/2024/TT-NHNN --article 18 # + clauses and their vectors
HF_HUB_OFFLINE=1 python scripts/inspect_ingested_data.py search "điều kiện mở ví điện tử" --top-k 10
python scripts/inspect_ingested_data.py check                           # consistency; exit 1 on FAIL
python scripts/inspect_ingested_data.py check --sample 10000            # scan more points for zero vectors
HF_HUB_OFFLINE=1 python scripts/eval_retrieval_hit.py                   # Hit@10 on the 100 questions
```

Add `2>&1 | grep -v '| INFO'` to hide connection logs.

---

## 2. Neo4j Browser (Cypher)

Paste one query at a time into the Browser prompt. Queries that `RETURN p` (a path) draw a graph. The others show a table.

**Parameters.** Set these once per session, then reuse them in the queries below:

```cypher
:param id => '40/2024/TT-NHNN'
```
```cypher
:param date => '2020-01-01'
```

Doc ids are normalized: upper case, `Đ` becomes `D` (`52/2024/ND-CP`, not `52/2024/NĐ-CP`). Reused legacy numbers carry a year suffix (`22/QD-NH1@1994`).

### 2.1 Overview

```cypher
// Node counts by label
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC
```
```cypher
// Relationship counts by type
MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC
```
```cypher
// Documents by status and where the status came from (stubs have no title)
MATCH (d:Document)
RETURN CASE WHEN d.title IS NULL THEN '(stub)' ELSE d.status END AS status,
       d.status_source AS source, count(*) AS docs
ORDER BY docs DESC
```
```cypher
// Documents by type
MATCH (d:Document) WHERE d.title IS NOT NULL
RETURN d.doc_type AS type, count(*) AS docs ORDER BY docs DESC
```
```cypher
// Schema diagram (labels and relationship types)
CALL db.schema.visualization()
```

### 2.2 Find a Document

```cypher
// By keyword in the title
MATCH (d:Document) WHERE d.title CONTAINS 'trung gian thanh toán'
RETURN d.doc_id, d.title, d.status, d.issue_date ORDER BY d.issue_date DESC LIMIT 25
```
```cypher
// By number fragment (case-insensitive)
MATCH (d:Document) WHERE toUpper(d.doc_id) CONTAINS '40/2024'
RETURN d.doc_id, d.title, d.status
```
```cypher
// All properties of one document (MoJ status, dates, source_url, revoked_by...)
MATCH (d:Document {doc_id: $id}) RETURN properties(d) AS props
```

### 2.3 Articles and Clauses

```cypher
// Articles of a document with their clause counts
MATCH (:Document {doc_id: $id})-[:CONTAINS]->(a:Article)
OPTIONAL MATCH (a)-[:CONTAINS]->(c:Clause)
RETURN a.article_number AS dieu, a.title AS title, count(c) AS clauses, a.article_id
ORDER BY toInteger(a.article_number), a.article_id
```
```cypher
// Clauses of one article (Điều 18)
MATCH (a:Article {article_id: $id + ':Article_18'})-[:CONTAINS]->(c:Clause)
RETURN c.clause_number AS khoan, c.content AS content, c.clause_id
ORDER BY toInteger(c.clause_number)
```
```cypher
// Full-text-ish search over clause content (no index: takes a few seconds)
MATCH (d:Document)-[:CONTAINS]->(a:Article)-[:CONTAINS]->(c:Clause)
WHERE c.content CONTAINS 'định danh điện tử'
RETURN d.doc_id, d.status, a.article_number AS dieu, c.clause_number AS khoan,
       left(c.content, 160) AS excerpt
LIMIT 25
```
```cypher
// Graph view: a document's tree (limit keeps the Browser responsive)
MATCH p = (:Document {doc_id: $id})-[:CONTAINS]->(:Article)-[:CONTAINS]->(:Clause)
RETURN p LIMIT 80
```

### 2.4 Relations and Validity Over Time

```cypher
// Graph view: every non-structural edge around a document and its articles
MATCH (d:Document {doc_id: $id})
OPTIONAL MATCH (d)-[:CONTAINS]->(a:Article)
WITH d, collect(a) AS arts
UNWIND [d] + arts AS n
MATCH p = (n)-[r]-(x)
WHERE NOT type(r) IN ['CONTAINS', 'ISSUED_BY']
RETURN p LIMIT 150
```
```cypher
// Which instruments amend / guide / supersede this document (document level)
MATCH (src:Document)-[r:AMENDS|GUIDES|SUPERSEDES]->(:Document {doc_id: $id})
RETURN type(r) AS rel, src.doc_id, src.issue_date, src.status, r.scope
ORDER BY src.issue_date
```
```cypher
// What this document amends / supersedes
MATCH (:Document {doc_id: $id})-[r:AMENDS|GUIDES|SUPERSEDES]->(dst:Document)
RETURN type(r) AS rel, dst.doc_id, dst.status, r.scope
```
```cypher
// Supersession chain of an old instrument, oldest to newest (graph view)
MATCH p = (:Document {doc_id: '01/1997/QH10'})<-[:SUPERSEDES*1..6]-(:Document)
RETURN p
```
```cypher
// Same chain as a table, with the in-force end of each chain
MATCH p = (:Document {doc_id: '01/1997/QH10'})<-[:SUPERSEDES*1..6]-(newest:Document)
WHERE NOT ()-[:SUPERSEDES]->(newest)
RETURN [x IN nodes(p) | x.doc_id] AS chain, newest.status AS newest_status
```
```cypher
// Documents in force on $date by MoJ dates
MATCH (d:Document) WHERE d.title IS NOT NULL
  AND d.effective_date <= $date
  AND (d.expiration_date IS NULL OR d.expiration_date > $date)
RETURN d.doc_type AS type, count(*) AS in_force_on_date ORDER BY in_force_on_date DESC
```
```cypher
// Manual status overrides (MoJ contradicts the instrument itself)
MATCH (d:Document {status_source: 'manual_override'})
RETURN d.doc_id, d.status, d.effective_date, d.revoked_by, d.override_reason
```

Both `in_force` and `active` mean "in force", and a non-empty `revoked_by` always means inactive. The queries below test for both.

### 2.5 Data Quality Checks

```cypher
// Corpus documents the parser could not split into articles
MATCH (d:Document) WHERE d.status_source IS NOT NULL AND NOT (d)-[:CONTAINS]->(:Article)
RETURN d.doc_id, d.doc_type, d.title
```
```cypher
// Contradiction: marked in force but has revoked_by
MATCH (d:Document)
WHERE d.status IN ['in_force', 'active'] AND coalesce(d.revoked_by, '') <> ''
RETURN d.doc_id, d.status, d.eff_status_code, d.revoked_by
```
```cypher
// Expired corpus documents with no known successor
MATCH (d:Document)
WHERE d.status_source IS NOT NULL AND d.status = 'expired'
  AND coalesce(d.revoked_by, '') = '' AND NOT ()-[:SUPERSEDES]->(d)
RETURN d.doc_type AS type, count(*) AS unlinked ORDER BY unlinked DESC
```
```cypher
// Stub documents (cited but not in the corpus), most referenced first
MATCH (d:Document) WHERE d.title IS NULL
RETURN d.doc_id, COUNT { ()-->(d) } AS referenced_by
ORDER BY referenced_by DESC LIMIT 25
```
```cypher
// Articles whose number repeats inside a document (suffixed _2, _3... by the parser)
MATCH (a:Article) WHERE a.article_id =~ '.*:Article_[0-9]+_[0-9]+$'
RETURN a.doc_id, count(*) AS repeated ORDER BY repeated DESC LIMIT 25
```
```cypher
// Benchmark leakage: clauses built from testset reference answers
MATCH (c:Clause) WHERE c.clause_id ENDS WITH ':Clause_?'
RETURN c.clause_id, left(c.content, 150) AS content
ORDER BY c.clause_id
```

---

## 3. Qdrant

### 3.1 Dashboard

Open http://localhost:6333/dashboard, then **Collections > vietnamese_legal_clauses** to browse points and payloads. The **Console** tab accepts REST requests. Paste the method line, a blank line, then the JSON body:

```
POST collections/vietnamese_legal_clauses/points/scroll

{
  "limit": 10,
  "filter": {"must": [{"key": "doc_id", "match": {"value": "40/2024/TT-NHNN"}}]},
  "with_payload": ["doc_id", "article_number", "clause_number", "status", "raw_clause"]
}
```

### 3.2 curl Equivalents

```bash
Q=http://localhost:6333/collections/vietnamese_legal_clauses

# Collection info: points_count, vector size (768), distance (Cosine)
curl -s $Q | python -m json.tool

# Point count for one document
curl -s -X POST $Q/points/count -H 'Content-Type: application/json' \
  -d '{"exact": true, "filter": {"must": [{"key": "doc_id", "match": {"value": "40/2024/TT-NHNN"}}]}}'

# Point count by payload status (in_force | expired | not_in_force)
curl -s -X POST $Q/points/count -H 'Content-Type: application/json' \
  -d '{"exact": true, "filter": {"must": [{"key": "status", "match": {"value": "expired"}}]}}'

# Clauses of one article, payload only
curl -s -X POST $Q/points/scroll -H 'Content-Type: application/json' -d '{
  "limit": 50,
  "filter": {"must": [{"key": "article_id", "match": {"value": "40/2024/TT-NHNN:Article_18"}}]},
  "with_payload": ["clause_id", "clause_number", "raw_clause"]
}' | python -m json.tool

# Benchmark leakage: points built from testset reference answers
curl -s -X POST $Q/points/count -H 'Content-Type: application/json' \
  -d '{"exact": true, "filter": {"must": [{"key": "source", "match": {"value": "sbv_testset_tvpl"}}]}}'
```

### 3.3 From a Clause in Neo4j to Its Vector

Ingestion sets each point id to `uuid5(NAMESPACE_DNS, clause_id)`, so a Neo4j `clause_id` maps to exactly one point:

```bash
PID=$(python -c "import uuid,sys; print(uuid.uuid5(uuid.NAMESPACE_DNS, sys.argv[1]))" \
  '40/2024/TT-NHNN:Article_18:Clause_1')
curl -s $Q/points/$PID | python -m json.tool | head -30
```

A `404` here means that clause has no vector.

### 3.4 Semantic Search (query by meaning)

Qdrant only compares vectors, so a text question must first be embedded with **the same bi-encoder used at ingest** (`bkai-foundation-models/vietnamese-bi-encoder`, normalized). A different model gives meaningless scores.

**Python** (closest to what `LawGraphAgent.qdrant_retrieve` does):

```python
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("bkai-foundation-models/vietnamese-bi-encoder")
client = QdrantClient(host="localhost", port=6333)

question = "điều kiện mở ví điện tử cho người dưới 15 tuổi"
vector = model.encode(question, normalize_embeddings=True).tolist()

hits = client.query_points(
    collection_name="vietnamese_legal_clauses",
    query=vector,
    limit=5,
    query_filter=models.Filter(  # optional: drop it to search everything
        must=[models.FieldCondition(key="doc_id", match=models.MatchAny(any=["40/2024/TT-NHNN"]))],
        must_not=[models.FieldCondition(key="source", match=models.MatchValue(value="sbv_testset_tvpl"))],
    ),
    with_payload=["doc_id", "article_number", "clause_number", "status", "raw_clause"],
).points

for h in hits:
    p = h.payload
    print(f"{h.score:.3f}  {p['doc_id']}  Điều {p['article_number']} khoản {p['clause_number']}")
    print("       ", p["raw_clause"][:120])
```

Run it with `HF_HUB_OFFLINE=1 python my_query.py`.

**curl**: embed in Python, send the vector over REST:

```bash
HF_HUB_OFFLINE=1 python -c "
import json, sys
from sentence_transformers import SentenceTransformer
v = SentenceTransformer('bkai-foundation-models/vietnamese-bi-encoder').encode(sys.argv[1], normalize_embeddings=True).tolist()
print(json.dumps({'query': v, 'limit': 5, 'with_payload': ['doc_id', 'article_number', 'clause_number']}))
" "lãi suất cho vay ngắn hạn" 2>/dev/null > /tmp/qbody.json

curl -s -X POST $Q/points/query -H 'Content-Type: application/json' -d @/tmp/qbody.json | python -m json.tool
```

**No embedding needed: "clauses similar to this clause".** Pass an existing point id as the query, and Qdrant uses its stored vector. This also works in the dashboard Console:

```
POST collections/vietnamese_legal_clauses/points/query

{
  "query": "<point id from section 3.3>",
  "limit": 5,
  "with_payload": ["doc_id", "article_number", "clause_number"]
}
```

**Filters.** Useful payload keys: `doc_id`, `article_id`, `clause_id`, `doc_type`, `issuer`, `status`, `effective_date` (all indexed). Combine them in `must` / `must_not` / `should`.

Do not trust the `status` filter for validity. Payload status is a snapshot from ingest time, and 182 points currently disagree with the graph. For example, `33/2012/TT-NHNN` still says `in_force` in Qdrant but has `revoked_by` in Neo4j. The application searches without a status filter and takes validity from Neo4j. To see that view, use `python scripts/inspect_ingested_data.py search "..."`.

---

## 4. Reference Values (2026-10-28)

| What | Value |
| :--- | ---: |
| Document / Article / Clause nodes | 2,539 / 21,181 / 67,029 |
| of which stub documents | 907 |
| Corpus documents (`status_source` set) | 1,627 |
| `SUPERSEDES` / `AMENDS` / `GUIDES` edges | 501 / 1,503 / 2,684 |
| Qdrant points | 67,026 (768-dim, Cosine) |
| Leaked testset chunks (should be 0) | 90 in Qdrant, 90 `Clause_?` nodes in Neo4j |
