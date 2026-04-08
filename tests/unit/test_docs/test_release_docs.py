"""Regression tests for release runbook and checklist docs."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK_PATH = REPO_ROOT / "docs" / "release" / "v3-cutover-runbook.md"
CHECKLIST_PATH = REPO_ROOT / "docs" / "release" / "v4-cutover-checklist.md"


def test_v3_cutover_runbook_exists_and_documents_current_flags() -> None:
    """The runbook should capture the current v3 cutover command and rollback inputs."""
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "bash scripts/release/run_cutover_checks.sh" in runbook
    assert "V3_RUNTIME_ENABLED=true" in runbook
    assert "V3_TASK_COORDINATOR_ENABLED=true" in runbook
    assert "V3_LEGACY_FALLBACK_ENABLED=true" in runbook
    assert "V4_CANARY_ENABLED=true" in runbook
    assert "1% -> 5% -> 20% -> 50% -> 100%" in runbook
    assert "red_flag_miss_rate > 0.01" in runbook


def test_v4_cutover_checklist_references_runbook_and_cutover_script() -> None:
    """The checklist should point operators to the runbook and pre-cutover script."""
    checklist = CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "docs/release/v3-cutover-runbook.md" in checklist
    assert "bash scripts/release/run_cutover_checks.sh" in checklist
    assert "V3_RUNTIME_ENABLED=true" in checklist
    assert "V3_LEGACY_FALLBACK_ENABLED=true" in checklist
    assert "V4_RUNTIME_ENABLED" not in checklist
