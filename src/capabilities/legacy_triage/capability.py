"""Legacy triage capability adapter for TriNav v2 runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue

LegacyInvoker = Callable[..., Awaitable[dict[str, Any]]]


class LegacyTriageCapability:
    """Adapter that executes the existing legacy triage chain."""

    name = "legacy_triage"
    version = "v1"

    def __init__(self, invoker: LegacyInvoker | None = None) -> None:
        self._invoker = invoker

    def _resolve_invoker(self) -> LegacyInvoker:
        if self._invoker is None:
            # Lazy import avoids requiring legacy chain dependencies at module import time.
            from src.chains.triage_chain import invoke_chain

            self._invoker = cast(LegacyInvoker, invoke_chain)
        return cast(LegacyInvoker, self._invoker)

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        invoker = self._resolve_invoker()
        payload = await invoker(
            session_id=context.session_id,
            text=context.text,
            image_base64=context.image_base64,
            gps_lat=context.gps_lat,
            gps_lng=context.gps_lng,
        )
        error_message = payload.get("error_message")
        errors: list[str] = []
        if isinstance(error_message, str) and error_message.strip():
            errors.append(error_message)

        return CapabilityResult(
            name=self.name,
            success=payload.get("status") != "error",
            payload=payload,
            provenance={
                "source": "legacy_graph",
                "graph": "src.chains.triage_chain.invoke_chain",
                "capability_version": self.version,
            },
            errors=errors,
        )

    async def fallback(
        self,
        context: ExecutionContext,
        reason: str,
        error: Exception | None = None,
    ) -> CapabilityResult:
        _ = context
        provenance: dict[str, JSONValue] = {
            "source": "legacy_graph",
            "graph": "src.chains.triage_chain.invoke_chain",
            "capability_version": self.version,
        }
        if error is not None:
            provenance["error_type"] = type(error).__name__

        return CapabilityResult(
            name=self.name,
            success=False,
            payload={},
            provenance=provenance,
            errors=[reason],
        )
