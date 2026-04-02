"""Navigation capability for TriNav v3."""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue

_SOURCE = "v3_medical_pipeline"
_SAFE_BUSY_MESSAGE = "服务繁忙，请尽快线下就医"
_NODE_TIMEOUT_SECONDS = 0.35


async def navigator(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.navigator import navigator as _navigator

    return await _navigator(state)


async def weather_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.weather_fetcher import weather_fetcher as _weather_fetcher

    return await _weather_fetcher(state)


def _heuristic_triage_level(text: str) -> str:
    if any(token in text for token in ("呼吸困难", "胸痛", "抽搐", "昏迷", "大出血", "中毒")):
        return "EMERGENCY"
    if any(token in text for token in ("严重", "剧烈", "高烧", "高热", "持续恶化")):
        return "URGENT"
    return "ROUTINE"


class NavigationCapability:
    """Run hospital navigation + weather warning pipeline for v3."""

    name = "navigation"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "navigation"}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        state: dict[str, Any] = {
            "session_id": context.session_id,
            "triage_level": _heuristic_triage_level(context.text),
            "gps_lat": context.gps_lat,
            "gps_lng": context.gps_lng,
            "case_domain": None,
            "recommended_departments": ["全科", "内科"],
        }

        try:
            navigation_state = await asyncio.wait_for(
                navigator(state),
                timeout=_NODE_TIMEOUT_SECONDS,
            )
        except Exception:
            navigation_state = {**state, "navigation_result": None}

        try:
            weather_state = await asyncio.wait_for(
                weather_fetcher(navigation_state),
                timeout=_NODE_TIMEOUT_SECONDS,
            )
        except Exception:
            weather_state = {**navigation_state, "weather_alert": None}

        navigation_result = weather_state.get("navigation_result")
        weather_alert = weather_state.get("weather_alert")

        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "navigation_signal": "routing_prepared" if navigation_result is not None else "routing_unavailable",
                "destination_type": "clinical_guidance",
                "navigation_result": navigation_result,
                "weather_alert": weather_alert,
            },
            provenance={
                "source": _SOURCE,
                "capability_version": self.version,
            },
        )

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        _ = context
        provenance: dict[str, JSONValue] = {
            "source": _SOURCE,
            "capability_version": self.version,
        }
        if error is not None:
            provenance["error_type"] = type(error).__name__
        return CapabilityResult(
            name=self.name,
            success=False,
            payload={
                "status": "degraded",
                "navigation_signal": "unavailable",
                "destination_type": "clinical_guidance",
                "navigation_result": None,
                "weather_alert": None,
                "message": _SAFE_BUSY_MESSAGE,
            },
            provenance=provenance,
            errors=[reason],
        )
