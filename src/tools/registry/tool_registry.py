"""In-memory tool registry for TriNav v2 runtime."""

import asyncio
from typing import Any

from src.tools.registry.tool_spec import ToolSpec


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

    async def invoke(self, name: str, payload: dict[str, Any]) -> Any:
        """Invoke a tool by name with timeout protection."""

        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Tool '{name}' is not registered")

        return await asyncio.wait_for(spec.handler(payload), timeout=spec.timeout_s)
