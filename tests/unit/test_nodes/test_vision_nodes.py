"""Unit tests for vision processing nodes."""
import pytest
from src.chains.nodes.image_quality_gate import image_quality_gate
from src.chains.nodes.vision_extract import vision_extract
from unittest.mock import patch, AsyncMock
import base64


@pytest.mark.asyncio
async def test_image_quality_gate_valid_image(minimal_state, sample_image_base64):
    """Test image quality gate accepts valid image."""
    state = minimal_state.copy()
    state["image_base64"] = sample_image_base64

    # Mock the size and dimension checks to allow small test image
    with patch("src.chains.nodes.image_quality_gate.MIN_IMAGE_SIZE_BYTES", 10), \
         patch("src.chains.nodes.image_quality_gate.MIN_IMAGE_DIMENSION", 1):
        result = await image_quality_gate(state)

    # Small test image should pass with mocked size limits
    assert result["image_as_valid"] is True
    assert result.get("visual_findings") is None


@pytest.mark.asyncio
async def test_image_quality_gate_no_image(minimal_state):
    """Test image quality gate handles missing image."""
    state = minimal_state.copy()
    state["image_base64"] = None

    result = await image_quality_gate(state)

    # Should handle gracefully
    assert result["image_as_valid"] is False


@pytest.mark.asyncio
async def test_image_quality_gate_invalid_base64(minimal_state):
    """Test image quality gate rejects invalid base64."""
    state = minimal_state.copy()
    state["image_base64"] = "not-valid-base64!!!"

    result = await image_quality_gate(state)

    # Should reject invalid base64
    assert result["image_as_valid"] is False


@pytest.mark.asyncio
async def test_image_quality_gate_too_large(minimal_state):
    """Test image quality gate rejects oversized image."""
    state = minimal_state.copy()
    # Create base64 for 6MB image (exceeds 5MB limit)
    large_data = "x" * (6 * 1024 * 1024)
    large_b64 = base64.b64encode(large_data.encode()).decode()
    state["image_base64"] = large_b64

    result = await image_quality_gate(state)

    # Should reject oversized image
    assert result["image_as_valid"] is False


@pytest.mark.asyncio
async def test_vision_extract_valid_image(minimal_state, sample_image_base64, mock_llm_service):
    """Test vision extract processes valid image."""
    state = minimal_state.copy()
    state["image_base64"] = sample_image_base64
    state["image_as_valid"] = True
    state["text"] = "手臂上出现红疹"

    mock_llm_service.extract_visual_features.return_value = {
        "type": "rash",
        "summary": "手臂红斑伴丘疹",
        "features": ["红斑", "丘疹"],
        "confidence": 0.8
    }

    with patch("src.chains.nodes.vision_extract.get_llm_service", return_value=mock_llm_service):
        result = await vision_extract(state)

    # Should extract visual findings
    assert result["visual_findings"] is not None
    assert result["visual_findings"]["type"] == "rash"


@pytest.mark.asyncio
async def test_vision_extract_invalid_image(minimal_state):
    """Test vision extract skips invalid image."""
    state = minimal_state.copy()
    state["image_base64"] = "some-image"
    state["image_as_valid"] = False

    result = await vision_extract(state)

    # Should skip processing
    assert result["visual_findings"] is None


@pytest.mark.asyncio
async def test_vision_extract_no_image(minimal_state):
    """Test vision extract handles missing image."""
    state = minimal_state.copy()
    state["image_base64"] = None
    state["image_as_valid"] = False

    result = await vision_extract(state)

    # Should return None
    assert result["visual_findings"] is None


@pytest.mark.asyncio
async def test_vision_extract_llm_failure(minimal_state, sample_image_base64):
    """Test vision extract handles LLM failure gracefully."""
    state = minimal_state.copy()
    state["image_base64"] = sample_image_base64
    state["image_as_valid"] = True
    state["text"] = "皮肤问题"

    mock_llm = AsyncMock()
    mock_llm.extract_visual_features = AsyncMock(side_effect=Exception("Vision API failed"))

    with patch("src.chains.nodes.vision_extract.get_llm_service", return_value=mock_llm):
        result = await vision_extract(state)

    # Should degrade gracefully
    assert result["visual_findings"] is None
