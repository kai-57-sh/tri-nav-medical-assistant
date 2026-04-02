"""Unit tests for TriNav v2 runtime type models."""

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


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
        provenance={"source": "llm", "model": "qwen-plus"},
        errors=[],
    )
    assert out.provenance["source"] == "llm"
