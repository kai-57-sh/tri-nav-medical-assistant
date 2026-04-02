from enum import StrEnum


class StopReason(StrEnum):
    TOOL_BUDGET_EXCEEDED = "tool_budget_exceeded"
    TIME_BUDGET_EXCEEDED = "time_budget_exceeded"
