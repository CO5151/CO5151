#!/usr/bin/env bash
# Full 100-question benchmark, all 4 architecture arms, identical concise contract.
# Usage:  bash scripts/run_full_benchmark.sh [limit]
set -uo pipefail

LIMIT="${1:-100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

export BENCH_CONCISE=1

echo "=== Working dir: $PWD | limit=$LIMIT ==="

echo "--- LangGraph arms (workflow / react / multi_agent) ---"
.venv/bin/python scripts/benchmark_10_questions.py --limit "$LIMIT" --tag full
echo "LG EXIT=$?"

echo "--- Google ADK arm ---"
../.venv-adk/bin/python scripts/benchmark_adk_10_questions.py --limit "$LIMIT" --tag full
echo "ADK EXIT=$?"

echo "=== DONE ==="
