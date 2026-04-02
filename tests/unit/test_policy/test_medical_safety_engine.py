"""Unit tests for structured medical safety engine."""

from src.platform.policy.medical_safety_engine import MedicalSafetyEngine


def test_medical_safety_engine_rewrites_high_risk_language() -> None:
    engine = MedicalSafetyEngine()

    result = engine.enforce("根据症状可以确诊流感，先观察几天，不用着急。")

    assert result.risk_level == "high"
    assert "确诊" not in result.text
    assert "疑似" in result.text
    assert "先观察几天" not in result.text
    assert "不用着急" not in result.text
    assert "建议尽快就医" in result.text
    assert "rewrite.confirmed_diagnosis" in result.matched_rules
    assert "rewrite.delay_to_care.observe_days" in result.matched_rules
    assert "rewrite.delay_to_care.no_hurry" in result.matched_rules


def test_medical_safety_engine_preserves_existing_timely_care_guidance() -> None:
    engine = MedicalSafetyEngine()

    result = engine.enforce("你已经确诊肺炎，建议尽快就医。")

    assert result.risk_level == "high"
    assert "确诊" not in result.text
    assert "疑似" in result.text
    assert result.text.count("建议尽快就医") == 1


def test_medical_safety_engine_keeps_low_risk_text_unchanged() -> None:
    engine = MedicalSafetyEngine()

    result = engine.enforce("请保持休息，多喝水。")

    assert result.risk_level == "low"
    assert result.matched_rules == []
    assert result.text == "请保持休息，多喝水。"
