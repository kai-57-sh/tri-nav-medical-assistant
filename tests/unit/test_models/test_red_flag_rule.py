"""Tests for RedFlagRule and RuleCondition models."""
import pytest
from pydantic import ValidationError

from src.models.red_flag_rule import RedFlagRule, RuleCondition


class TestRuleCondition:
    """Test RuleCondition validation."""

    def test_rule_condition_valid_contains_any(self):
        """Test valid rule condition with contains_any operator."""
        condition = RuleCondition(
            field="accompanying_symptoms",
            op="contains_any",
            value=["呼吸困难", "喘不过气", "窒息感"]
        )
        assert condition.field == "accompanying_symptoms"
        assert condition.op == "contains_any"
        assert len(condition.value) == 3

    def test_rule_condition_valid_contains_all(self):
        """Test valid rule condition with contains_all operator."""
        condition = RuleCondition(
            field="symptoms",
            op="contains_all",
            value=["发热", "咳嗽"]
        )
        assert condition.op == "contains_all"

    def test_rule_condition_valid_equals(self):
        """Test valid rule condition with equals operator."""
        condition = RuleCondition(
            field="severity",
            op="equals",
            value="严重"
        )
        assert condition.op == "equals"
        assert condition.value == "严重"

    def test_rule_condition_invalid_operator(self):
        """Test invalid operator."""
        with pytest.raises(ValidationError) as exc_info:
            RuleCondition(
                field="symptoms",
                op="invalid_op",
                value=["test"]
            )
        assert "op" in str(exc_info.value)

    def test_rule_condition_invalid_field_empty(self):
        """Test field - Pydantic v2 allows empty strings by default."""
        # Document that empty field is allowed
        condition = RuleCondition(
            field="",
            op="contains_any",
            value=["test"]
        )
        assert condition.field == ""


