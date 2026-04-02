"""Permission decision model and engine for platform tool access."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Permission outcome returned for one tool invocation attempt."""

    allow: bool
    reason: str
    decision_id: str


class PermissionEngine:
    """Evaluate whether a tool invocation should be allowed."""

    def __init__(self, *, sensitive_tool_patterns: tuple[str, ...] | None = None) -> None:
        patterns = (
            ("vision_extract", "vision_tool", "vision_*")
            if sensitive_tool_patterns is None
            else sensitive_tool_patterns
        )
        self._sensitive_tool_patterns = tuple(pattern.lower() for pattern in patterns if pattern.strip())
        self._decisions: list[PolicyDecision] = []

    def decide(
        self,
        tool_name: str,
        payload: Mapping[str, Any] | None,
        context: Mapping[str, Any] | None,
    ) -> PolicyDecision:
        """Return an allow/deny decision for a tool invocation."""

        _ = payload
        normalized_tool_name = tool_name.strip()
        normalized_context = context or {}

        if not normalized_tool_name:
            return self._record_decision(
                allow=False,
                reason="invalid_tool_name",
            )

        if not self._is_sensitive_tool(normalized_tool_name):
            return self._record_decision(
                allow=True,
                reason="non_sensitive_tool",
            )

        if self._has_sensitive_tool_consent(normalized_tool_name, normalized_context):
            return self._record_decision(
                allow=True,
                reason="consent_present",
            )

        return self._record_decision(
            allow=False,
            reason="missing_patient_consent",
        )

    def list_decisions(self) -> list[PolicyDecision]:
        """Return immutable snapshots of all decisions made by this instance."""

        return list(self._decisions)

    def _record_decision(self, *, allow: bool, reason: str) -> PolicyDecision:
        decision = PolicyDecision(
            allow=allow,
            reason=reason,
            decision_id=uuid4().hex,
        )
        self._decisions.append(decision)
        return decision

    def _is_sensitive_tool(self, tool_name: str) -> bool:
        lowered_name = tool_name.lower()
        return any(fnmatchcase(lowered_name, pattern) for pattern in self._sensitive_tool_patterns)

    def _has_sensitive_tool_consent(
        self,
        tool_name: str,
        context: Mapping[str, Any],
    ) -> bool:
        if self._extract_direct_consent(context):
            return True

        consents = context.get("consents")
        if isinstance(consents, Mapping):
            if self._is_truthy(consents.get(tool_name)):
                return True
            if self._is_truthy(consents.get("vision")):
                return True
            if self._is_truthy(consents.get("sensitive_tools")):
                return True

        return False

    def _extract_direct_consent(self, source: Mapping[str, Any]) -> bool:
        direct_keys = (
            "consent",
            "user_consent",
            "sensitive_tool_consent",
            "consent_to_sensitive_tools",
            "vision_consent",
        )
        return any(self._is_truthy(source.get(key)) for key in direct_keys)

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "allow", "consented"}
        if isinstance(value, (int, float)):
            return value != 0
        return False
