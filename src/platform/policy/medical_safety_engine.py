"""Structured medical safety engine for output enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SafetyResult:
    """Structured safety enforcement output."""

    text: str
    risk_level: str
    matched_rules: list[str]


_NEGATED_SEEK_CARE_PATTERN = re.compile(r"(不建议|无需|不必|不用|不宜|不需要|没必要)\s*尽快就医")
_TERMINAL_PUNCTUATION = {"。", "！", "？"}

_MEDICAL_REWRITE_RULES: tuple[tuple[str, str, str], ...] = (
    ("rewrite.confirmed_diagnosis", "确诊", "疑似"),
    ("rewrite.delay_to_care.avoid_hospital", "别去医院", "建议尽快就医"),
    ("rewrite.delay_to_care.observe_days", "先观察几天", "建议尽快就医"),
    ("rewrite.delay_to_care.observe", "先观察", "建议尽快就医"),
    ("rewrite.delay_to_care.no_hurry", "不用着急", "建议尽快就医"),
    ("rewrite.delay_to_care.no_visit", "不用就医", "建议尽快就医"),
    ("rewrite.delay_to_care.overconfident", "肯定没事", "建议尽快就医"),
)


def _normalize_trailing_punctuation(text: str) -> str:
    normalized = text.rstrip()
    while normalized.endswith(("..", ".。", "。。")):
        normalized = f"{normalized[:-2]}。"
    return normalized


class MedicalSafetyEngine:
    """Detect and rewrite risky medical response language."""

    def enforce(self, text: str) -> SafetyResult:
        """Return rewritten text and structured safety metadata."""

        rewritten = text if isinstance(text, str) else ""
        matched_rules: list[str] = []

        rewritten, negated_count = _NEGATED_SEEK_CARE_PATTERN.subn("建议尽快就医", rewritten)
        if negated_count > 0:
            matched_rules.append("rewrite.negated_seek_care")

        for rule_id, source, target in _MEDICAL_REWRITE_RULES:
            if source in rewritten:
                rewritten = rewritten.replace(source, target)
                matched_rules.append(rule_id)

        rewritten = _normalize_trailing_punctuation(rewritten)
        if matched_rules and "尽快就医" not in rewritten:
            if rewritten and rewritten[-1] not in _TERMINAL_PUNCTUATION:
                rewritten = f"{rewritten}。"
            rewritten = f"{rewritten}建议尽快就医"
            matched_rules.append("guidance.appended_timely_care")

        return SafetyResult(
            text=rewritten,
            risk_level="high" if matched_rules else "low",
            matched_rules=matched_rules,
        )
