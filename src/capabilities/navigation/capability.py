"""Navigation capability for TriNav v3."""

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, JSONValue


class NavigationCapability:
    """Emit deterministic clinical navigation signal."""

    name = "navigation"
    version = "v3"

    async def plan(self, context: ExecutionContext) -> dict[str, JSONValue]:
        _ = context
        return {"enabled": True, "stage": "navigation"}

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
                "navigation_signal": "routing_prepared",
                "destination_type": "clinical_guidance",
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
            payload={"status": "degraded", "navigation_signal": "unavailable"},
            provenance=provenance,
            errors=[reason],
        )
