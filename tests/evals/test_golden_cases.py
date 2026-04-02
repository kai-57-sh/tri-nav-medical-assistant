"""Eval gate tests for golden-case fixtures."""

import json
from pathlib import Path

import pytest


@pytest.mark.eval
def test_golden_cases_fixture_has_minimum_rows() -> None:
    """Golden fixture must exist and provide enough rows for gate scaffolding."""

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "golden_cases.json"
    assert fixture_path.exists()
    rows = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert len(rows) >= 10
