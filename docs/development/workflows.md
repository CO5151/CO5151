# Developer Workflows

This guide outlines common day-to-day development tasks and operational workflows in LegalPilot-VN.

---

## 1. Document Ingestion CLI

You can ingest legal documents individually or in bulk using the Python CLI module or the `./run.sh` shortcut.

### Using `./run.sh`:
```bash
# Ingest all files in data/raw (default)
./run.sh ingest

# Ingest a specific directory
./run.sh ingest path/to/documents

# Ingest a single file
./run.sh ingest data/raw/152_2020_ND-CP.txt
```

### Using `python -m src.knowledge.ingestion`:
For advanced ingestion options, run the Python module directly:
```bash
# View all available CLI flags
python3 -m src.knowledge.ingestion --help

# Ingest with LLM fallback disabled
python3 -m src.knowledge.ingestion --dir data/raw --no-llm

# Ingest only into Neo4j (skipping Qdrant vector store)
python3 -m src.knowledge.ingestion --file data/raw/70_2023_ND-CP.txt --no-qdrant

# Ingest only into Qdrant (skipping Neo4j graph)
python3 -m src.knowledge.ingestion --file data/raw/70_2023_ND-CP.txt --no-neo4j
```

---

## 2. Running Tests

We use `pytest` for all unit and integration tests.

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_ingestion.py -v

# Run tests matching a specific pattern
pytest tests/ -k "selective_traversal" -v

# Run with test coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

> **Note on Database Tests**: Tests in `test_knowledge_clients.py` and `test_selective_traversal.py` automatically skip if Neo4j or Qdrant containers are not running. Run `docker compose up -d` before testing to execute the complete suite.

---

## 3. Code Formatting & Linting

We enforce strict code formatting and linting via **Ruff** and static type checking via **Mypy**.

```bash
# 1. Format code automatically
ruff format src tests

# 2. Check for lint errors and auto-fix simple ones
ruff check --fix src tests

# 3. Verify format without modifying files (used in CI)
ruff format --check src tests

# 4. Run static type checking with Mypy
mypy src tests
```

---

## 4. Working with Docker Containers

Manage the background database services with Docker Compose:

```bash
# Start Neo4j and Qdrant in detached mode
docker compose up -d

# View service logs
docker compose logs -f

# Check container status
docker compose ps

# Stop database services
docker compose down

# Wipe database volumes for a clean reset
docker compose down -v
```

### Service Web Consoles:
* **Neo4j Browser**: Visit `http://localhost:7474` (User: `neo4j`, Password: `legalpilot_password`).
* **Qdrant Dashboard**: Visit `http://localhost:6333/dashboard`.
