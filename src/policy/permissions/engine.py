"""Layered permission decision engine for TriNav v2."""

from collections.abc import Sequence

from src.policy.permissions.decision_log import DecisionLog
from src.policy.permissions.rules import PermissionAction, PermissionRule


class PermissionEngine:
    """Evaluates permission rules with fixed layer precedence."""

    def __init__(
        self,
        request_rules: Sequence[PermissionRule] | None = None,
        session_rules: Sequence[PermissionRule] | None = None,
        env_rules: Sequence[PermissionRule] | None = None,
        global_rules: Sequence[PermissionRule] | None = None,
        decision_log: DecisionLog | None = None,
    ) -> None:
        self._request_rules = tuple(request_rules or ())
        self._session_rules = tuple(session_rules or ())
        self._env_rules = tuple(env_rules or ())
        self._global_rules = tuple(global_rules or ())
        self._decision_log = decision_log

    def decide(self, target: str) -> PermissionAction:
        """Return the first matched action by layer, defaulting to ASK."""
        for layer_name, rules in (
            ("request", self._request_rules),
            ("session", self._session_rules),
            ("env", self._env_rules),
            ("global", self._global_rules),
        ):
            matched_rule = self._match_rule_in_layer(rules, target)
            if matched_rule is not None:
                if self._decision_log is not None:
                    self._decision_log.record(
                        target=target,
                        action=matched_rule.action,
                        reason=f"{layer_name} layer matched rule '{matched_rule.target}'",
                    )
                return matched_rule.action

        if self._decision_log is not None:
            self._decision_log.record(
                target=target,
                action=PermissionAction.ASK,
                reason="default fallback: no matching rule",
            )
        return PermissionAction.ASK

    @staticmethod
    def _match_rule_in_layer(
        rules: Sequence[PermissionRule], target: str
    ) -> PermissionRule | None:
        for rule in rules:
            if rule.matches(target):
                return rule
        return None
