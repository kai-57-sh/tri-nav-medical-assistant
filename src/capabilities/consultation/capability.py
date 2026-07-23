"""Consultation capability for TriNav v3."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue
from src.utils.logging_config import get_logger

_SOURCE = "v3_medical_pipeline"
_SAFE_BUSY_MESSAGE = "服务繁忙，请尽快线下就医"
_PROD_NODE_TIMEOUT_SECONDS = float(os.getenv("TRINAV_NODE_TIMEOUT_SECONDS", "25.0"))
_TEST_NODE_TIMEOUT_SECONDS = 0.35
logger = get_logger(__name__)


async def clinical_extractor(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.clinical_extractor import clinical_extractor as _clinical_extractor

    return await _clinical_extractor(state)


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
    if any(token in text for token in ("胸痛", "胸口痛", "胸闷", "疼痛", "剧痛")):
        symptoms.append("痛")
    if any(token in text for token in ("头痛",)):
        symptoms.append("头痛")
    if any(token in text for token in ("咳嗽",)):
        symptoms.append("咳嗽")
    if any(token in text for token in ("发热", "发烧", "高热")):
        accompanying.append("发烧")
    if any(token in text for token in ("呼吸困难", "喘不过气", "气促")):
        accompanying.append("呼吸困难")

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


def _build_summary(text: str, symptom_schema: dict[str, Any]) -> str:
    body_part = symptom_schema.get("body_part")
    symptoms = symptom_schema.get("symptoms")
    severity = symptom_schema.get("severity")

    parts: list[str] = []
    if isinstance(body_part, str) and body_part:
        parts.append(f"部位：{body_part}")
    if isinstance(symptoms, list) and symptoms:
        parts.append("症状：" + "、".join(str(item) for item in symptoms[:3]))
    if isinstance(severity, str) and severity:
        parts.append(f"程度：{severity}")

    if parts:
        return "；".join(parts)
    return text[:120]


def _node_timeout_seconds(context: ExecutionContext) -> float:
    override = context.metadata.get("node_timeout_seconds")
    if isinstance(override, (int, float)) and float(override) > 0:
        return float(override)
    if os.getenv("QWEN_API_KEY") == "test-key":
        return _TEST_NODE_TIMEOUT_SECONDS
    return _PROD_NODE_TIMEOUT_SECONDS


class ConsultationCapability:
    """Produce intake summary and consultation status for downstream triage."""

    name = "consultation"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "intake"}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        state: dict[str, Any] = {
            "session_id": context.session_id,
            "text": context.text,
        }

        symptom_schema: dict[str, Any] | None = None
        try:
            extractor_result = await asyncio.wait_for(
                clinical_extractor(state),
                timeout=_node_timeout_seconds(context),
            )
            candidate = extractor_result.get("symptom_schema")
            if isinstance(candidate, dict):
                symptom_schema = candidate
        except Exception as exc:
            logger.warning("consultation_fallback_to_heuristic", extra={"error": str(exc)})
            symptom_schema = None

        if symptom_schema is None:
            symptom_schema = _extract_symptom_schema_heuristic(context.text)

        summary = _build_summary(context.text, symptom_schema)
        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "summary": summary,
                "consultation_signal": "intake_complete",
            },
            state_patch={
                "consultation": {
                    "summary": summary,
                    "symptom_schema": symptom_schema,
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
                "summary": "",
                "consultation_signal": "consultation_degraded",
                "message": _SAFE_BUSY_MESSAGE,
            },
            provenance=provenance,
            errors=[reason],
        )
