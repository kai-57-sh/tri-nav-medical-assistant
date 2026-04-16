"""Navigation capability for TriNav v3."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue
from src.utils.logging_config import get_logger

_SOURCE = "v3_medical_pipeline"
_SAFE_BUSY_MESSAGE = "服务繁忙，请尽快线下就医"
_PROD_NODE_TIMEOUT_SECONDS = 3.0
_TEST_NODE_TIMEOUT_SECONDS = 0.35
_TRIAGE_LEVELS = frozenset({"EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"})
logger = get_logger(__name__)


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
    if any(token in text for token in ("轻微", "稍微", "好转", "缓解", "不严重")):
        return "SELF_CARE"
    return "ROUTINE"


def _triage_level_from_context(context: ExecutionContext) -> str:
    metadata = context.metadata if isinstance(context.metadata, dict) else {}
    raw = metadata.get("triage_level")
    if isinstance(raw, str) and raw in _TRIAGE_LEVELS:
        return raw
    return _heuristic_triage_level(context.text)


def _default_departments(triage_level: str) -> list[str]:
    if triage_level == "EMERGENCY":
        return ["急诊"]
    if triage_level == "URGENT":
        return ["急诊", "内科"]
    if triage_level == "SELF_CARE":
        return ["全科"]
    return ["全科", "内科"]


def _node_timeout_seconds(context: ExecutionContext) -> float:
    override = context.metadata.get("node_timeout_seconds")
    if isinstance(override, (int, float)) and float(override) > 0:
        return float(override)
    if os.getenv("QWEN_API_KEY") == "test-key":
        return _TEST_NODE_TIMEOUT_SECONDS
    return _PROD_NODE_TIMEOUT_SECONDS


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
        triage_level = _triage_level_from_context(context)
        state: dict[str, Any] = {
            "session_id": context.session_id,
            "triage_level": triage_level,
            "gps_lat": context.gps_lat,
            "gps_lng": context.gps_lng,
            "case_domain": None,
            "recommended_departments": _default_departments(triage_level),
        }

        try:
            navigation_state = await asyncio.wait_for(
                navigator(state),
                timeout=_node_timeout_seconds(context),
            )
        except Exception as exc:
            logger.warning("navigator_timeout_or_error", extra={"error": str(exc)})
            navigation_state = {**state, "navigation_result": None}

        try:
            weather_state = await asyncio.wait_for(
                weather_fetcher(navigation_state),
                timeout=_node_timeout_seconds(context),
            )
        except Exception as exc:
            logger.warning("weather_fetcher_timeout_or_error", extra={"error": str(exc)})
            weather_state = {**navigation_state, "weather_alert": None}

        navigation_result = weather_state.get("navigation_result")
        weather_alert = weather_state.get("weather_alert")
        navigation_result_patch = navigation_result if isinstance(navigation_result, dict) else None
        weather_alert_patch = weather_alert if isinstance(weather_alert, dict) else None

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
            state_patch={
                "navigation": {
                    "navigation_result": navigation_result_patch,
                    "weather_alert": weather_alert_patch,
                }
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
