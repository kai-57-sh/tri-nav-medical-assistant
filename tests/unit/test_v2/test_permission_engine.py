"""Unit tests for TriNav v2 permission engine."""

from src.policy.permissions.engine import PermissionEngine
from src.policy.permissions.rules import PermissionAction, PermissionRule


def test_decide_prefers_request_layer_over_all_others() -> None:
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.search", action=PermissionAction.DENY)],
        session_rules=[PermissionRule(target="tool.search", action=PermissionAction.ALLOW)],
        env_rules=[PermissionRule(target="tool.search", action=PermissionAction.ASK)],
        global_rules=[PermissionRule(target="tool.search", action=PermissionAction.ALLOW)],
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.DENY


def test_decide_uses_next_matching_layer_when_higher_layer_has_no_match() -> None:
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.write", action=PermissionAction.DENY)],
        session_rules=[PermissionRule(target="tool.search", action=PermissionAction.ALLOW)],
        env_rules=[PermissionRule(target="tool.search", action=PermissionAction.DENY)],
        global_rules=[PermissionRule(target="tool.search", action=PermissionAction.ASK)],
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.ALLOW


def test_decide_uses_first_match_within_layer() -> None:
    engine = PermissionEngine(
        request_rules=[
            PermissionRule(target="*", action=PermissionAction.ASK),
            PermissionRule(target="tool.search", action=PermissionAction.DENY),
        ]
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.ASK


def test_decide_defaults_to_ask_when_no_rule_matches() -> None:
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.write", action=PermissionAction.DENY)],
        session_rules=[PermissionRule(target="tool.read", action=PermissionAction.ALLOW)],
        env_rules=[PermissionRule(target="tool.exec", action=PermissionAction.DENY)],
        global_rules=[PermissionRule(target="tool.debug", action=PermissionAction.ALLOW)],
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.ASK
