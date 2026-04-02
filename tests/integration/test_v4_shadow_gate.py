"""Integration tests for v4 shadow/canary gate decisions."""

import pytest

from src.release.canary.gate import CanaryGate


@pytest.fixture(autouse=True)
def patch_ncbi_services() -> None:
    """Override integration autouse fixture to keep this test hermetic."""

    yield


@pytest.mark.integration
def test_canary_gate_blocks_when_red_flag_miss_exceeds_threshold() -> None:
    gate = CanaryGate(max_red_flag_miss_rate=0.01)
    decision = gate.evaluate({"red_flag_miss_rate": 0.03, "p95_ms": 4100})
    assert decision.allow is False
    assert decision.reason == "red_flag_miss_rate_exceeded"


@pytest.mark.integration
def test_canary_gate_blocks_when_p95_exceeds_threshold() -> None:
    gate = CanaryGate(max_red_flag_miss_rate=0.01, max_p95_ms=6000)
    decision = gate.evaluate({"red_flag_miss_rate": 0.005, "p95_ms": 6100})
    assert decision.allow is False
    assert decision.reason == "p95_ms_exceeded"


@pytest.mark.integration
def test_canary_gate_allows_when_metrics_hit_threshold_exactly() -> None:
    gate = CanaryGate(max_red_flag_miss_rate=0.01, max_p95_ms=6000)
    decision = gate.evaluate({"red_flag_miss_rate": 0.01, "p95_ms": 6000})
    assert decision.allow is True
    assert decision.reason == "within_thresholds"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("metrics", "expected_reason"),
    [
        ({"p95_ms": 4100}, "missing_red_flag_miss_rate"),
        ({"red_flag_miss_rate": 0.004}, "missing_p95_ms"),
        ({"red_flag_miss_rate": "0.004", "p95_ms": 4100}, "missing_red_flag_miss_rate"),
        ({"red_flag_miss_rate": float("nan"), "p95_ms": 4100}, "missing_red_flag_miss_rate"),
        ({"red_flag_miss_rate": -0.1, "p95_ms": 4100}, "missing_red_flag_miss_rate"),
        ({"red_flag_miss_rate": 0.004, "p95_ms": 0}, "missing_p95_ms"),
        ({"red_flag_miss_rate": 0.004, "p95_ms": -1}, "missing_p95_ms"),
        ({"red_flag_miss_rate": 0.004, "p95_ms": float("nan")}, "missing_p95_ms"),
        ({"red_flag_miss_rate": 0.004, "p95_ms": float("inf")}, "missing_p95_ms"),
    ],
)
def test_canary_gate_blocks_on_missing_or_invalid_metrics(
    metrics: dict[str, object],
    expected_reason: str,
) -> None:
    gate = CanaryGate(max_red_flag_miss_rate=0.01, max_p95_ms=6000)
    decision = gate.evaluate(metrics)
    assert decision.allow is False
    assert decision.reason == expected_reason
