"""Pytest fixtures for LegalPilot-VN test suite."""

from pathlib import Path

import pytest

from src.memory.sqlite_manager import SQLiteMemoryManager
from src.security.sanitizer import InputSanitizer
from src.security.token_gate import HumanTokenGate


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


@pytest.fixture(autouse=True)
def _isolate_sqlite(tmp_path, monkeypatch):
    """Mọi SQLiteMemoryManager() không truyền path sẽ dùng DB tạm của test.

    Trước đây test ghi thẳng vào data/enterprise_compliance.db, nên cache trạng
    thái văn bản của test này rò sang test khác: chạy riêng thì xanh, chạy cả
    bộ thì đỏ (test_statute_status làm hỏng test_agents).
    """
    from src.memory import sqlite_manager as sm

    original = sm.SQLiteMemoryManager.__init__

    def patched(self, db_path: str = ""):
        original(self, db_path=str(tmp_path / "compliance.db"))

    monkeypatch.setattr(sm.SQLiteMemoryManager, "__init__", patched)


@pytest.fixture(autouse=True)
def _offline_network(monkeypatch):
    """Test không gọi vbpl.vn: bộ test phải tất định, không phụ thuộc mạng."""
    monkeypatch.setenv("LEGALPILOT_OFFLINE", "1")
