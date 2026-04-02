"""Evidence capability for TriNav v3."""

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


class EvidenceCapability:
    """Emit deterministic evidence collection signals."""

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
        return CapabilityResult(
            name=self.name,
            success=True,
            payload={
                "status": "ok",
                "evidence_signal": "evidence_pending",
                "query": context.text[:120],
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
            payload={"status": "degraded", "evidence_signal": "unavailable"},
            provenance=provenance,
            errors=[reason],
        )
