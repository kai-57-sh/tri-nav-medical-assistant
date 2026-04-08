"""Tests for the checked-in environment template."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_TEMPLATE_PATH = REPO_ROOT / ".env.example"


def test_env_template_includes_current_runtime_flags():
    """The env template should document the current v3/v4 runtime controls."""
    env_template = ENV_TEMPLATE_PATH.read_text(encoding="utf-8")

    expected_keys = {
        "V2_RUNTIME_ENABLED=",
        "V2_SHADOW_COMPARE_ENABLED=",
        "V3_RUNTIME_ENABLED=",
        "V3_SHADOW_COMPARE_ENABLED=",
        "V3_LEGACY_FALLBACK_ENABLED=",
        "V3_TASK_COORDINATOR_ENABLED=",
        "V3_BUILTIN_PLUGINS_ENABLED=",
        "V3_PLUGIN_TRACE_ENABLED=",
        "V3_PLUGIN_MEDICAL_FOOTER_ENABLED=",
        "V4_CANARY_ENABLED=",
        "V4_GATE_MAX_RED_FLAG_MISS_RATE=",
        "V4_GATE_MAX_P95_MS=",
    }

    for key in expected_keys:
        assert key in env_template, f"missing {key} in .env.example"


def test_env_template_excludes_legacy_weather_keys():
    """The env template should not advertise removed weather env vars."""
    env_template = ENV_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "WEATHER_API_URL=" not in env_template
    assert "WEATHER_API_KEY=" not in env_template


def test_env_template_matches_current_public_defaults():
    """The env template should reflect the checked-in runtime defaults and supported knobs."""
    env_template = ENV_TEMPLATE_PATH.read_text(encoding="utf-8")

    expected_entries = {
        "DEBUG=false",
        "TRINAV_LOG_FILE=logs/trinav.log",
        "LANGCHAIN_TRACING_V2=false",
        "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317",
        "LLM_TIMEOUT=30",
        "AMAP_TIMEOUT=5",
        "NCBI_TIMEOUT=10",
        "MAX_TEXT_LENGTH=2000",
        "MAX_CLARIFICATION_ROUNDS=2",
        "MAX_CLARIFICATION_QUESTIONS=3",
    }

    for entry in expected_entries:
        assert entry in env_template, f"missing {entry} in .env.example"
