"""RuntimeKernel single-entry runtime execution surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.core.coordinator.runtime_coordinator import RuntimeCoordinator
from src.core.plugins.registry import RuntimePluginRegistry
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import JSONValue, CapabilityResult
from src.core.state.event_store import InMemoryEventStore


class RuntimeInvokePayload(Protocol):
    """Minimal payload contract required by RuntimeKernel."""

    text: str
    image_base64: str | None
    gps_lat: float | None
    gps_lng: float | None
    metadata: dict[str, Any]


class RuntimeEventBus(Protocol):
    """Minimal event bus contract used by RuntimeKernel."""

    def dump(self) -> list[dict[str, JSONValue]]:
        """Return serialized runtime events."""


@dataclass(frozen=True)
class RuntimeKernelInvokeResult:
    """Kernel invoke result consumed by API adapters."""

    results: list[CapabilityResult]
    runtime_events: list[dict[str, JSONValue]]


class RuntimeKernelInvokeError(RuntimeError):
    """RuntimeKernel invoke failure that carries collected runtime events."""

    def __init__(
        self,
        *,
        message: str,
        runtime_events: list[dict[str, JSONValue]],
        error: Exception,
    ) -> None:
        super().__init__(message)
        self.runtime_events = runtime_events
        self.error = error


class RuntimeKernel:
    """Execute one assistant turn through runtime coordinator and event bus."""

    def __init__(
        self,
        *,
        coordinator: RuntimeCoordinator,
        event_bus: RuntimeEventBus,
    ) -> None:
        self._coordinator = coordinator
        self._event_bus = event_bus

    async def invoke(
        self,
        *,
        payload: RuntimeInvokePayload,
        request_id: str,
        session_id: str,
        trace_id: str,
    ) -> RuntimeKernelInvokeResult:
        """Run one assistant invoke turn and return results with runtime events."""

        context_metadata = dict(payload.metadata)
        context_metadata["trace_id"] = trace_id
        context = ExecutionContext(
            request_id=request_id,
            session_id=session_id,
            text=payload.text,
            image_base64=payload.image_base64,
            gps_lat=payload.gps_lat,
            gps_lng=payload.gps_lng,
            metadata=context_metadata,
        )
        try:
            results = await self._coordinator.run(context)
        except Exception as exc:
            raise RuntimeKernelInvokeError(
                message="assistant_v2_runtime_failed",
                runtime_events=self._event_bus.dump(),
                error=exc,
            ) from exc
        return RuntimeKernelInvokeResult(
            results=results,
            runtime_events=self._event_bus.dump(),
        )


def build_runtime_kernel(
    *,
    event_store: InMemoryEventStore,
    plugins: RuntimePluginRegistry | None = None,
) -> RuntimeKernel:
    """Build RuntimeKernel with legacy v2 triage capability."""

    from src.capabilities.legacy_triage.capability import LegacyTriageCapability
    from src.core.runtime.event_bus import EventBus
    from src.core.runtime.query_engine import QueryEngine

    event_bus = EventBus()
    engine = QueryEngine(
        [LegacyTriageCapability()],
        event_bus=event_bus,
        event_store=event_store,
    )
    coordinator = RuntimeCoordinator(engine=engine, plugins=plugins)
    return RuntimeKernel(coordinator=coordinator, event_bus=event_bus)
