"""Policy-aware tool gateway."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from src.platform.policy.permission_engine import PermissionEngine


class ToolRegistryProtocol(Protocol):
    """Minimal tool registry contract required by ToolGateway."""

    async def invoke_raw(self, name: str, payload: dict[str, Any]) -> Any:
        """Invoke a registered tool and return raw handler output."""


class ToolPermissionDeniedError(PermissionError):
    """Raised when policy denies a tool invocation."""

    def __init__(self, reason: str, *, decision_id: str) -> None:
        self.reason = reason
        self.decision_id = decision_id
        super().__init__(f"{reason} (decision_id={decision_id})")


class ToolGateway:
    """Run tool invocations through policy checks before execution."""

    def __init__(
        self,
        *,
        tool_registry: ToolRegistryProtocol,
        permission_engine: PermissionEngine,
    ) -> None:
        self._tool_registry = tool_registry
        self._permission_engine = permission_engine

    async def invoke(
        self,
        tool_name: str,
        payload: Mapping[str, Any] | None,
        context: Mapping[str, Any] | None = None,
    ) -> Any:
        """Authorize and invoke a registered tool."""

        normalized_payload = dict(payload or {})
        normalized_context = dict(context or {})
        decision = self._permission_engine.decide(
            tool_name=tool_name,
            payload=normalized_payload,
            context=normalized_context,
        )
        if not decision.allow:
            raise ToolPermissionDeniedError(decision.reason, decision_id=decision.decision_id)

        return await self._tool_registry.invoke_raw(tool_name, normalized_payload)
