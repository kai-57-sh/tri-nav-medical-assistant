"""Unit tests for navigation_intent_detector node."""
import pytest
from src.chains.nodes.navigation_intent_detector import navigation_intent_detector


@pytest.mark.asyncio
async def test_navigation_only_request_short():
    """纯导航请求 - 短句."""
    state = {"text": "推荐医院", "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is True


@pytest.mark.asyncio
async def test_navigation_only_request_various_keywords():
    """测试各种医院关键词."""
    test_cases = [
        "我要挂号",
        "急诊在哪里",
        "请导航",
        "我要就医",
    ]

    for text in test_cases:
        state = {"text": text, "session_id": "test-123"}
        result = await navigation_intent_detector(state)
        assert result["navigation_only"] is True, f"Failed for: {text}"


@pytest.mark.asyncio
async def test_symptom_with_hospital_request():
    """症状 + 医院请求 → 应该走分诊流程."""
    state = {"text": "肚子疼，推荐医院", "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is False


@pytest.mark.asyncio
async def test_symptom_keywords_detection():
    """症状关键词检测."""
    test_cases = [
        "头疼，推荐医院",
        "我发烧了，医院在哪",
        "咳嗽不止，需要挂号",
        "头晕去医院",
        "呕吐和腹泻，急诊",
    ]

    for text in test_cases:
        state = {"text": text, "session_id": "test-123"}
        result = await navigation_intent_detector(state)
        assert result["navigation_only"] is False, f"Should require triage for: {text}"


@pytest.mark.asyncio
async def test_long_request_with_hospital_keyword():
    """长句（包含症状描述）即使有医院关键词也走分诊."""
    long_text = "您好，我最近感觉身体非常不舒服，特别是腹部经常疼痛，请问您能不能推荐一家好的医院帮我检查一下？"
    state = {"text": long_text, "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is False  # 长句 > 15字符


@pytest.mark.asyncio
async def test_negative_hospital_request():
    """否定医院请求."""
    test_cases = [
        "我不想去医院",
        "不想去医院，有没有其他办法",
        "无需就医",
    ]

    for text in test_cases:
        state = {"text": text, "session_id": "test-123"}
        result = await navigation_intent_detector(state)
        assert result["navigation_only"] is False, f"Should be negative for: {text}"


@pytest.mark.asyncio
async def test_no_hospital_keyword():
    """无医院关键词."""
    state = {"text": "我最近感觉不太舒服", "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is False


@pytest.mark.asyncio
async def test_empty_text():
    """空文本."""
    state = {"text": "", "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is False


@pytest.mark.asyncio
async def test_boundary_case_15_chars():
    """边界测试：正好15字符."""
    # 纯医院请求，15字符
    text = "推荐医院给我看" * 2  # 14字符
    state = {"text": text, "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is True

    # 纯医院请求，16字符
    text = "推荐医院给我看病" * 2  # 16字符
    state = {"text": text, "session_id": "test-123"}
    result = await navigation_intent_detector(state)
    assert result["navigation_only"] is False


@pytest.mark.asyncio
async def test_mixed_symptom_and_navigation():
    """混合症状和导航请求."""
    test_cases = [
        "头疼去医院挂什么科",
        "肚子疼，去哪家医院",
        "发烧38度，推荐医院",
    ]

    for text in test_cases:
        state = {"text": text, "session_id": "test-123"}
        result = await navigation_intent_detector(state)
        assert result["navigation_only"] is False, f"Should triage for: {text}"
