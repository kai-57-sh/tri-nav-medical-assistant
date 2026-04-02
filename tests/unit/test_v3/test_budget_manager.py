from src.core.runtime.budget_manager import BudgetManager
from src.core.runtime.stop_reason import StopReason


def test_budget_manager_stops_after_tool_budget_exceeded() -> None:
    budget = BudgetManager(max_tool_calls=2, max_elapsed_ms=10_000)
    assert budget.consume_tool_call() is None
    assert budget.consume_tool_call() is None
    assert budget.consume_tool_call() == StopReason.TOOL_BUDGET_EXCEEDED


def test_budget_manager_stops_after_time_budget_exceeded() -> None:
    timeline = iter([0.0, 0.1, 1.2])  # seconds
    budget = BudgetManager(max_tool_calls=10, max_elapsed_ms=500, now_fn=lambda: next(timeline))
    assert budget.check_elapsed() is None
    assert budget.check_elapsed() is StopReason.TIME_BUDGET_EXCEEDED
