"""Built-in runtime plugins for v3 parity rollout."""

from __future__ import annotations

from src.core.plugins.protocol import RuntimePlugin
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult

_MEDICAL_DISCLAIMER = "本建议仅供参考，不替代专业医疗诊断。"


class TraceContextPlugin:
    """Ensure trace metadata exists and mark trace plugin activation."""

    name = "trace_context"

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        metadata = dict(context.metadata)
        trace_id = metadata.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id.strip():
            metadata["trace_id"] = f"trace-{context.request_id}"
        metadata["trace_plugin_enabled"] = True
        return context.model_copy(update={"metadata": metadata})

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        _ = context
        return results


class MedicalDisclaimerPlugin:
    """Append medical disclaimer to user-facing final responses."""

    name = "medical_footer"

    async def before_execute(self, context: ExecutionContext) -> ExecutionContext:
        return context

    async def after_execute(
        self,
        context: ExecutionContext,
        results: list[CapabilityResult],
    ) -> list[CapabilityResult]:
        _ = context
        updated: list[CapabilityResult] = []
        for result in results:
            payload = dict(result.payload)
            status = payload.get("status")
            response = payload.get("response")
            if (
                isinstance(status, str)
                and status in {"final", "need_more_info"}
                and isinstance(response, str)
            ):
                payload["response"] = self._append_disclaimer(response)
                updated.append(result.model_copy(update={"payload": payload}))
                continue
            updated.append(result)
        return updated

    def _append_disclaimer(self, response: str) -> str:
        text = response.strip()
        if _MEDICAL_DISCLAIMER in text:
            return text
        if not text:
            return _MEDICAL_DISCLAIMER
        if text[-1] not in {"。", "！", "？", ".", "!", "?"}:
            text = f"{text}。"
        return f"{text}{_MEDICAL_DISCLAIMER}"


def create_builtin_plugins(
    *,
    trace_enabled: bool,
    medical_footer_enabled: bool,
) -> list[RuntimePlugin]:
    """Create built-in plugin instances based on feature switches."""

    plugins: list[RuntimePlugin] = []
    if trace_enabled:
        plugins.append(TraceContextPlugin())
    if medical_footer_enabled:
        plugins.append(MedicalDisclaimerPlugin())
    return plugins
