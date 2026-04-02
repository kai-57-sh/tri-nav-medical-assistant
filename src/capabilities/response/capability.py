"""Response capability for TriNav v3."""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue

_SOURCE = "v3_medical_pipeline"
_SAFE_BUSY_MESSAGE = "服务繁忙，请尽快线下就医"
_NODE_TIMEOUT_SECONDS = 0.35


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
    return "ROUTINE"


def _build_response_state(context: ExecutionContext) -> dict[str, Any]:
    triage_level = _heuristic_triage_level(context.text)
    excerpt = context.text.strip()[:20]
    if triage_level == "EMERGENCY":
        departments = ["急诊"]
        reason = "检测到高风险症状，建议立即急诊评估"
    elif triage_level == "URGENT":
        departments = ["急诊", "内科"]
        reason = "症状存在较高风险，建议尽快线下就医"
    else:
        departments = ["全科", "内科"]
        reason = "当前信息未见明确紧急信号，建议常规门诊就诊"

    return {
        "session_id": context.session_id,
        "need_clarify": False,
        "triage_level": triage_level,
        "triage_reason": reason,
        "recommended_departments": departments,
        "possible_causes": [f"{excerpt}相关不适（疑似）"] if excerpt else ["症状相关不适（疑似）"],
        "self_care_tips": ["记录症状变化并保持休息。"],
        "red_flags": ["若出现呼吸困难、胸痛、意识改变，请立即急诊。"],
        "navigation_result": None,
        "weather_alert": None,
        "evidence_selected": [],
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
                timeout=_NODE_TIMEOUT_SECONDS,
            )
            status_raw = verifier_state.get("status")
            if isinstance(status_raw, str) and status_raw in {"final", "need_more_info"}:
                status = status_raw
            final_response_raw = verifier_state.get("final_response")
            if isinstance(final_response_raw, str) and final_response_raw.strip():
                generated_response = final_response_raw
            else:
                generated_response = response_composer(state)
        except Exception:
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
