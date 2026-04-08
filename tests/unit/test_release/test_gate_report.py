"""Tests for machine-readable canary gate reports."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.release.ops.gate_report import build_gate_report

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "scripts" / "release" / "check_canary_gate.py"


def test_build_gate_report_returns_exit_code_and_reason() -> None:
    """Gate reports should expose both the decision and a CLI-friendly exit code."""
    report = build_gate_report(
        metrics={"red_flag_miss_rate": 0.02, "p95_ms": 4200},
        max_red_flag_miss_rate=0.01,
        max_p95_ms=6000,
    )

    assert report["allow"] is False
    assert report["reason"] == "red_flag_miss_rate_exceeded"
    assert report["exit_code"] == 1


def test_check_canary_gate_cli_runs_from_repo_root(tmp_path: Path) -> None:
    """CLI should be runnable from the repo root exactly as documented."""
    metrics_path = tmp_path / "canary_ok.json"
    metrics_path.write_text(
        json.dumps({"red_flag_miss_rate": 0.002, "p95_ms": 4100}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(CLI_PATH), str(metrics_path), "0.01", "6000"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["allow"] is True
    assert payload["reason"] == "within_thresholds"
    assert payload["exit_code"] == 0
