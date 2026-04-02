"""Turn-loop scaffold for RuntimeKernel-based execution."""

from __future__ import annotations

from dataclasses import dataclass

from src.platform.runtime.kernel import RuntimeInvokePayload, RuntimeKernel, RuntimeKernelInvokeResult


@dataclass(slots=True)
class RuntimeTurnLoop:
    """Minimal single-turn loop wrapper around RuntimeKernel."""

    kernel: RuntimeKernel

    async def run_turn(
        self,
        *,
        payload: RuntimeInvokePayload,
        request_id: str,
        session_id: str,
        trace_id: str,
    ) -> RuntimeKernelInvokeResult:
        return await self.kernel.invoke(
            payload=payload,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
        )
