"""Permission rule models for TriNav v2."""

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatchcase


class PermissionAction(str, Enum):
    """Supported permission decisions."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionRule:
    """A single rule mapping a target pattern to a permission action."""

    target: str
    action: PermissionAction

    def matches(self, target: str) -> bool:
        """Return whether this rule applies to a target identifier."""
        return fnmatchcase(target, self.target)
