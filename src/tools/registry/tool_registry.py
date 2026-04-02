"""In-memory tool registry for TriNav v2 runtime."""

import asyncio
from typing import Any

from src.tools.registry.tool_spec import ToolInvokeEnvelope, ToolSpec


class ToolRegistryError(Exception):
    """Base exception for tool registry invocation failures."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when invoke is called with an unknown tool name."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' is not registered")


class ToolTimeoutError(ToolRegistryError):
    """Raised when a tool invocation exceeds configured timeout."""

    def __init__(self, tool_name: str, timeout_s: float) -> None:
        self.tool_name = tool_name
        self.timeout_s = timeout_s
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout_s:.3f}s. "
            "Increase timeout_s or optimize the tool handler."
        )


class ToolInvocationError(ToolRegistryError):
    """Raised when a tool handler fails during invocation."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' invocation failed: {message}")


class ToolRegistry:
    """Registers tools and invokes them by name."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Register one tool spec; raises on duplicate names."""

        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")

        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """Return registered tool spec by name."""

        return self._tools.get(name)

    async def invoke(self, name: str, payload: dict[str, Any]) -> ToolInvokeEnvelope:
        """Invoke a tool by name with timeout protection and normalized errors."""

        spec = self.get(name)
        if spec is None:
            raise ToolNotFoundError(name)

        try:
            result = await asyncio.wait_for(spec.handler(payload), timeout=spec.timeout_s)
            return {"tool": name, "ok": True, "result": result}
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise ToolTimeoutError(name, spec.timeout_s) from exc
        except Exception as exc:
            raise ToolInvocationError(name, str(exc)) from exc
