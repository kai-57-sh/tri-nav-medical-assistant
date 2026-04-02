"""Medical output safety guard."""


def enforce_output_guard(text: str) -> str:
    """Rewrite risky medical wording and enforce emergency guidance."""

    guarded = text.replace("确诊", "疑似").replace("别去医院", "建议尽快就医")
    if "尽快就医" not in guarded:
        if guarded and guarded[-1] not in {"。", "！", "？"}:
            guarded = f"{guarded}。"
        guarded = f"{guarded}建议尽快就医"
    return guarded
