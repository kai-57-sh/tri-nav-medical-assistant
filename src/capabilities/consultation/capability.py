"""Consultation capability for TriNav v3."""

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


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
        summary = context.text[:120]
        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "summary": summary,
                "consultation_signal": "intake_complete",
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
            payload={"status": "degraded", "summary": ""},
            provenance=provenance,
            errors=[reason],
        )
