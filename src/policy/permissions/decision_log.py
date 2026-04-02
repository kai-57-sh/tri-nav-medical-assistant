"""Decision logging for permission engine outcomes."""

from __future__ import annotations

from typing import TypedDict

from src.policy.permissions.rules import PermissionAction


class DecisionRow(TypedDict):
    target: str
    action: str
    reason: str


class DecisionLog:
    """In-memory permission decision log."""

    def __init__(self) -> None:
        self._rows: list[DecisionRow] = []

    def record(self, target: str, action: PermissionAction | str, reason: str) -> None:
        action_value = action.value if isinstance(action, PermissionAction) else str(action)
        self._rows.append(
            {
                "target": target,
                "action": action_value,
                "reason": reason,
            }
        )

    def list(self) -> list[DecisionRow]:
        return [row.copy() for row in self._rows]
