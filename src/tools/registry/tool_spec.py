"""Tool specification model for TriNav v2 runtime."""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]
ToolInvokeEnvelope = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Runtime tool definition used by ToolRegistry."""

    name: str
    handler: ToolHandler
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool name must be a non-empty string")

        if not callable(self.handler):
            raise TypeError("Tool handler must be callable")

        if not inspect.iscoroutinefunction(self.handler):
            raise TypeError("Tool handler must be an async function")

        if self.timeout_s <= 0:
            raise ValueError("Tool timeout must be > 0")
