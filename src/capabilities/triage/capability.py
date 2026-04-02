"""Triage capability for TriNav v3."""

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


class TriageCapability:
    """Return deterministic triage signal for v3 workflow integration."""

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
        _ = context
        _ = plan
        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "triage_level": "ROUTINE",
                "triage_signal": "triage_completed",
            },
            provenance={
                "source": "v3_stub",
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
            "source": "v3_stub",
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
            },
            provenance=provenance,
            errors=[reason],
        )
