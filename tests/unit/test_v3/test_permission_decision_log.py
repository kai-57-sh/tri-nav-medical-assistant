"""Unit tests for permission decision logging."""

from src.policy.permissions.decision_log import DecisionLog
from src.policy.permissions.engine import PermissionEngine
from src.policy.permissions.rules import PermissionAction, PermissionRule


def test_decision_log_record_and_list_returns_copy() -> None:
    log = DecisionLog()
    log.record(target="tool.search", action=PermissionAction.ALLOW, reason="request matched")
    rows = log.list()

    assert rows == [
        {"target": "tool.search", "action": "allow", "reason": "request matched"},
    ]

    rows[0]["reason"] = "mutated"
    assert log.list()[0]["reason"] == "request matched"


def test_permission_engine_records_match_reason_when_log_attached() -> None:
    log = DecisionLog()
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.search", action=PermissionAction.DENY)],
        decision_log=log,
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.DENY
    rows = log.list()
    assert len(rows) == 1
    assert rows[0]["target"] == "tool.search"
    assert rows[0]["action"] == "deny"
    assert "request" in rows[0]["reason"]
    assert "matched" in rows[0]["reason"]


def test_permission_engine_records_default_fallback_reason_when_no_match() -> None:
    log = DecisionLog()
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.write", action=PermissionAction.DENY)],
        decision_log=log,
    )

    decision = engine.decide("tool.search")

    assert decision == PermissionAction.ASK
    rows = log.list()
    assert len(rows) == 1
    assert rows[0]["target"] == "tool.search"
    assert rows[0]["action"] == "ask"
    assert "default" in rows[0]["reason"]
    assert "fallback" in rows[0]["reason"]
