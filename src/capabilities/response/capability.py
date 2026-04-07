"""Response capability for TriNav v3."""

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


async def reasoning_verifier(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.reasoning_verifier import reasoning_verifier as _reasoning_verifier

    return await _reasoning_verifier(state)


def response_composer(state: dict[str, Any]) -> str:
    from src.chains.nodes.response_composer import compose_response

    return compose_response(state)


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


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _prefer_non_empty_dict(canonical: Any, fallback: Any) -> dict[str, Any] | None:
    if isinstance(canonical, dict) and canonical:
        return canonical
    if isinstance(fallback, dict):
        return fallback
    return None


def _triage_defaults(triage_level: str) -> tuple[list[str], str]:
    if triage_level == "EMERGENCY":
        return ["急诊"], "检测到高风险症状，建议立即急诊评估"
    if triage_level == "URGENT":
        return ["急诊", "内科"], "症状存在较高风险，建议尽快线下就医"
    if triage_level == "SELF_CARE":
        return ["全科"], "当前症状偏轻，可先居家观察并择期门诊复评"
    return ["全科", "内科"], "当前信息未见明确紧急信号，建议常规门诊就诊"


def _node_timeout_seconds(context: ExecutionContext) -> float:
    override = context.metadata.get("node_timeout_seconds")
    if isinstance(override, (int, float)) and float(override) > 0:
        return float(override)
    if os.getenv("QWEN_API_KEY") == "test-key":
        return _TEST_NODE_TIMEOUT_SECONDS
    return _PROD_NODE_TIMEOUT_SECONDS


def _build_response_state(context: ExecutionContext) -> dict[str, Any]:
    metadata = context.metadata if isinstance(context.metadata, dict) else {}
    triage_state = context.turn_state.triage
    evidence_state = context.turn_state.evidence
    navigation_state = context.turn_state.navigation

    triage_level = triage_state.triage_level or _triage_level_from_context(context)
    excerpt = context.text.strip()[:20]
    default_departments, default_reason = _triage_defaults(triage_level)
    departments = (
        _normalize_str_list(triage_state.recommended_departments)
        or _normalize_str_list(metadata.get("recommended_departments"))
        or default_departments
    )
    triage_reason = (
        triage_state.triage_reason.strip()
        if isinstance(triage_state.triage_reason, str) and triage_state.triage_reason.strip()
        else (
            metadata.get("triage_reason")
            if isinstance(metadata.get("triage_reason"), str) and str(metadata.get("triage_reason")).strip()
            else default_reason
        )
    )
    possible_causes = (
        _normalize_str_list(triage_state.possible_causes)
        or _normalize_str_list(metadata.get("possible_causes"))
        or ([f"{excerpt}相关不适（疑似）"] if excerpt else ["症状相关不适（疑似）"])
    )
    self_care_tips = (
        _normalize_str_list(triage_state.self_care_tips)
        or _normalize_str_list(metadata.get("self_care_tips"))
        or ["记录症状变化并保持休息。"]
    )
    red_flags = (
        _normalize_str_list(triage_state.red_flags)
        or _normalize_str_list(metadata.get("red_flags"))
        or ["若出现呼吸困难、胸痛、意识改变，请立即急诊。"]
    )
    navigation_result = _prefer_non_empty_dict(
        navigation_state.navigation_result,
        metadata.get("navigation_result"),
    )
    weather_alert = _prefer_non_empty_dict(
        navigation_state.weather_alert,
        metadata.get("weather_alert"),
    )
    evidence_selected = (
        _normalize_dict_list(evidence_state.evidence_selected)
        or _normalize_dict_list(metadata.get("evidence_selected"))
    )

    return {
        "session_id": context.session_id,
        "need_clarify": False,
        "triage_level": triage_level,
        "triage_reason": triage_reason,
        "recommended_departments": departments,
        "possible_causes": possible_causes,
        "self_care_tips": self_care_tips,
        "red_flags": red_flags,
        "navigation_result": navigation_result,
        "weather_alert": weather_alert,
        "evidence_selected": evidence_selected,
    }


class ResponseCapability:
    """Generate v3 medical response payload via verifier + composer pipeline."""

    name = "response"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "response"}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        state = _build_response_state(context)

        status = "final"
        generated_response: str
        try:
            verifier_state = await asyncio.wait_for(
                reasoning_verifier(state),
                timeout=_node_timeout_seconds(context),
            )
            status_raw = verifier_state.get("status")
            if isinstance(status_raw, str) and status_raw in {"final", "need_more_info"}:
                status = status_raw
            final_response_raw = verifier_state.get("final_response")
            if isinstance(final_response_raw, str) and final_response_raw.strip():
                generated_response = final_response_raw
            else:
                generated_response = response_composer(state)
        except Exception as exc:
            logger.warning("reasoning_verifier_timeout_or_error", extra={"error": str(exc)})
            generated_response = response_composer(state)

        response_text = f"已记录症状：{context.text[:80]}\n{generated_response}".strip()
        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": status,
                "response_signal": "response_ready",
                "response": response_text,
                "response_text": response_text,
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
                "status": "error",
                "response_signal": "response_error",
                "response": "",
                "response_text": "",
                "message": _SAFE_BUSY_MESSAGE,
            },
            provenance=provenance,
            errors=[reason],
        )
