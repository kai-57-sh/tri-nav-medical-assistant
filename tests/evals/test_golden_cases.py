"""Eval gate tests for golden-case fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from src.interfaces.api.shadow_compare_v3 import compare_v1_v3

_ALLOWED_TRIAGE = {"EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"}


def _load_rows() -> list[dict[str, Any]]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "golden_cases.json"
    assert fixture_path.exists()
    rows = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    return rows


def _heuristic_triage(text: str) -> str:
    """Deterministic, input-driven triage heuristic for eval smoke checks."""

    if any(token in text for token in ("呼吸困难", "胸痛", "意识模糊", "肢体无力", "出冷汗")):
        return "EMERGENCY"
    if any(token in text for token in ("剧烈腹痛", "头痛伴呕吐", "反复咳嗽", "咳嗽两周")):
        return "URGENT"
    if any(token in text for token in ("皮疹", "咽痛", "擦伤", "红肿")):
        return "ROUTINE"
    return "SELF_CARE"


@pytest.mark.eval
def test_golden_cases_fixture_contract_and_rows() -> None:
    """Golden fixture must provide required row schema and enough cases."""

    rows = _load_rows()
    assert len(rows) >= 10
    for row in rows:
        assert isinstance(row, dict)
        assert "input" in row
        assert "expect_triage" in row
        assert isinstance(row["input"], str)
        assert row["input"].strip()
        assert row["expect_triage"] in _ALLOWED_TRIAGE


@pytest.mark.eval
@pytest.mark.asyncio
async def test_golden_cases_compare_helper_smoke() -> None:
    """Fixture rows should exercise compare helper with both match and mismatch cases."""
    rows = _load_rows()
    saw_mismatch = False

    for row in rows:
        expected_triage = row["expect_triage"]
        predicted_triage = _heuristic_triage(row["input"])

        async def v1_runner(_: dict[str, object]) -> dict[str, object]:
            return {"status": "final", "triage_level": expected_triage}

        async def v3_runner(_: dict[str, object]) -> dict[str, object]:
            return {"status": "final", "triage_level": predicted_triage}

        result = await compare_v1_v3(
            {"text": row["input"]},
            v1_runner=v1_runner,
            v3_runner=v3_runner,
        )
        assert result["same_status"] is True
        assert result["same_triage"] is (expected_triage == predicted_triage)
        assert result["v1"]["triage_level"] == expected_triage
        assert result["v3"]["triage_level"] == predicted_triage
        if expected_triage != predicted_triage:
            saw_mismatch = True

    assert saw_mismatch is True
