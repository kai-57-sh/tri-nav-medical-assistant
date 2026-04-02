"""Runtime query engine orchestration for TriNav v2."""

from typing import Any, Protocol

from src.core.capability.planner import PlannerProtocol
from src.core.capability.executor import ExecutorProtocol, SequentialExecutor
from src.core.capability.protocol import Capability
from src.core.runtime.budget_manager import BudgetManager
from src.core.runtime.event_bus import EventBus
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult, RuntimeStop


class EventStoreProtocol(Protocol):
    """Protocol for runtime event persistence backends."""

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Store one runtime event under the given session."""


class QueryEngine:
    """Coordinate capability execution and runtime event emission."""

    def __init__(
        self,
        capabilities: list[Capability],
        *,
        event_bus: EventBus | None = None,
        event_store: EventStoreProtocol | None = None,
        executor: ExecutorProtocol | None = None,
        planner: PlannerProtocol | None = None,
        budget: BudgetManager | None = None,
    ) -> None:
        self._capabilities = list(capabilities)
        self.event_bus = event_bus or EventBus()
        self._event_store = event_store
        self._executor_override = executor
        self._planner = planner
        self._budget = budget

    def _get_executor(self, context: ExecutionContext) -> ExecutorProtocol:
        """Return an executor for this run, using planner on the default path."""

        if self._executor_override is not None:
            return self._executor_override

        planned_capabilities = self._capabilities
        if self._planner is not None:
            capabilities_by_name = {capability.name: capability for capability in self._capabilities}
            planned_capabilities = self._planner.plan(context, capabilities_by_name)
        return SequentialExecutor(planned_capabilities)

    def _emit_runtime_event(
        self,
        *,
        event_type: str,
        request_id: str,
        session_id: str,
        trace_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit to bus and optionally persist by session."""

        payload = {} if data is None else dict(data)
        if trace_id is not None:
            payload["trace_id"] = trace_id

        event = self.event_bus.emit_runtime_event(
            event_type=event_type,
            request_id=request_id,
            session_id=session_id,
            data=payload,
        )
        if self._event_store is not None:
            self._event_store.append(session_id, event.model_dump(mode="json"))

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run the configured capabilities and emit lifecycle events."""

        raw_trace_id = context.metadata.get("trace_id")
        trace_id = raw_trace_id if isinstance(raw_trace_id, str) and raw_trace_id else None
        self._emit_runtime_event(
            event_type="runtime_started",
            request_id=context.request_id,
            session_id=context.session_id,
            trace_id=trace_id,
        )

        if self._budget is not None:
            stop_reason = self._budget.check_elapsed()
            if stop_reason is not None:
                stop = RuntimeStop(reason=stop_reason)
                self._emit_runtime_event(
                    event_type="runtime_stopped",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    trace_id=trace_id,
                    data=stop.model_dump(mode="json"),
                )
                self._emit_runtime_event(
                    event_type="runtime_finished",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    trace_id=trace_id,
                    data={"capabilities_executed": 0, "success": False},
                )
                return []

        results: list[CapabilityResult] = []
        escaped_error: Exception | None = None
        error_stage = "executor"
        try:
            try:
                executor = self._get_executor(context)
            except Exception as exc:
                escaped_error = exc
                error_stage = "planner"
                raise

            try:
                results = await executor.execute(context)
                return results
            except Exception as exc:
                escaped_error = exc
                error_stage = "executor"
                raise
        finally:
            for result in results:
                self._emit_runtime_event(
                    event_type="capability_completed",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    trace_id=trace_id,
                    data={"capability": result.name, "success": result.success},
                )

            if escaped_error is not None:
                self._emit_runtime_event(
                    event_type="runtime_failed",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    trace_id=trace_id,
                    data={
                        "error_type": type(escaped_error).__name__,
                        "error_message": str(escaped_error),
                        "error_stage": error_stage,
                    },
                )

            self._emit_runtime_event(
                event_type="runtime_finished",
                request_id=context.request_id,
                session_id=context.session_id,
                trace_id=trace_id,
                data={
                    "capabilities_executed": len(results),
                    "success": escaped_error is None,
                },
            )
