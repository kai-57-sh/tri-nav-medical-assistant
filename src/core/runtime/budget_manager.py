from collections.abc import Callable
from time import monotonic

from src.core.runtime.stop_reason import StopReason


class BudgetManager:
    def __init__(
        self,
        *,
        max_tool_calls: int,
        max_elapsed_ms: int,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self._max_tool_calls = max_tool_calls
        self._max_elapsed_ms = max_elapsed_ms
        self._tool_calls = 0
        self._now_fn = now_fn or monotonic
        self._started_at = self._now_fn()

    def consume_tool_call(self) -> StopReason | None:
        self._tool_calls += 1
        if self._tool_calls > self._max_tool_calls:
            return StopReason.TOOL_BUDGET_EXCEEDED
        return None

    def check_elapsed(self) -> StopReason | None:
        elapsed_ms = int((self._now_fn() - self._started_at) * 1000)
        if elapsed_ms > self._max_elapsed_ms:
            return StopReason.TIME_BUDGET_EXCEEDED
        return None
