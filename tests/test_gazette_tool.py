"""Unit tests for the Gazette and VBPL verification tool.

Tests:
- Verification of active and expired statutes
- SQLite cache hit and TTL storage
- Gazette search tool execution
- ToolDefinition compliance with Google ADK
"""

import contextlib
from pathlib import Path
from typing import Any

from src.memory.sqlite_manager import SQLiteMemoryManager
from src.tools.gazette_tool import (
    SEARCH_GAZETTE_TOOL,
    VERIFY_VBPL_STATUS_TOOL,
    search_gazette,
    verify_vbpl_status,
)


class TestGazetteTool:
    """Test suite for live gazette verification and caching."""

    test_db_path = "data/test_gazette_tool.db"

    def setup_method(self) -> None:
        self.memory = SQLiteMemoryManager(self.test_db_path)
        self.memory.init_tables()

    def teardown_method(self) -> None:
        p = Path(self.test_db_path)
        if p.exists():
            with contextlib.suppress(OSError):
                p.unlink()

    def test_verify_active_statute(self) -> None:
        """Tests that active document status is correctly resolved."""
        res: dict[str, Any] = verify_vbpl_status("52/2024/ND-CP", memory_manager=self.memory)
        assert res["doc_id"] == "52/2024/ND-CP"
        assert res["status"] == "active"
        assert res["is_in_force"] is True

    def test_verify_revoked_statute(self) -> None:
        """Tests that revoked document status is correctly flagged as expired."""
        res: dict[str, Any] = verify_vbpl_status("101/2012/ND-CP", memory_manager=self.memory)
        assert res["doc_id"] == "101/2012/ND-CP"
        assert res["status"] == "expired"
        assert res["is_in_force"] is False

    def test_sqlite_cache_hit(self) -> None:
        """Tests that subsequent checks hit the SQLite statute_cache."""
        # First call stores in cache
        first_res = verify_vbpl_status("70/2023/ND-CP", memory_manager=self.memory)
        assert first_res["doc_id"] == "70/2023/ND-CP"

        # Second call should retrieve from cache
        second_res = verify_vbpl_status("70/2023/ND-CP", memory_manager=self.memory)
        assert second_res["cached"] is True
        assert second_res["source"] == "statute_cache"
        assert second_res["status"] == "active"

    def test_search_gazette_tool(self) -> None:
        """Tests search_gazette returns matching documents."""
        results = search_gazette("ví điện tử", limit=3)
        assert len(results) > 0
        assert any(r.get("doc_id") == "52/2024/ND-CP" for r in results)

    def test_adk_tool_definitions(self) -> None:
        """Tests that tool definitions adhere to Google ADK schema."""
        assert VERIFY_VBPL_STATUS_TOOL.name == "verify_vbpl_status"
        assert callable(VERIFY_VBPL_STATUS_TOOL.func)
        assert "doc_id" in VERIFY_VBPL_STATUS_TOOL.parameters_schema["properties"]

        assert SEARCH_GAZETTE_TOOL.name == "search_gazette"
        assert callable(SEARCH_GAZETTE_TOOL.func)
        assert "query" in SEARCH_GAZETTE_TOOL.parameters_schema["properties"]