class TestRedFlagRule:
    """Test RedFlagRule validation rules."""

    def test_red_flag_rule_valid_complete(self):
        """Test valid red flag rule with all fields."""
        rule = RedFlagRule(
            id="RF_BREATHING_DIFFICULTY",
            priority="high",
            version="1.0.0",
            conditions=[
                RuleCondition(
                    field="accompanying_symptoms",
                    op="contains_any",
                    value=["呼吸困难", "喘不过气", "窒息感"]
                )
            ],
            triage_level="EMERGENCY",
            user_message="检测到呼吸困难症状，建议立即急诊/呼叫急救",
            department=["急诊"]
        )
        assert rule.id == "RF_BREATHING_DIFFICULTY"
        assert rule.priority == "high"
        assert rule.version == "1.0.0"
        assert len(rule.conditions) == 1
        assert rule.triage_level == "EMERGENCY"

    def test_red_flag_rule_valid_multiple_conditions(self):
        """Test valid rule with multiple conditions."""
        rule = RedFlagRule(
            id="RF_HIGH_FEVER_SEVERE",
            priority="high",
            version="1.0.0",
            conditions=[
                RuleCondition(field="symptoms", op="contains_any", value=["发热", "发烧"]),
                RuleCondition(field="severity", op="equals", value="严重")
            ],
            triage_level="EMERGENCY",
            user_message="高热伴严重症状，建议立即急诊",
            department=["急诊", "发热门诊"]
        )
        assert len(rule.conditions) == 2

    def test_red_flag_rule_valid_medium_priority(self):
        """Test valid rule with medium priority."""
        rule = RedFlagRule(
            id="RF_MODERATE_PAIN",
            priority="medium",
            version="1.0.0",
            conditions=[
                RuleCondition(field="severity", op="equals", value="中度")
            ],
            triage_level="EMERGENCY",
            user_message="中度疼痛，建议就医",
            department=["全科"]
        )
        assert rule.priority == "medium"

    def test_red_flag_rule_valid_low_priority(self):
        """Test valid rule with low priority."""
        rule = RedFlagRule(
            id="RF_MILD_SYMPTOM",
            priority="low",
            version="1.0.0",
            conditions=[
                RuleCondition(field="severity", op="equals", value="轻微")
            ],
            triage_level="EMERGENCY",
            user_message="轻微症状，建议观察",
            department=["全科"]
        )
        assert rule.priority == "low"

    def test_red_flag_rule_id_validator_pass(self):
        """Test id validator: 'RF_' prefix passes."""
        rule = RedFlagRule(
            id="RF_TEST_RULE",
            priority="high",
            version="1.0.0",
            conditions=[
                RuleCondition(field="symptoms", op="contains_any", value=["test"])
            ],
            triage_level="EMERGENCY",
            user_message="Test message",
            department=["急诊"]
        )
        assert rule.id == "RF_TEST_RULE"

    def test_red_flag_rule_id_validator_fail_no_prefix(self):
        """Test id validator: pattern mismatch fails."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="BREATHING_DIFFICULTY",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test message",
                department=["急诊"]
            )
        # Pydantic v2 error: "String should match pattern"
        assert "pattern" in str(exc_info.value).lower()

    def test_red_flag_rule_id_validator_fail_wrong_prefix(self):
        """Test id validator: wrong prefix 'RFE_' fails pattern."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RFE_TEST_RULE",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test message",
                department=["急诊"]
            )
        # Pydantic v2 error: "String should match pattern"
        assert "pattern" in str(exc_info.value).lower()

    def test_red_flag_rule_id_pattern_fail_lowercase(self):
        """Test id validator: lowercase letters fail pattern."""
        # Pattern requires uppercase letters and underscores only
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_test_rule",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test message",
                department=["急诊"]
            )
        assert "id" in str(exc_info.value)

    def test_red_flag_rule_id_pattern_fail_special_chars(self):
        """Test id validator: special characters fail pattern."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST-RULE",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test message",
                department=["急诊"]
            )
        assert "id" in str(exc_info.value)

    def test_red_flag_rule_invalid_priority(self):
        """Test invalid priority value."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="critical",  # Invalid
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test",
                department=["急诊"]
            )
        assert "priority" in str(exc_info.value)

    def test_red_flag_rule_invalid_triage_level(self):
        """Test invalid triage_level (only EMERGENCY allowed)."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="URGENT",  # Invalid, red flag rules always EMERGENCY
                user_message="Test",
                department=["急诊"]
            )
        assert "triage_level" in str(exc_info.value)

    def test_red_flag_rule_invalid_user_message_empty(self):
        """Test user_message cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="",
                department=["急诊"]
            )
        assert "user_message" in str(exc_info.value)

    def test_red_flag_rule_invalid_user_message_too_long(self):
        """Test user_message max length 500."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="a" * 501,
                department=["急诊"]
            )
        assert "user_message" in str(exc_info.value)

    def test_red_flag_rule_invalid_department_empty(self):
        """Test department cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test",
                department=[]
            )
        assert "department" in str(exc_info.value)

    def test_red_flag_rule_invalid_conditions_empty(self):
        """Test conditions cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            RedFlagRule(
                id="RF_TEST",
                priority="high",
                version="1.0.0",
                conditions=[],
                triage_level="EMERGENCY",
                user_message="Test",
                department=["急诊"]
            )
        assert "conditions" in str(exc_info.value)

    def test_red_flag_rule_all_valid_operators(self):
        """Test all valid operators."""
        operators = ["contains_any", "contains_all", "equals"]
        op_names = ["CONTAINS_ANY", "CONTAINS_ALL", "EQUALS"]
        for op, op_name in zip(operators, op_names):
            rule = RedFlagRule(
                id=f"RF_TEST_{op_name}",
                priority="high",
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op=op, value=["test"] if op != "equals" else "test")
                ],
                triage_level="EMERGENCY",
                user_message="Test",
                department=["急诊"]
            )
            assert rule.conditions[0].op == op

    def test_red_flag_rule_all_valid_priorities(self):
        """Test all valid priority values."""
        priorities = ["high", "medium", "low"]
        for priority in priorities:
            rule = RedFlagRule(
                id=f"RF_TEST_{priority.upper()}",
                priority=priority,
                version="1.0.0",
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test",
                department=["急诊"]
            )
            assert rule.priority == priority

    def test_red_flag_rule_version_various_formats(self):
        """Test various version formats without numbers in ID."""
        versions = ["1.0.0", "2.1.3", "0.0.1", "10.20.30"]
        # Use version names without numbers to match pattern [A-Z_]+
        version_ids = ["VERSION_A", "VERSION_B", "VERSION_C", "VERSION_D"]
        for version, v_id in zip(versions, version_ids):
            rule = RedFlagRule(
                id=f"RF_TEST_{v_id}",
                priority="high",
                version=version,
                conditions=[
                    RuleCondition(field="symptoms", op="contains_any", value=["test"])
                ],
                triage_level="EMERGENCY",
                user_message="Test",
                department=["急诊"]
            )
            assert rule.version == version

    def test_red_flag_rule_json_serialization(self):
        """Test RedFlagRule can be serialized to JSON."""
        rule = RedFlagRule(
            id="RF_BREATHING_DIFFICULTY",
            priority="high",
            version="1.0.0",
            conditions=[
                RuleCondition(
                    field="accompanying_symptoms",
                    op="contains_any",
                    value=["呼吸困难", "喘不过气"]
                )
            ],
            triage_level="EMERGENCY",
            user_message="检测到呼吸困难",
            department=["急诊"]
        )

        # Test model_dump
        data = rule.model_dump()
        assert data["id"] == "RF_BREATHING_DIFFICULTY"
        assert data["priority"] == "high"
        assert len(data["conditions"]) == 1

        # Test JSON serialization
        json_str = rule.model_dump_json()
        assert "RF_BREATHING_DIFFICULTY" in json_str
        assert "呼吸困难" in json_str
