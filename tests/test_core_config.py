"""Tests for configuration loading and system settings."""

from pathlib import Path

import pytest

from src.core.config import Settings, load_yaml_config
from src.core.exceptions import ConfigurationError


def test_default_settings():
    """Verify default settings values."""
    settings = Settings()
    assert settings.APP_NAME == "legalpilot-vn"
    assert settings.MAX_REFINE_LOOPS == 3
    assert settings.HUMAN_GATE_REQUIRE_TOKEN is True


def test_load_yaml_config_success(tmp_path: Path):
    """Verify loading a valid YAML file."""
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text("system:\n  app_name: 'test-app'\n", encoding="utf-8")

    data = load_yaml_config(yaml_file)
    assert data["system"]["app_name"] == "test-app"


def test_load_yaml_config_not_found():
    """Verify error raised when YAML file does not exist."""
    with pytest.raises(ConfigurationError):
        load_yaml_config("non_existent_file.yaml")


def test_system_certificates_are_opt_in(monkeypatch: pytest.MonkeyPatch):
    """The OS trust store is only injected when LEGALPILOT_USE_SYSTEM_CERTS is on."""
    import truststore

    from src.core.config import use_system_certificates

    calls: list[bool] = []
    monkeypatch.setattr(truststore, "inject_into_ssl", lambda: calls.append(True))

    assert use_system_certificates(Settings(LEGALPILOT_USE_SYSTEM_CERTS=False)) is False
    assert calls == []

    assert use_system_certificates(Settings(LEGALPILOT_USE_SYSTEM_CERTS=True)) is True
    assert calls == [True]


def test_system_certificates_missing_truststore(monkeypatch: pytest.MonkeyPatch):
    """A missing truststore package degrades to certifi instead of crashing."""
    import sys

    from src.core.config import use_system_certificates

    monkeypatch.setitem(sys.modules, "truststore", None)
    assert use_system_certificates(Settings(LEGALPILOT_USE_SYSTEM_CERTS=True)) is False
