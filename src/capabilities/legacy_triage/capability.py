"""Legacy triage capability adapter for TriNav v2 runtime."""

from __future__ import annotations

from typing import cast

from src.chains.triage_chain import invoke_chain
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


class LegacyTriageCapability:
    """Adapter that executes the existing legacy triage chain."""

    name = "legacy_triage"
    version = "v1"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True}

    async def run(
        self,
        context: ExecutionContext,
        plan: dict[str, JSONValue] | None = None,
    ) -> CapabilityResult:
        _ = plan
        payload = cast(
            dict[str, JSONValue],
            await invoke_chain(
                session_id=context.session_id,
                text=context.text,
                image_base64=context.image_base64,
                gps_lat=context.gps_lat,
                gps_lng=context.gps_lng,
            ),
        )
        return CapabilityResult(
            name=self.name,
            success=True,
            payload=payload,
            provenance={
                "source": "legacy_graph",
                "graph": "src.chains.triage_chain.invoke_chain",
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
            "source": "legacy_graph",
            "graph": "src.chains.triage_chain.invoke_chain",
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
