"""Medical output safety guard."""

_MEDICAL_GUARD_REPLACEMENTS: dict[str, str] = {
    "不建议尽快就医": "建议尽快就医",
    "不需要尽快就医": "建议尽快就医",
    "确诊": "疑似",
    "别去医院": "建议尽快就医",
    "先观察几天": "建议尽快就医",
    "先观察": "建议尽快就医",
    "不用着急": "建议尽快就医",
    "不用就医": "建议尽快就医",
    "肯定没事": "建议尽快就医",
}


def _normalize_trailing_punctuation(text: str) -> str:
    normalized = text.rstrip()
    while normalized.endswith(("..", ".。", "。。")):
        if normalized.endswith(".."):
            normalized = f"{normalized[:-2]}。"
        else:
            normalized = f"{normalized[:-2]}。"
    return normalized


def enforce_output_guard(text: str) -> str:
    """Rewrite risky medical wording and enforce emergency guidance."""

    guarded = text
    for source, target in _MEDICAL_GUARD_REPLACEMENTS.items():
        guarded = guarded.replace(source, target)

    if "尽快就医" not in guarded:
        guarded = _normalize_trailing_punctuation(guarded)
        if guarded and guarded[-1] not in {"。", "！", "？"}:
            guarded = f"{guarded}。"
        guarded = f"{guarded}建议尽快就医"
    return guarded
