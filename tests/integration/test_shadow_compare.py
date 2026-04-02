"""Integration tests for v1/v2 shadow compare helper."""

import pytest

from src.interfaces.api.shadow_compare import compare_v1_v2


@pytest.fixture(autouse=True)
def patch_ncbi_services() -> None:
    """Override integration autouse fixture to keep this test hermetic."""

    yield


@pytest.mark.asyncio
@pytest.mark.integration
async def test_compare_v1_v2_returns_diff_summary_contract() -> None:
    """compare_v1_v2 returns expected keys and comparison values."""

    async def v1_runner(payload: dict[str, object]) -> dict[str, object]:
        assert payload["text"] == "left arm rash"
        return {"status": "final", "triage_level": "ROUTINE"}

    async def v2_runner(payload: dict[str, object]) -> dict[str, object]:
        assert payload["text"] == "left arm rash"
        return {"status": "need_more_info", "triage_level": "URGENT"}

    result = await compare_v1_v2({"text": "left arm rash"}, v1_runner=v1_runner, v2_runner=v2_runner)

    assert set(result.keys()) == {"same_status", "same_triage", "v1", "v2"}
    assert result["same_status"] is False
    assert result["same_triage"] is False
    assert result["v1"] == {"status": "final", "triage_level": "ROUTINE"}
    assert result["v2"] == {"status": "need_more_info", "triage_level": "URGENT"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_compare_v1_v2_marks_matches_when_outputs_align() -> None:
    """compare_v1_v2 marks both comparisons true when normalized fields match."""

    async def v1_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE", "extra": "ignored"}

    async def v2_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE"}

    result = await compare_v1_v2({"text": "same"}, v1_runner=v1_runner, v2_runner=v2_runner)

    assert result["same_status"] is True
    assert result["same_triage"] is True
    assert result["v1"] == {"status": "final", "triage_level": "ROUTINE"}
    assert result["v2"] == {"status": "final", "triage_level": "ROUTINE"}
