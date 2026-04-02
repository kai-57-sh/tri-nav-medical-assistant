"""Unit tests for permission decision logging."""

import pytest

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


def test_decision_log_rejects_invalid_action_value() -> None:
    log = DecisionLog()

    with pytest.raises(ValueError, match="Invalid permission action"):
        log.record(target="tool.search", action="noop", reason="invalid")


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


@pytest.mark.parametrize(
    "engine_kwargs, expected_action, expected_layer",
    [
        (
            {"session_rules": [PermissionRule(target="tool.search", action=PermissionAction.ALLOW)]},
            PermissionAction.ALLOW,
            "session",
        ),
        (
            {"env_rules": [PermissionRule(target="tool.search", action=PermissionAction.DENY)]},
            PermissionAction.DENY,
            "env",
        ),
        (
            {"global_rules": [PermissionRule(target="tool.search", action=PermissionAction.ALLOW)]},
            PermissionAction.ALLOW,
            "global",
        ),
    ],
)
def test_permission_engine_records_layer_reason_for_non_request_matches(
    engine_kwargs: dict[str, list[PermissionRule]],
    expected_action: PermissionAction,
    expected_layer: str,
) -> None:
    log = DecisionLog()
    engine = PermissionEngine(decision_log=log, **engine_kwargs)

    decision = engine.decide("tool.search")

    assert decision == expected_action
    rows = log.list()
    assert len(rows) == 1
    assert rows[0]["action"] == expected_action.value
    assert expected_layer in rows[0]["reason"]
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


def test_permission_engine_appends_decision_rows_in_call_order() -> None:
    log = DecisionLog()
    engine = PermissionEngine(
        request_rules=[PermissionRule(target="tool.search", action=PermissionAction.DENY)],
        session_rules=[PermissionRule(target="tool.weather", action=PermissionAction.ALLOW)],
        decision_log=log,
    )

    decision_first = engine.decide("tool.search")
    decision_second = engine.decide("tool.weather")
    decision_third = engine.decide("tool.unknown")

    assert decision_first == PermissionAction.DENY
    assert decision_second == PermissionAction.ALLOW
    assert decision_third == PermissionAction.ASK

    rows = log.list()
    assert [row["target"] for row in rows] == ["tool.search", "tool.weather", "tool.unknown"]
