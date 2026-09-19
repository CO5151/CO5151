# Getting Started

This guide gets your local development environment up and running in under 5 minutes.

---

## Prerequisites

Before starting, ensure you have the following installed:
* **Python**: 3.10, 3.11, 3.12, or 3.13.
* **Docker & Docker Compose**: For running Neo4j and Qdrant database containers.
* **Git**: For version control.

---

## 1. Quickstart with `run.sh`

The easiest way to initialize the project is using the included [`run.sh`](../../run.sh) script:

```bash
# 1. Clone the repository
git clone https://github.com/DangLamTung/CO5151.git
cd CO5151

# 2. Run foundation setup (creates .env, starts Docker, inits SQLite)
./run.sh setup
```

This single command:
1. Copies `.env.example` to `.env` if not already present.
2. Starts Neo4j and Qdrant containers via Docker Compose.
3. Activates or creates your Python virtual environment.
4. Initializes the SQLite database and verifies table schemas.

---

## 2. Environment Configuration

Inspect the generated `.env` file and customize your settings if needed:

```env
# Google Gemini API Key (for LLM orchestration and fallback parsing)
GEMINI_API_KEY=your_gemini_api_key_here

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=legalpilot_password

# Qdrant Vector Store
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=vietnamese_legal_clauses

# SQLite Memory Database
SQLITE_DB_PATH=data/legalpilot_memory.db
```

---

## 3. Ingest Sample Legal Data

Populate your local Neo4j and Qdrant instances with the sample decrees in `data/raw`:

```bash
./run.sh ingest data/raw
```

You will see the pipeline parse Decree 152/2020/ND-CP and Decree 70/2023/ND-CP, extract cross-references, and index them into both databases.

---

## 4. Launch the Web UI

Start the Streamlit interface to interact with the legal assistant:

```bash
./run.sh ui
```

Open your browser at `http://localhost:8501`.

---

## 5. Verify Everything with Tests

Run the complete test suite to ensure all components are healthy:

```bash
./run.sh test
```
