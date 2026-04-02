"""Permission rule models for TriNav v2."""

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase


class PermissionAction(StrEnum):
    """Supported permission decisions."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionRule:
    """A single rule mapping a target pattern to a permission action."""

    target: str
    action: PermissionAction | str

    def __post_init__(self) -> None:
        """Normalize action to PermissionAction and validate raw string input."""
        if isinstance(self.action, PermissionAction):
            normalized = self.action
        elif isinstance(self.action, str):
            try:
                normalized = PermissionAction(self.action)
            except ValueError as exc:
                raise ValueError(f"Invalid permission action: {self.action}") from exc
        else:
            raise ValueError(f"Invalid permission action: {self.action}")

        object.__setattr__(self, "action", normalized)

    def matches(self, target: str) -> bool:
        """Return whether this rule applies to a target identifier."""
        return fnmatchcase(target, self.target)
