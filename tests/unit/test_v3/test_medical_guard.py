"""Unit tests for medical output safety guard."""

import re

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


@pytest.mark.parametrize(
    "negated_phrase",
    [
        "不建议尽快就医",
        "无需尽快就医",
        "不必尽快就医",
        "不用尽快就医",
        "不宜尽快就医",
        "不需要尽快就医",
        "没必要尽快就医",
        "不建议   尽快就医",
        "无需  尽快就医",
    ],
)
def test_enforce_output_guard_normalizes_negated_seek_care_variants(
    negated_phrase: str,
) -> None:
    original = f"当前情况{negated_phrase}，继续观察。"

    guarded = enforce_output_guard(original)

    assert negated_phrase not in guarded
    assert "建议尽快就医" in guarded
    assert "尽快就医" in guarded
    assert re.search(r"(不建议|无需|不必|不用|不宜|不需要|没必要)\s*尽快就医", guarded) is None
