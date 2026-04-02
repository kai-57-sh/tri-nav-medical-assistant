"""Task-level coordinator for multi-step runtime subtasks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from src.core.runtime.execution_context import ExecutionContext

TaskRunner = Callable[[ExecutionContext], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class TaskSpec:
    """One runnable task definition."""

    name: str
    runner: TaskRunner
    required: bool = True


class TaskCoordinator:
    """Execute task specs sequentially with required/optional semantics."""

    def __init__(self, tasks: Sequence[TaskSpec]) -> None:
        self._tasks = list(tasks)

    async def run(self, context: ExecutionContext) -> dict[str, dict[str, Any]]:
        """Run all tasks and stop on required failure."""

        results: dict[str, dict[str, Any]] = {}
        for task in self._tasks:
            try:
                payload = await task.runner(context)
                if not isinstance(payload, dict):
                    raise TypeError("task runner must return dict payload")
                results[task.name] = {
                    "success": True,
                    "payload": payload,
                    "error": None,
                    "required": task.required,
                }
            except Exception as exc:
                results[task.name] = {
                    "success": False,
                    "payload": {},
                    "error": f"{type(exc).__name__}: {exc}",
                    "required": task.required,
                }
                if task.required:
                    break
        return results
