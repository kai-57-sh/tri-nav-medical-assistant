"""Vision tool adapter for TriNav runtime."""

import base64
from typing import Any


def _validate_image_base64(payload: dict[str, Any]) -> str:
    image_base64 = payload.get("image_base64")
    if not isinstance(image_base64, str) or not image_base64.strip():
        raise ValueError("payload['image_base64'] must be a non-empty string")
    image_base64_s = image_base64.strip()
    padded_base64 = image_base64_s + ("=" * ((4 - len(image_base64_s) % 4) % 4))
    try:
        base64.b64decode(padded_base64, validate=True)
    except Exception as exc:
        raise ValueError("payload['image_base64'] must be valid base64 data") from exc

    return image_base64_s


def _validate_text(payload: dict[str, Any]) -> str | None:
    text = payload.get("text")
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("payload['text'] must be a string when provided")
    return text


def _get_llm_service() -> Any:
    from src.services.llm_service import get_llm_service

    return get_llm_service()


async def vision_extract_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapter from generic payload to visual feature extraction call."""

    image_base64 = _validate_image_base64(payload)
    text = _validate_text(payload)

    visual_findings = await _get_llm_service().extract_visual_features(
        image_base64=image_base64,
        text=text,
    )
    return {"visual": visual_findings}
