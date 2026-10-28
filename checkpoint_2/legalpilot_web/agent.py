"""ADK web entry point --- Checkpoint 2 demo.

Run from `CO5151/checkpoint_2/`:

    ../.venv-adk/bin/adk web --port 8000

Then open http://127.0.0.1:8000 and pick `legalpilot_web`.

ADK discovers this module because it exposes `root_agent`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# checkpoint_2/legalpilot_web/agent.py -> CO5151/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The retriever and the graph export are addressed with paths relative to the
# project root (`data/processed/...`). `adk web` sets the CWD to the folder it
# scans, so without this the dense index silently fails to load and retrieval
# degrades to the 6-document catalogue.
os.chdir(PROJECT_ROOT)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / ".env")

# Pin the dense retriever for the demo: the Cypher path matches on exact
# document numbers and returns the wrong statute for a natural-language query,
# which makes the demo look broken. Set BENCH_RETRIEVER=auto to let the
# retriever try Neo4j first instead.
os.environ.setdefault("BENCH_RETRIEVER", "dense")

from src.agents.adk_pipeline import (  # noqa: E402
    DEFAULT_MODEL,
    WEB_DRAFTER_INSTRUCTION,
    build_legal_pipeline,
)
from src.agents.claim_auditor import ClaimAuditorAgent  # noqa: E402
from src.agents.lawgraph import LawGraphAgent  # noqa: E402

# Both workers are deterministic Python: the retriever reads the dense index
# (with the Neo4j validity map layered on top), the auditor reads
# status/revoked_by. Only the Planner and the Drafter call the LLM.
retriever = LawGraphAgent()
auditor = ClaimAuditorAgent()

# Architecture matches D2 Interim Report: OrchestratorAgent -> DrafterAuditorLoop (DrafterAgent <-> AuditorAgent)
root_agent = build_legal_pipeline(
    retriever,
    auditor,
    with_intake=False,
    with_web_finding=False,
    drafter_instruction=None,
)

__all__ = ["root_agent", "DEFAULT_MODEL"]
