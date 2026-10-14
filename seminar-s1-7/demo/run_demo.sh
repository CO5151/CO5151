#!/usr/bin/env bash
# ==============================================================================
# CO5151 Seminar S1-7: Agent Design Patterns for Law Graph Problem
# Quick Launcher for Group G4 (HCMUT-VNU)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================================================"
echo "  CO5151 SEMINAR S1-7: AGENT DESIGN PATTERNS FOR VIETNAMESE LAW GRAPH   "
echo "  Faculty Advisor: Dr. Le Xuan Bach | Group G4 (LegalPilot-VN)          "
echo "========================================================================"
echo ""
echo "Please select the demo mode to run:"
echo "  [1] Interactive Web Workbench (Local Browser UI at localhost:8765 / 8080)"
echo "  [2] Empirical Terminal Trace Benchmark (CLI side-by-side run)"
echo "  [3] Run Full Test Suite"
echo ""

MODE="${1:-1}"

if [ "$MODE" = "1" ]; then
    echo "Starting Web Demo Server..."
    python3 "$SCRIPT_DIR/serve_demo.py"
elif [ "$MODE" = "2" ]; then
    echo "Running Terminal Trace Benchmark..."
    python3 "$SCRIPT_DIR/demo_agent_design_lawgraph.py" --scenario fintech
elif [ "$MODE" = "3" ]; then
    echo "Running Evaluation Tests..."
    cd "$WORKSPACE_ROOT"
    python3 -m unittest tests/test_evaluation.py
else
    echo "Invalid option. Usage: ./run_demo.sh [1|2|3]"
    exit 1
fi
