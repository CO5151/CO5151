"""Pytest fixtures for LegalPilot-VN test suite."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.memory.sqlite_manager import SQLiteMemoryManager
from src.security.sanitizer import InputSanitizer
from src.security.token_gate import HumanTokenGate

#: Set to 1 to run ``@pytest.mark.live`` tests and let unit tests reach real services.
LIVE_TESTS_ENV = "LEGALPILOT_LIVE_TESTS"
# Port 9 (discard) is closed on every dev box and CI runner: connections fail fast.
_UNREACHABLE_PORT = 9


def _live_enabled() -> bool:
    return os.getenv(LIVE_TESTS_ENV) == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skips tests that need running Neo4j / Qdrant unless explicitly enabled."""
    if _live_enabled():
        return
    skip_live = pytest.mark.skip(reason=f"needs live Neo4j/Qdrant; set {LIVE_TESTS_ENV}=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def offline_services(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Isolates unit tests from whatever happens to run on the developer's machine.

    Without this, retrieval assertions depend on the live graph's contents (the
    SBV corpus load changed every e-wallet ranking), every agent call spends
    DeepSeek tokens, and the Claim Auditor scrapes vbpl.vn. Unit tests instead
    run against the committed JSON exports and the deterministic fallbacks.
    """
    if _live_enabled() or request.node.get_closest_marker("live"):
        yield
        return

    from src.agents import base, lawgraph, parser_agent
    from src.core.config import settings

    monkeypatch.setattr(settings, "NEO4J_URI", f"bolt://127.0.0.1:{_UNREACHABLE_PORT}")
    monkeypatch.setattr(settings, "QDRANT_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "QDRANT_PORT", _UNREACHABLE_PORT)
    monkeypatch.setenv(
        "VBPL_SEARCH_URL", f"http://127.0.0.1:{_UNREACHABLE_PORT}/?Keyword={{keyword}}"
    )

    # Per-process caches in LawGraphAgent: start empty, and never load the
    # embedding model (dense search falls back to keyword/catalog retrieval).
    monkeypatch.setattr(lawgraph, "_NEO4J_HANDLE", {"client": None})
    monkeypatch.setattr(lawgraph, "_QDRANT_HANDLE", {"manager": None})
    monkeypatch.setattr(lawgraph, "_GRAPH_STATUS", {})
    monkeypatch.setattr(lawgraph, "_EMBEDDER", {"model": None})
    monkeypatch.setattr(lawgraph, "_DENSE_INDEX", {"index": (None, None, [])})

    def _no_llm(*args: object, **kwargs: object) -> str:
        raise RuntimeError("LLM calls are disabled in unit tests")

    monkeypatch.setattr(base, "invoke_adk_agent", _no_llm)
    monkeypatch.setattr(parser_agent, "invoke_adk_agent", _no_llm)
    yield


@pytest.fixture
def temp_sqlite_db(tmp_path: Path) -> SQLiteMemoryManager:
    """Provides a fresh SQLite memory manager using a temporary database file."""
    db_file = tmp_path / "test_compliance.db"
    return SQLiteMemoryManager(db_path=str(db_file))


@pytest.fixture
def sanitizer(tmp_path: Path) -> InputSanitizer:
    """Provides an InputSanitizer with a temporary export directory."""
    export_dir = tmp_path / "workspace" / "dossiers"
    return InputSanitizer(max_input_length=1000, allowed_export_dir=str(export_dir))


@pytest.fixture
def token_gate() -> HumanTokenGate:
    """Provides a HumanTokenGate with a short expiration for testing."""
    return HumanTokenGate(token_expiry_seconds=2)
