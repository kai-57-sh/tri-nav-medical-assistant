"""Input Validator node (Node 1)."""
import uuid
import re
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.config.settings import get_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


@safe_node("InputValidator")
async def input_validator(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user input format and generate session ID if needed.

    Validation Rules:
    - Text: Max 2000 chars (FR-001)
    - Image base64: Valid base64 string (FR-002)
    - GPS: Valid lat/lng ranges (FR-003, FR-004)
    - Session ID: UUID format or generate new (FR-005)

    Args:
        state: Current workflow state

    Returns:
        Updated state with validated input and session_id

    Raises:
        ValueError: If input validation fails
    """
    # Extract input fields
    text = state.get("text")
    image_base64 = state.get("image_base64")
    lat = state.get("lat")
    lng = state.get("lng")
    session_id = state.get("session_id")

    # Validate or generate session ID
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {session_id}")
    else:
        # Validate UUID format
        try:
            uuid.UUID(session_id)
        except ValueError:
            raise ValueError("session_id 格式无效，应为UUID")

    # Validate text input
    if text:
        text_length = len(text)
        if text_length > settings.max_text_length:
            raise ValueError(
                f"文本长度超过限制（{text_length}/{settings.max_text_length}字符）"
            )

        # Check for empty text (only whitespace)
        if not text.strip():
            raise ValueError("文本内容不能为空")

    # Validate image if provided
    if image_base64:
        # Remove data URL prefix if present
        if image_base64.startswith("data:image"):
            image_base64 = image_base64.split(",", 1)[1]

        # Validate base64 format
        if not re.match(r'^[A-Za-z0-9+/]+=*$', image_base64):
            raise ValueError("图片格式无效，应为base64编码")

        # Validate image size (rough estimate: base64 length / 4 * 3)
        estimated_bytes = len(image_base64) * 3 // 4
        max_size = 5 * 1024 * 1024  # 5MB
        if estimated_bytes > max_size:
            raise ValueError(f"图片大小超过限制（{estimated_bytes / 1024 / 1024:.1f}MB/5MB）")

    # Validate GPS coordinates if provided
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90):
            raise ValueError(f"纬度无效（{lat}），应在-90到90之间")

        if not (-180 <= lng <= 180):
            raise ValueError(f"经度无效（{lng}），应在-180到180之间")

    # Determine input type
    input_type = "image" if image_base64 else "text"

    # Initialize turn count for new sessions
    turn_count = state.get("turn_count", 1)

    # Return validated state
    return {
        "session_id": session_id,
        "input_type": input_type,
        "text": text,
        "image_base64": image_base64,
        "lat": lat,
        "lng": lng,
        "turn_count": turn_count,
        "status": state.get("status", "processing")
    }
