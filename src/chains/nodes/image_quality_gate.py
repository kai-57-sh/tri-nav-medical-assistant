"""Image Quality Gate node (Node 3).

Checks if uploaded image meets quality requirements before processing.
If quality is insufficient, marks image as ignored and proceeds with text-only workflow.
"""
import base64
import binascii
import io
from typing import Any

from PIL import Image

from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


# Quality thresholds
MIN_IMAGE_DIMENSION = 200  # pixels
MAX_IMAGE_DIMENSION = 4096  # pixels
MIN_IMAGE_SIZE_BYTES = 10 * 1024  # 10KB
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


@safe_node("ImageQualityGate")
async def image_quality_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Validate image quality before vision processing.

    Checks:
    1. Image is not None
    2. Image dimensions are within acceptable range
    3. Image size is within acceptable range
    4. Image can be decoded successfully

    If any check fails, marks image_as_valid=False and proceeds with text-only workflow.

    Args:
        state: Current workflow state

    Returns:
        Updated state with image_as_valid flag
    """
    image_base64 = state.get("image_base64")
    session_id = state.get("session_id")

    # No image provided - that's OK, text-only workflow
    if not image_base64:
        logger.info("No image provided, using text-only workflow", extra={"session_id": session_id})
        return {"image_as_valid": False, "visual_findings": None}

    try:
        # Decode base64
        if "," in image_base64:
            # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
            image_base64 = image_base64.split(",", 1)[1]

        image_data = base64.b64decode(image_base64)

        # Check file size
        file_size = len(image_data)
        if file_size < MIN_IMAGE_SIZE_BYTES:
            logger.warning(
                f"Image too small: {file_size} bytes < {MIN_IMAGE_SIZE_BYTES}",
                extra={"session_id": session_id}
            )
            return {"image_as_valid": False, "visual_findings": None}

        if file_size > MAX_IMAGE_SIZE_BYTES:
            logger.warning(
                f"Image too large: {file_size} bytes > {MAX_IMAGE_SIZE_BYTES}",
                extra={"session_id": session_id}
            )
            return {"image_as_valid": False, "visual_findings": None}

        # Open image to check dimensions
        image = Image.open(io.BytesIO(image_data))

        width, height = image.size

        # Check dimensions
        if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
            logger.warning(
                f"Image dimensions too small: {width}x{height}",
                extra={"session_id": session_id}
            )
            return {"image_as_valid": False, "visual_findings": None}

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            logger.warning(
                f"Image dimensions too large: {width}x{height}",
                extra={"session_id": session_id}
            )
            return {"image_as_valid": False, "visual_findings": None}

        # All checks passed
        logger.info(
            f"Image quality check passed: {width}x{height}, {file_size} bytes",
            extra={"session_id": session_id}
        )

        return {"image_as_valid": True}

    except binascii.Error as e:
        logger.warning(f"Invalid base64 encoding: {e}", extra={"session_id": session_id})
        return {"image_as_valid": False, "visual_findings": None}

    except Exception as e:
        logger.warning(f"Image quality check failed: {e}", extra={"session_id": session_id})
        return {"image_as_valid": False, "visual_findings": None}
