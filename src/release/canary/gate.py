"""Canary gate decision logic for v4 release rollout."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class CanaryGateDecision:
    """Immutable canary gate decision result."""

    allow: bool
    reason: str


class CanaryGate:
    """Evaluate rollout safety based on shadow/canary metrics."""

    def __init__(
        self,
        *,
        max_red_flag_miss_rate: float,
        max_p95_ms: int = 6000,
    ) -> None:
        self.max_red_flag_miss_rate = max_red_flag_miss_rate
        self.max_p95_ms = max_p95_ms

    def evaluate(self, metrics: Mapping[str, Any]) -> CanaryGateDecision:
        """Return allow/block decision with an auditable reason code."""

        red_flag_miss_rate = metrics.get("red_flag_miss_rate")
        p95_ms = metrics.get("p95_ms")

        if not _is_valid_red_flag_miss_rate(red_flag_miss_rate):
            return CanaryGateDecision(allow=False, reason="missing_red_flag_miss_rate")
        if not _is_valid_p95_ms(p95_ms):
            return CanaryGateDecision(allow=False, reason="missing_p95_ms")

        red_flag_miss_rate_value = cast(float, red_flag_miss_rate)
        p95_ms_value = cast(float, p95_ms)

        if red_flag_miss_rate_value > self.max_red_flag_miss_rate:
            return CanaryGateDecision(allow=False, reason="red_flag_miss_rate_exceeded")
        if p95_ms_value > self.max_p95_ms:
            return CanaryGateDecision(allow=False, reason="p95_ms_exceeded")

        return CanaryGateDecision(allow=True, reason="within_thresholds")


def _is_number(value: Any) -> bool:
    """Return True when value is int/float but not bool."""

    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _is_valid_red_flag_miss_rate(value: Any) -> bool:
    """Return True when red-flag miss rate is finite and within [0, 1]."""

    return _is_number(value) and 0.0 <= value <= 1.0


def _is_valid_p95_ms(value: Any) -> bool:
    """Return True when p95 latency is finite and strictly positive."""

    return _is_number(value) and value > 0
