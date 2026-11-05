.PHONY: help install install-dev install-embeddings lint format typecheck test test-cov docker-up docker-down clean run-app

help:
	@echo "LegalPilot-VN - Available Makefile Commands:"
	@echo "  make install       Install runtime dependencies"
	@echo "  make install-dev   Install runtime and development dependencies"
	@echo "  make install-embeddings  Install sentence-transformers (needed to ingest / dense search)"
	@echo "  make lint          Run ruff linter"
	@echo "  make format        Run ruff code formatter"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make test          Run pytest suite"
	@echo "  make test-cov      Run pytest with coverage report"
	@echo "  make docker-up     Start Neo4j, Qdrant, and LiteLLM containers"
	@echo "  make docker-down   Stop containers"
	@echo "  make run-app       Start Streamlit Web UI"
	@echo "  make clean         Remove cache and temporary files"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt
	pre-commit install

install-embeddings:
	pip install -r requirements-embeddings.txt

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy src tests

test:
	pytest tests/

test-cov:
	pytest --cov=src --cov-report=term-missing --cov-report=html tests/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

run-app:
	streamlit run src/ui/app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -f .coverage coverage.xml
