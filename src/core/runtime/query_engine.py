"""Runtime query engine orchestration for TriNav v2."""

from typing import Any, Protocol

from src.core.capability.executor import ExecutorProtocol, SequentialExecutor
from src.core.capability.protocol import Capability
from src.core.runtime.event_bus import EventBus
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


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
    ) -> None:
        self._capabilities = list(capabilities)
        self.event_bus = event_bus or EventBus()
        self._event_store = event_store
        self._executor: ExecutorProtocol = executor or SequentialExecutor(self._capabilities)

    def _emit_runtime_event(
        self,
        *,
        event_type: str,
        request_id: str,
        session_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit to bus and optionally persist by session."""

        event = self.event_bus.emit_runtime_event(
            event_type=event_type,
            request_id=request_id,
            session_id=session_id,
            data=data,
        )
        if self._event_store is not None:
            self._event_store.append(session_id, event.model_dump(mode="json"))

    async def run(self, context: ExecutionContext) -> list[CapabilityResult]:
        """Run the configured capabilities and emit lifecycle events."""

        self._emit_runtime_event(
            event_type="runtime_started",
            request_id=context.request_id,
            session_id=context.session_id,
        )

        results: list[CapabilityResult] = []
        escaped_error: Exception | None = None
        try:
            results = await self._executor.execute(context)
            return results
        except Exception as exc:
            escaped_error = exc
            raise
        finally:
            for result in results:
                self._emit_runtime_event(
                    event_type="capability_completed",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    data={"capability": result.name, "success": result.success},
                )

            if escaped_error is not None:
                self._emit_runtime_event(
                    event_type="runtime_failed",
                    request_id=context.request_id,
                    session_id=context.session_id,
                    data={
                        "error_type": type(escaped_error).__name__,
                        "error_message": str(escaped_error),
                        "error_stage": "executor",
                    },
                )

            self._emit_runtime_event(
                event_type="runtime_finished",
                request_id=context.request_id,
                session_id=context.session_id,
                data={
                    "capabilities_executed": len(results),
                    "success": escaped_error is None,
                },
            )
