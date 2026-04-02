"""Tests for v2/v4 runtime and gate settings."""
import pytest
from pydantic import ValidationError

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


@pytest.mark.parametrize("value", ["-0.1", "1.1"])
def test_v4_gate_red_flag_miss_rate_rejects_out_of_range_env(monkeypatch, value):
    """v4 red-flag miss rate must stay within [0, 1]."""
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("V4_GATE_MAX_RED_FLAG_MISS_RATE", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_v4_gate_p95_rejects_non_positive_env(monkeypatch):
    """v4 p95 threshold must be positive."""
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("V4_GATE_MAX_P95_MS", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_v4_gate_thresholds_load_from_valid_env(monkeypatch):
    """v4 gate thresholds should load from valid env values."""
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("V4_GATE_MAX_RED_FLAG_MISS_RATE", "0.02")
    monkeypatch.setenv("V4_GATE_MAX_P95_MS", "7000")

    settings = Settings(_env_file=None)

    assert settings.v4_gate_max_red_flag_miss_rate == 0.02
    assert settings.v4_gate_max_p95_ms == 7000
