"""Regression tests for public compat-route documentation."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"
API_REFERENCE_PATH = REPO_ROOT / "docs" / "API_REFERENCE.md"
DEVELOPER_GUIDE_PATH = REPO_ROOT / "docs" / "DEVELOPER_GUIDE.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_section(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def test_readme_uses_generic_setup_path_and_compat_response_shape():
    """README examples should match the public compat contract."""
    readme = _read(README_PATH)
    triage_section = _extract_section(readme, "### Text-Only Triage (US1)", "### With GPS Navigation (US3)")

    assert "cd TriNav" in readme
    assert "cd /AII-wuqi/" not in readme
    assert '"output": {' in triage_section
    assert '"metadata": {' in triage_section
    assert '"runtime_mode": "v3"' in triage_section


def test_api_reference_matches_public_compat_fields_and_status_codes():
    """API reference should only advertise the current compat payload and HTTP behavior."""
    api_reference = _read(API_REFERENCE_PATH)
    request_section = _extract_section(
        api_reference,
        "#### 4.1.1 请求参数",
        "#### 4.1.2 请求示例",
    )
    response_section = _extract_section(
        api_reference,
        "#### 4.1.3 响应参数",
        "#### 4.1.4 响应示例",
    )
    status_section = _extract_section(
        api_reference,
        "### 6.1 HTTP 状态码",
        "### 6.2 业务错误码",
    )
    quick_table_section = _extract_section(
        api_reference,
        "### A. 状态码速查表",
        "### B. triage_level 枚举值",
    )

    assert "仍可用" not in request_section
    assert "`gps_lat`" in request_section
    assert "`gps_lng`" in request_section
    assert "别名字段会被忽略" in request_section

    expected_fields = {
        "`status`",
        "`session_id`",
        "`trace_id`",
        "`response`",
        "`safety`",
        "`runtime_events`",
        "`provenance`",
        "`trace`",
        "`triage_level`",
        "`recommended_departments`",
        "`possible_causes`",
        "`red_flags`",
        "`disclaimer`",
        "`error_message`",
    }
    removed_fields = {
        "`triage_reason`",
        "`triage_source`",
        "`self_care_tips`",
        "`clarify_questions`",
        "`navigation`",
        "`evidence`",
        "`weather_alert`",
        "`visual_findings`",
        "`turn_count`",
    }

    for field in expected_fields:
        assert field in response_section
    for field in removed_fields:
        assert field not in response_section

    assert "| 422 |" in status_section
    assert "| 503 |" in status_section
    assert "| 400 |" not in status_section
    assert "POST /assistant/invoke" in status_section
    assert "output.status=error" in status_section

    assert "| 422 |" in quick_table_section
    assert "| 503 |" in quick_table_section
    assert "| 400 |" not in quick_table_section


def test_developer_guide_otlp_example_matches_env_template():
    """The developer guide should use the same OTLP endpoint example as the env template."""
    developer_guide = _read(DEVELOPER_GUIDE_PATH)
    observability_section = _extract_section(
        developer_guide,
        "# === 可观测性 ===",
        "# === 超时（秒） ===",
    )

    assert "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317" in observability_section
    assert "4318" not in observability_section
