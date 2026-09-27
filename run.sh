#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# LegalPilot-VN: Environment Startup Script
# ==============================================================================

ACTION="${1:-setup}"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: python3 is not installed."
    exit 1
fi

# 2. Check or create .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[+] Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "[!] Warning: .env.example not found. Creating empty .env..."
        touch .env
    fi
fi

# 3. Check Docker and start database services
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "[+] Ensuring Neo4j and Qdrant services are running..."
    docker compose up -d
else
    echo "[!] Warning: Docker is not available. Ensure Neo4j and Qdrant are running."
fi

# 4. Check and activate virtual environment
if [ -d ".venv" ]; then
    echo "[+] Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[+] Activating virtual environment (venv)..."
    source venv/bin/activate
fi

# Dispatch based on action argument
case "$ACTION" in
    setup)
        echo "[+] Initializing SQLite enterprise compliance database..."
        python3 -c "from src.memory.sqlite_manager import SQLiteMemoryManager; mgr = SQLiteMemoryManager(); mgr.init_tables(); print('[+] SQLite tables verified.')"
        echo "[+] LegalPilot-VN foundation setup completed."
        echo "    Start the Web UI with: ./run.sh ui"
        echo "    Ingest documents with: ./run.sh ingest [data/raw]"
        echo "    Run test suite with:   ./run.sh test"
        ;;
    ingest)
        shift
        echo "[+] Running document ingestion..."
        if [ $# -eq 0 ]; then
            python3 -m src.knowledge.ingestion --dir "data/raw"
        elif [ -f "$1" ]; then
            python3 -m src.knowledge.ingestion --file "$1"
        elif [ -d "$1" ]; then
            python3 -m src.knowledge.ingestion --dir "$1"
        else
            python3 -m src.knowledge.ingestion "$@"
        fi
        ;;
    ui)
        echo "[+] Starting LegalPilot-VN Web UI..."
        streamlit run src/ui/app.py
        ;;
    test)
        echo "[+] Running test suite..."
        pytest tests/ -v
        ;;
    *)
        echo "[!] Unknown command: $ACTION"
        echo "Usage: ./run.sh [setup|ingest|ui|test]"
        exit 1
        ;;
esac
