"""Evidence capability for TriNav v3."""

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
logger = get_logger(__name__)


async def ncbi_query_builder(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.ncbi_query_builder import ncbi_query_builder as _ncbi_query_builder

    return await _ncbi_query_builder(state)


async def ncbi_retriever_tool(state: dict[str, Any]) -> dict[str, Any]:
    from src.chains.nodes.ncbi_retriever_tool import ncbi_retriever_tool as _ncbi_retriever_tool

    return await _ncbi_retriever_tool(state)


def _extract_symptom_schema_heuristic(text: str) -> dict[str, Any]:
    body_part = "未知"
    if any(token in text for token in ("胸", "胸口", "胸部")):
        body_part = "胸口"
    elif any(token in text for token in ("头", "头部")):
        body_part = "头部"
    elif any(token in text for token in ("腹", "肚子", "胃")):
        body_part = "腹部"

    symptoms: list[str] = []
    if any(token in text for token in ("痛", "疼")):
        symptoms.append("疼痛")
    if "咳嗽" in text:
        symptoms.append("咳嗽")
    if any(token in text for token in ("发热", "发烧")):
        symptoms.append("发烧")
    if not symptoms:
        symptoms.append(text[:20])

    return {
        "body_part": body_part,
        "symptoms": symptoms,
        "duration": None,
        "severity": "中度",
        "accompanying_symptoms": [],
        "onset": None,
    }


def _node_timeout_seconds(context: ExecutionContext) -> float:
    override = context.metadata.get("node_timeout_seconds")
    if isinstance(override, (int, float)) and float(override) > 0:
        return float(override)
    if os.getenv("QWEN_API_KEY") == "test-key":
        return _TEST_NODE_TIMEOUT_SECONDS
    return _PROD_NODE_TIMEOUT_SECONDS


def _external_tools_enabled(context: ExecutionContext) -> bool:
    raw = context.metadata.get("enable_external_tools")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    return bool(raw)


class EvidenceCapability:
    """Collect supporting evidence via NCBI query builder + retriever nodes."""

    name = "evidence"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "evidence"}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        base_state: dict[str, Any] = {
            "session_id": context.session_id,
            "text": context.text,
            "symptom_schema": _extract_symptom_schema_heuristic(context.text),
            "case_domain": None,
        }

        try:
            query_state = await asyncio.wait_for(
                ncbi_query_builder(base_state),
                timeout=_node_timeout_seconds(context),
            )
        except Exception as exc:
            logger.warning("ncbi_query_builder_timeout_or_error", extra={"error": str(exc)})
            query_state = {**base_state, "ncbi_query": ""}

        query_raw = query_state.get("ncbi_query")
        query = query_raw if isinstance(query_raw, str) else ""

        retrieval_state = {**base_state, **query_state}
        allow_external_tools = _external_tools_enabled(context)
        if not allow_external_tools:
            retrieval_state["ncbi_query"] = ""

        try:
            retriever_result = await asyncio.wait_for(
                ncbi_retriever_tool(retrieval_state),
                timeout=_node_timeout_seconds(context),
            )
        except Exception as exc:
            logger.warning("ncbi_retriever_timeout_or_error", extra={"error": str(exc)})
            retriever_result = {**retrieval_state, "evidence_selected": []}

        evidence_selected_raw = retriever_result.get("evidence_selected")
        evidence_selected = evidence_selected_raw if isinstance(evidence_selected_raw, list) else []

        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "evidence_signal": "evidence_ready" if evidence_selected else "evidence_pending",
                "query": query,
                "evidence_selected": evidence_selected,
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
                "evidence_signal": "unavailable",
                "query": "",
                "evidence_selected": [],
                "message": _SAFE_BUSY_MESSAGE,
            },
            provenance=provenance,
            errors=[reason],
        )
