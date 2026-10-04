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

    def test_env_target_query_configuration(self, monkeypatch: Any) -> None:
        """Tests that VBPL_TARGET_QUERY / VBPL_SEARCH_URL env vars configure search query URL."""
        from unittest.mock import MagicMock

        captured_urls: list[str] = []

        def mock_get(client_self: Any, url: str, **kwargs: Any) -> Any:
            captured_urls.append(url)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.url = url
            mock_resp.text = (
                "<html><body><a class='title'>Văn bản 88/2024/ND-CP</a>Còn hiệu lực</body></html>"
            )
            return mock_resp

        import httpx

        monkeypatch.setattr(httpx.Client, "get", mock_get)
        monkeypatch.setenv(
            "VBPL_TARGET_QUERY", "https://custom-mock-portal.gov.vn/timkiem?q={keyword}"
        )

        res = verify_vbpl_status("88/2024/ND-CP", memory_manager=self.memory, force_refresh=True)
        assert len(captured_urls) == 1
        assert captured_urls[0] == "https://custom-mock-portal.gov.vn/timkiem?q=88/2024/ND-CP"
        assert res["status"] == "active"
        assert "88/2024/ND-CP" in res["title"]

    def test_html_parsed_with_mock_portal(self, monkeypatch: Any) -> None:
        """Tests HTML parsing leveraging BeautifulSoup and HTMLParsed metadata."""
        from unittest.mock import MagicMock

        mock_html = """<!DOCTYPE html>
        <html>
        <head><title>VBPL Search Result</title></head>
        <body>
            <div class="header">
                <a class="title" href="/detail/99">Nghị định 99/2024/NĐ-CP Quy định thanh toán điện tử</a>
            </div>
            <div class="meta">
                <p>Số: 99/2024/NĐ-CP</p>
                <p>Trạng thái: Hết hiệu lực</p>
                <p>Ngày có hiệu lực: ngày 01 tháng 07 năm 2024</p>
            </div>
        </body>
        </html>"""

        def mock_get(client_self: Any, url: str, **kwargs: Any) -> Any:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.url = url
            mock_resp.text = mock_html
            return mock_resp

        import httpx

        monkeypatch.setattr(httpx.Client, "get", mock_get)

        res = verify_vbpl_status("99/2024/ND-CP", memory_manager=self.memory, force_refresh=True)
        assert res["doc_id"] == "99/2024/ND-CP"
        assert res["status"] == "expired"
        assert res["is_in_force"] is False
        assert "Nghị định 99/2024/NĐ-CP" in res["title"]
        assert res["source"] == "vbpl.vn"
