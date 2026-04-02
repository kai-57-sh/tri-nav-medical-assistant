"""Tests for v2 runtime settings flags."""
from src.config.settings import Settings


def test_v2_runtime_flag_defaults_false(monkeypatch):
    """v2 flags should default to False when not set in env."""
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.delenv("V2_RUNTIME_ENABLED", raising=False)
    monkeypatch.delenv("V2_SHADOW_COMPARE_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.v2_runtime_enabled is False
    assert settings.v2_shadow_compare_enabled is False


def test_v2_runtime_flag_from_env(monkeypatch):
    """v2 flags should load from environment variables."""
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("V2_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("V2_SHADOW_COMPARE_ENABLED", "true")

    settings = Settings(_env_file=None)

    assert settings.v2_runtime_enabled is True
    assert settings.v2_shadow_compare_enabled is True
