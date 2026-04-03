"""Unit tests for TriNav v2 runtime type models."""

import pytest
from pydantic import ValidationError

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, RuntimeEvent


def test_execution_context_minimal_fields() -> None:
    ctx = ExecutionContext(
        request_id="r1",
        session_id="s1",
        text="发烧",
        image_base64=None,
        gps_lat=None,
        gps_lng=None,
        metadata={},
    )
    assert ctx.request_id == "r1"
    assert ctx.session_id == "s1"


def test_capability_result_contains_provenance() -> None:
    out = CapabilityResult(
        name="triage",
        success=True,
        payload={"triage_level": "URGENT"},
        provenance={"source": "llm", "model": "grok-4-1-fast-reasoning"},
        errors=[],
    )
    assert out.provenance["source"] == "llm"


def test_runtime_event_minimal_fields() -> None:
    event = RuntimeEvent(
        event_type="runtime_started",
        request_id="r1",
        session_id="s1",
    )
    assert event.event_type == "runtime_started"
    assert event.data == {}


@pytest.mark.parametrize("field_name", ["request_id", "session_id", "text"])
def test_execution_context_rejects_blank_required_strings(field_name: str) -> None:
    payload = {
        "request_id": "r1",
        "session_id": "s1",
        "text": "发烧",
        "image_base64": None,
        "gps_lat": None,
        "gps_lng": None,
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        ExecutionContext(**payload)


@pytest.mark.parametrize("field_name", ["event_type", "request_id", "session_id"])
def test_runtime_event_rejects_blank_required_strings(field_name: str) -> None:
    payload = {
        "event_type": "runtime_started",
        "request_id": "r1",
        "session_id": "s1",
    }
    payload[field_name] = ""

    with pytest.raises(ValidationError):
        RuntimeEvent(**payload)


def test_default_factory_isolation_for_mutable_fields() -> None:
    first = CapabilityResult(name="triage", success=True, payload={"triage_level": "URGENT"})
    second = CapabilityResult(name="triage", success=True, payload={"triage_level": "ROUTINE"})
    first_event = RuntimeEvent(event_type="runtime_started", request_id="r1", session_id="s1")
    second_event = RuntimeEvent(event_type="runtime_started", request_id="r2", session_id="s2")
    first_ctx = ExecutionContext(request_id="r1", session_id="s1", text="发烧")
    second_ctx = ExecutionContext(request_id="r2", session_id="s2", text="咳嗽")

    first.provenance["source"] = "llm"
    first_event.data["step"] = "start"
    first_ctx.metadata["trace"] = "t1"

    assert second.provenance == {}
    assert second_event.data == {}
    assert second_ctx.metadata == {}
