"""Unit tests for medical output safety guard."""

import pytest

from src.policy.safety import enforce_output_guard


def test_enforce_output_guard_rewrites_risky_medical_wording() -> None:
    original = "根据症状可以确诊流感，先观察几天，不用着急，别去医院。"

    guarded = enforce_output_guard(original)

    assert "确诊" not in guarded
    assert "疑似" in guarded
    assert "先观察几天" not in guarded
    assert "不用着急" not in guarded
    assert "别去医院" not in guarded
    assert "建议尽快就医" in guarded
    assert "尽快就医" in guarded


def test_enforce_output_guard_appends_safety_guidance_when_missing() -> None:
    original = "目前考虑是轻微不适，请注意休息。"

    guarded = enforce_output_guard(original)

    assert "尽快就医" in guarded
    assert "..。" not in guarded


@pytest.mark.parametrize(
    "phrase",
    [
        "先观察几天",
        "不用着急",
        "不用就医",
        "肯定没事",
    ],
)
def test_enforce_output_guard_removes_delay_to_care_phrases(phrase: str) -> None:
    original = f"目前判断{phrase}。"

    guarded = enforce_output_guard(original)

    assert phrase not in guarded
    assert "尽快就医" in guarded


def test_enforce_output_guard_rewrites_negated_procare_phrase_bypass() -> None:
    original = "目前不建议尽快就医，先在家休息。"

    guarded = enforce_output_guard(original)

    assert "不建议尽快就医" not in guarded
    assert "建议尽快就医" in guarded
    assert "尽快就医" in guarded
