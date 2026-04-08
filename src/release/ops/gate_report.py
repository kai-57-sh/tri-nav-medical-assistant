"""Machine-readable canary gate reporting helpers."""

from __future__ import annotations

from typing import Any

from src.release.canary.gate import CanaryGate


def build_gate_report(
    *,
    metrics: dict[str, Any],
    max_red_flag_miss_rate: float,
    max_p95_ms: int,
) -> dict[str, object]:
    """Return an auditable canary decision payload for automation."""

    decision = CanaryGate(
        max_red_flag_miss_rate=max_red_flag_miss_rate,
        max_p95_ms=max_p95_ms,
    ).evaluate(metrics)
    return {
        "allow": decision.allow,
        "reason": decision.reason,
        "metrics": metrics,
        "exit_code": 0 if decision.allow else 1,
    }
