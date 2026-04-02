"""Runtime query engine orchestration for TriNav v2."""

from src.core.capability.executor import SequentialExecutor
from src.core.capability.protocol import Capability
from src.core.runtime.event_bus import EventBus
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


class QueryEngine:
    """Coordinate capability execution and runtime event emission."""

    def __init__(
        self,
        capabilities: list[Capability],
        *,
        event_bus: EventBus | None = None,
        executor: SequentialExecutor | None = None,
    ) -> None:
        self._capabilities = list(capabilities)
        self.event_bus = event_bus or EventBus()
        self._executor = executor or SequentialExecutor(self._capabilities)

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run the configured capabilities and emit lifecycle events."""

        self.event_bus.emit_runtime_event(
            event_type="runtime_started",
            request_id=context.request_id,
            session_id=context.session_id,
        )

        results = await self._executor.execute(context)

        for result in results:
            self.event_bus.emit_runtime_event(
                event_type="capability_completed",
                request_id=context.request_id,
                session_id=context.session_id,
                data={"capability": result.name, "success": result.success},
            )

        self.event_bus.emit_runtime_event(
            event_type="runtime_finished",
            request_id=context.request_id,
            session_id=context.session_id,
            data={"capabilities_executed": len(results)},
        )
        return results
