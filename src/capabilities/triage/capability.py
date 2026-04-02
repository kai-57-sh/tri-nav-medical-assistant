"""Triage capability for TriNav v3."""

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


async def red_flag_detector(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.red_flag_detector import red_flag_detector as _red_flag_detector

    return await _red_flag_detector(state)


async def triage_classifier(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.triage_classifier import triage_classifier as _triage_classifier

    return await _triage_classifier(state)


async def triage_merger(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.triage_merger import triage_merger as _triage_merger

    return await _triage_merger(state)


def _extract_symptom_schema_heuristic(text: str) -> dict[str, Any]:
    body_part = "未知"
    if any(token in text for token in ("胸", "胸口", "胸部")):
        body_part = "胸口"
    elif any(token in text for token in ("头", "头部")):
        body_part = "头部"
    elif any(token in text for token in ("腹", "肚子", "胃")):
        body_part = "腹部"

    symptoms: list[str] = []
    accompanying: list[str] = []
    if any(token in text for token in ("胸痛", "胸口痛", "胸闷", "压迫感", "剧痛", "疼痛")):
        symptoms.append("痛")
    if any(token in text for token in ("头痛", "头晕")):
        symptoms.append("头痛")
    if any(token in text for token in ("咳嗽",)):
        symptoms.append("咳嗽")
    if any(token in text for token in ("抽搐", "昏迷")):
        symptoms.append("抽搐")
    if any(token in text for token in ("出血", "大出血", "流血不止")):
        symptoms.append("大出血")
    if any(token in text for token in ("呼吸困难", "喘不过气", "窒息")):
        accompanying.append("呼吸困难")
    if any(token in text for token in ("发热", "发烧", "高热")):
        accompanying.append("发烧")
    if any(token in text for token in ("出汗", "冒冷汗")):
        accompanying.append("出汗")

    severity = "严重" if any(token in text for token in ("剧烈", "严重", "无法", "明显")) else "中度"
    if any(token in text for token in ("轻微", "稍微")):
        severity = "轻微"

    return {
        "body_part": body_part,
        "symptoms": symptoms or [text[:20]],
        "duration": None,
        "severity": severity,
        "accompanying_symptoms": accompanying,
        "onset": None,
    }


def _heuristic_triage(text: str) -> dict[str, Any]:
    emergency_tokens = (
        "呼吸困难",
        "喘不过气",
        "窒息",
        "胸痛",
        "大出血",
        "抽搐",
        "昏迷",
        "意识不清",
        "中毒",
        "中风",
    )
    urgent_tokens = (
        "高烧",
        "高热",
        "持续恶化",
        "无法进食",
        "无法活动",
        "剧烈",
        "严重",
    )
    self_care_tokens = (
        "轻微",
        "稍微",
        "好转",
        "缓解",
        "不严重",
    )

    if any(token in text for token in emergency_tokens):
        triage_level = "EMERGENCY"
        triage_reason = "检测到高风险症状，建议立即急诊评估"
        departments = ["急诊"]
        red_flags = ["如出现持续胸痛、呼吸困难或意识改变，请立即拨打急救电话。"]
    elif any(token in text for token in urgent_tokens):
        triage_level = "URGENT"
        triage_reason = "症状存在较高风险，建议尽快线下就医"
        departments = ["急诊", "内科"]
        red_flags = ["若症状快速加重，请立即急诊。"]
    elif any(token in text for token in self_care_tokens):
        triage_level = "SELF_CARE"
        triage_reason = "症状偏轻，可先居家观察并预约门诊复评"
        departments = ["全科"]
        red_flags = ["若症状加重或出现胸痛、呼吸困难，请立即急诊。"]
    else:
        triage_level = "ROUTINE"
        triage_reason = "当前信息未见明确紧急信号，建议常规门诊就诊"
        departments = ["全科", "内科"]
        red_flags = ["若出现呼吸困难、胸痛、意识改变，请立即急诊。"]

    excerpt = text.strip()[:20]
    possible_causes = [f"{excerpt}相关不适（疑似）"] if excerpt else ["症状相关不适（疑似）"]
    return {
        "llm_triage_level": triage_level,
        "llm_triage_reason": triage_reason,
        "llm_recommended_departments": departments,
        "llm_possible_causes": possible_causes,
        "llm_self_care_tips": ["记录症状变化并保持休息。"],
        "llm_red_flags": red_flags,
    }


def _node_timeout_seconds(context: ExecutionContext) -> float:
    override = context.metadata.get("node_timeout_seconds")
    if isinstance(override, (int, float)) and float(override) > 0:
        return float(override)
    if os.getenv("QWEN_API_KEY") == "test-key":
        return _TEST_NODE_TIMEOUT_SECONDS
    return _PROD_NODE_TIMEOUT_SECONDS


class TriageCapability:
    """Run rule-based + LLM-style triage merge pipeline for v3 integration."""

    name = "triage"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "triage"}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        state: dict[str, Any] = {
            "session_id": context.session_id,
            "text": context.text,
            "symptom_schema": _extract_symptom_schema_heuristic(context.text),
        }

        red_flag_state = await red_flag_detector(state)

        classifier_state: dict[str, Any]
        try:
            classifier_state = await asyncio.wait_for(
                triage_classifier(red_flag_state),
                timeout=_node_timeout_seconds(context),
            )
        except Exception as exc:
            logger.warning("triage_classifier_timeout_or_error", extra={"error": str(exc)})
            classifier_state = {**red_flag_state, **_heuristic_triage(context.text)}

        llm_triage_level = classifier_state.get("llm_triage_level")
        if not isinstance(llm_triage_level, str) or llm_triage_level not in _TRIAGE_LEVELS:
            classifier_state = {**red_flag_state, **_heuristic_triage(context.text)}

        merged_state = await triage_merger({**red_flag_state, **classifier_state})
        triage_level_raw = merged_state.get("triage_level")
        triage_level = triage_level_raw if isinstance(triage_level_raw, str) else "URGENT"

        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "triage_level": triage_level,
                "triage_signal": "triage_completed",
                "triage_reason": merged_state.get("triage_reason", ""),
                "recommended_departments": merged_state.get("recommended_departments", []),
                "possible_causes": merged_state.get("possible_causes", []),
                "self_care_tips": merged_state.get("self_care_tips", []),
                "red_flags": merged_state.get("red_flags", []),
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
                "triage_level": "SELF_CARE",
                "triage_signal": "triage_degraded",
                "triage_reason": _SAFE_BUSY_MESSAGE,
                "message": _SAFE_BUSY_MESSAGE,
            },
            provenance=provenance,
            errors=[reason],
        )
