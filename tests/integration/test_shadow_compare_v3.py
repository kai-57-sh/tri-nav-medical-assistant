"""Integration tests for v1/v3 shadow compare helper."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.interfaces.api.shadow_compare_v3 as shadow_compare_v3_api
from src.interfaces.api.shadow_compare_v3 import compare_v1_v3


@pytest.fixture(autouse=True)
def patch_ncbi_services() -> None:
    """Override integration autouse fixture to keep this test hermetic."""

    yield


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime_enabled: bool,
    shadow_enabled: bool,
) -> TestClient:
    """Build app with patched feature flags for route-level behavior tests."""

    monkeypatch.setattr(
        shadow_compare_v3_api,
        "get_settings",
        lambda: SimpleNamespace(
            v3_runtime_enabled=runtime_enabled,
            v3_shadow_compare_enabled=shadow_enabled,
        ),
    )
    app = FastAPI()
    app.include_router(shadow_compare_v3_api.router)
    return TestClient(app)


@pytest.mark.integration
def test_shadow_compare_v3_enabled_returns_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route should return compare contract when v3 shadow feature flags are enabled."""

    async def fake_v1(payload: dict[str, object]) -> dict[str, object]:
        assert payload["text"] == "arm pain"
        return {"status": "final", "triage_level": "ROUTINE"}

    async def fake_v3(payload: dict[str, object]) -> dict[str, object]:
        assert payload["text"] == "arm pain"
        return {"status": "need_more_info", "triage_level": "URGENT"}

    monkeypatch.setattr(shadow_compare_v3_api, "_run_v1", fake_v1)
    monkeypatch.setattr(shadow_compare_v3_api, "_run_v3", fake_v3)
    client = _build_client(monkeypatch, runtime_enabled=True, shadow_enabled=True)

    response = client.post("/assistant/v3/shadow/compare", json={"text": "arm pain"})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {"same_status", "same_triage", "v1", "v3"}
    assert body["same_status"] is False
    assert body["same_triage"] is False
    assert body["v1"]["status"] == "final"
    assert body["v3"]["status"] == "need_more_info"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_compare_v1_v3_marks_matches_when_outputs_align() -> None:
    """compare_v1_v3 marks both comparisons true when normalized fields match."""

    async def v1_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE", "extra": "ignored"}

    async def v3_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE"}

    result = await compare_v1_v3({"text": "same"}, v1_runner=v1_runner, v3_runner=v3_runner)

    assert result["same_status"] is True
    assert result["same_triage"] is True
    assert result["v1"]["status"] == "final"
    assert result["v1"]["triage_level"] == "ROUTINE"
    assert result["v1"]["failed"] is False
    assert result["v3"]["status"] == "final"
    assert result["v3"]["triage_level"] == "ROUTINE"
    assert result["v3"]["failed"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_compare_v1_v3_one_runner_raises_forces_non_match() -> None:
    """A runner failure should be surfaced and force compare mismatch."""

    async def v1_runner(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("v1 boom")

    async def v3_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE"}

    result = await compare_v1_v3({"text": "x"}, v1_runner=v1_runner, v3_runner=v3_runner)

    assert result["same_status"] is False
    assert result["same_triage"] is False
    assert result["v1"]["failed"] is True
    assert result["v1"]["error_type"] == "RuntimeError"
    assert result["v1"]["error_message"] == "v1 boom"
    assert result["v3"]["failed"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_compare_v1_v3_invalid_payload_forces_non_match() -> None:
    """Invalid runner payload should be marked and force compare mismatch."""

    async def v1_runner(_: dict[str, object]) -> dict[str, object]:
        return {"status": "final", "triage_level": "ROUTINE"}

    async def v3_runner(_: dict[str, object]) -> object:
        return {"triage_level": "ROUTINE"}  # missing status -> invalid payload

    result = await compare_v1_v3({"text": "x"}, v1_runner=v1_runner, v3_runner=v3_runner)

    assert result["same_status"] is False
    assert result["same_triage"] is False
    assert result["v1"]["invalid_payload"] is False
    assert result["v3"]["invalid_payload"] is True
    assert result["v3"]["error_type"] == "InvalidPayload"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("runtime_enabled", "shadow_enabled"),
    [(False, True), (True, False), (False, False)],
)
def test_shadow_compare_v3_disabled_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    runtime_enabled: bool,
    shadow_enabled: bool,
) -> None:
    """Route should be hidden unless both v3 feature flags are enabled."""

    client = _build_client(
        monkeypatch,
        runtime_enabled=runtime_enabled,
        shadow_enabled=shadow_enabled,
    )

    response = client.post("/assistant/v3/shadow/compare", json={"text": "arm pain"})

    assert response.status_code == 404
    assert response.json() == {"detail": "shadow_compare_disabled"}
