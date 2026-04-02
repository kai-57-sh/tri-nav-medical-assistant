"""Layered permission decision engine for TriNav v2."""

from collections.abc import Sequence

from src.policy.permissions.rules import PermissionAction, PermissionRule


class PermissionEngine:
    """Evaluates permission rules with fixed layer precedence."""

    def __init__(
        self,
        request_rules: Sequence[PermissionRule] | None = None,
        session_rules: Sequence[PermissionRule] | None = None,
        env_rules: Sequence[PermissionRule] | None = None,
        global_rules: Sequence[PermissionRule] | None = None,
    ) -> None:
        self._request_rules = tuple(request_rules or ())
        self._session_rules = tuple(session_rules or ())
        self._env_rules = tuple(env_rules or ())
        self._global_rules = tuple(global_rules or ())

    def decide(self, target: str) -> PermissionAction:
        """Return the first matched action by layer, defaulting to ASK."""
        for rules in (
            self._request_rules,
            self._session_rules,
            self._env_rules,
            self._global_rules,
        ):
            action = self._match_in_layer(rules, target)
            if action is not None:
                return action
        return PermissionAction.ASK

    @staticmethod
    def _match_in_layer(rules: Sequence[PermissionRule], target: str) -> PermissionAction | None:
        for rule in rules:
            if rule.matches(target):
                return rule.action
        return None
