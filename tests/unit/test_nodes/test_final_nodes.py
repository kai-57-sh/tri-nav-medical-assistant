"""Unit tests for safety verification and final response nodes."""
from unittest.mock import AsyncMock, patch

import pytest

from src.chains.nodes.final_status_router import final_status_router
from src.chains.nodes.reasoning_verifier import reasoning_verifier
from src.chains.nodes.response_composer import compose_response
from src.chains.nodes.session_saver import session_save
from src.utils.constants import DISCLAIMER_TEXT


# Session Saver Tests
@pytest.mark.asyncio
async def test_session_saver_success(minimal_state, mock_redis_service, sample_symptom_schema):
    """Test session saver saves to Redis."""
    state = minimal_state.copy()
    state["session_id"] = "test-session"
    state["symptom_schema"] = sample_symptom_schema
    state["turn_count"] = 1

    with patch("src.chains.nodes.session_saver.get_redis_service", return_value=mock_redis_service):
        result = await session_save(state)

    # Should call save_session
    mock_redis_service.save_session.assert_called_once()
    # Session_saver is side-effect only, returns state unchanged (decorator merges empty dict with state)
    assert result["session_id"] == "test-session"
    assert result["symptom_schema"] == sample_symptom_schema


@pytest.mark.asyncio
async def test_session_saver_redis_unhealthy(minimal_state):
    """Test session saver handles Redis failure gracefully."""
    state = minimal_state.copy()
    state["session_id"] = "test-session"

    # Mock unhealthy Redis
    mock_redis = AsyncMock()
    mock_redis.is_healthy = False

    with patch("src.chains.nodes.session_saver.get_redis_service", return_value=mock_redis):
        result = await session_save(state)

    # Should not fail, just skip saving and return state unchanged
    assert result["session_id"] == "test-session"


# Response Composer Tests
def test_response_composer_clarification():
    """Test response composer formats clarification questions."""
    state = {
        "need_clarify": True,
        "clarify_questions": [
            "有发热吗？",
            "疼痛持续多久了？",
            "受过外伤吗？"
        ]
    }

    response = compose_response(state)

    # Should include clarification questions
    assert "为了更准确地评估您的情况" in response
    assert "1. 有发热吗？" in response
    assert "2. 疼痛持续多久了？" in response
    assert "3. 受过外伤吗？" in response


def test_response_composer_emergency():
    """Test response composer formats emergency response."""
    state = {
        "need_clarify": False,
        "triage_level": "EMERGENCY",
        "triage_reason": "检测到紧急情况",
        "recommended_departments": ["急诊科"],
        "possible_causes": [],
        "self_care_tips": [],
        "red_flags": ["需要立即就医"],
        "navigation_result": None,
        "weather_alert": None,
        "evidence_selected": None
    }

    response = compose_response(state)

    # Should include emergency formatting
    assert "⚠️ 紧急提醒" in response
    assert "检测到紧急情况" in response
    assert "急诊科" in response
    assert "需要立即就医" in response
    # Should have mandatory hotline tip
    assert "温馨提示" in response


def test_response_composer_routine_with_navigation():
    """Test response composer formats routine with navigation."""
    state = {
        "need_clarify": False,
        "triage_level": "ROUTINE",
        "triage_reason": "症状轻微",
        "recommended_departments": ["皮肤科"],
        "possible_causes": ["湿疹", "过敏性皮炎"],
        "self_care_tips": ["避免抓挠", "保持清洁"],
        "red_flags": [],
        "navigation_result": {
            "hospitals": [
                {
                    "rank": 1,
                    "name": "北京协和医院",
                    "reason": "三甲医院，距离最近"
                },
                {
                    "rank": 2,
                    "name": "北京医院",
                    "reason": "三甲医院"
                }
            ],
            "route_plan": {
                "summary": "距离1.5公里，约5分钟车程"
            }
        },
        "weather_alert": {
            "condition": "阴天",
            "temp_c": 15,
            "humidity": 70,
            "wind_speed_kmh": 12,
            "tip": "注意保暖"
        },
        "evidence_selected": [
            {
                "title": "Dermatitis Guidelines",
                "year": "2023",
                "type": "Guideline"
            }
        ]
    }

    response = compose_response(state)

    # Should include all sections
    assert "🏥 常规就诊" in response
    assert "皮肤科" in response
    assert "湿疹" in response
    assert "避免抓挠" in response
    assert "北京协和医院" in response
    assert "路线规划" in response
    assert "天气提示" in response
    assert "注意保暖" in response
    assert "参考文献" in response
    assert "温馨提示" in response


def test_response_composer_self_care():
    """Test response composer formats self-care response."""
    state = {
        "need_clarify": False,
        "triage_level": "SELF_CARE",
        "triage_reason": "可居家观察",
        "recommended_departments": [],
        "possible_causes": ["轻微感冒"],
        "self_care_tips": ["多喝水", "充分休息"],
        "red_flags": [],
        "navigation_result": None,
        "weather_alert": None,
        "evidence_selected": []
    }

    response = compose_response(state)

    # Should include self-care formatting
    assert "💡 居家观察" in response
    assert "可居家观察" in response
    assert "多喝水" in response
    assert "温馨提示" in response


def test_response_composer_mandatory_elements():
    """Test response composer includes mandatory disclaimer and hotline."""
    state = {
        "need_clarify": False,
        "triage_level": "ROUTINE",
        "triage_reason": "测试",
        "recommended_departments": [],
        "possible_causes": [],
        "self_care_tips": [],
        "red_flags": [],
        "navigation_result": None,
        "weather_alert": None,
        "evidence_selected": None
    }

    response = compose_response(state)

    # Should always include mandatory hotline tip
    assert "温馨提示" in response
    assert "拨打当地医疗热线" in response or "拨打医院电话" in response


# Reasoning Verifier Tests
@pytest.mark.asyncio
async def test_reasoning_verifier_safe_response(minimal_state, mock_llm_service):
    """Test reasoning verifier approves safe response."""
    state = minimal_state.copy()
    state["need_clarify"] = False
    state["triage_level"] = "ROUTINE"
    state["recommended_departments"] = ["皮肤科"]
    state["possible_causes"] = ["可能湿疹"]
    state["self_care_tips"] = ["保持清洁"]
    state["red_flags"] = []

    mock_llm_service.verify_safety.return_value = {
        "is_safe": True,
        "violations": [],
        "sanitized_content": "Safe response text"
    }

    with patch("src.chains.nodes.reasoning_verifier.get_llm_service", return_value=mock_llm_service):
        result = await reasoning_verifier(state)

    # Should approve and set final status
    assert result["final_response"] is not None
    assert result["status"] == "final"


@pytest.mark.asyncio
async def test_reasoning_verifier_needs_clarification(minimal_state, mock_llm_service):
    """Test reasoning verifier handles clarification needed."""
    state = minimal_state.copy()
    state["need_clarify"] = True
    state["clarify_questions"] = ["有发热吗？"]

    mock_llm_service.verify_safety.return_value = {
        "is_safe": True,
        "violations": [],
        "sanitized_content": "Safe clarification"
    }

    with patch("src.chains.nodes.reasoning_verifier.get_llm_service", return_value=mock_llm_service):
        result = await reasoning_verifier(state)

    # Should set need_more_info status
    assert result["status"] == "need_more_info"


@pytest.mark.asyncio
async def test_reasoning_verifier_unsafe_sanitized(minimal_state, mock_llm_service):
    """Test reasoning verifier sanitizes unsafe response."""
    state = minimal_state.copy()
    state["need_clarify"] = False
    state["triage_level"] = "ROUTINE"
    state["triage_reason"] = "诊断为皮肤问题"

    mock_llm_service.verify_safety.return_value = {
        "is_safe": False,
        "violations": ["diagnosis"],
        "sanitized_content": "Sanitized response without diagnosis"
    }

    with patch("src.chains.nodes.reasoning_verifier.get_llm_service", return_value=mock_llm_service):
        result = await reasoning_verifier(state)

    # Should use sanitized version
    assert result["final_response"] == "Sanitized response without diagnosis"


# Final Status Router Tests
@pytest.mark.asyncio
async def test_final_status_router_need_more_info(minimal_state):
    """Test final status router returns clarification response."""
    state = minimal_state.copy()
    state["status"] = "need_more_info"
    state["session_id"] = "test-123"
    state["clarify_questions"] = ["问题1", "问题2"]
    state["final_response"] = "Need more info"

    result = await final_status_router(state)

    # Should return clarification format
    assert result["status"] == "need_more_info"
    assert result["session_id"] == "test-123"
    assert result["clarify_questions"] == ["问题1", "问题2"]
    assert result["response"] == "Need more info"
    assert result["disclaimer"] == DISCLAIMER_TEXT


@pytest.mark.asyncio
async def test_final_status_router_final_response(minimal_state):
    """Test final status router returns final triage response."""
    state = minimal_state.copy()
    state["status"] = "final"
    state["session_id"] = "test-456"
    state["final_response"] = "Full assessment"
    state["triage_level"] = "ROUTINE"
    state["recommended_departments"] = ["皮肤科"]
    state["possible_causes"] = ["湿疹"]
    state["self_care_tips"] = ["保持清洁"]
    state["red_flags"] = []
    state["navigation_result"] = {"hospitals": []}
    state["evidence_selected"] = []

    result = await final_status_router(state)

    # Should return full response
    assert result["status"] == "final"
    assert result["session_id"] == "test-456"
    assert result["response"] == "Full assessment"
    assert result["disclaimer"] == DISCLAIMER_TEXT
    assert result["triage_level"] == "ROUTINE"
    assert "皮肤科" in result["recommended_departments"]


@pytest.mark.asyncio
async def test_final_status_router_error(minimal_state):
    """Test final status router returns error response."""
    state = minimal_state.copy()
    state["status"] = "error"
    state["session_id"] = "test-789"
    state["error_message"] = "系统错误"

    result = await final_status_router(state)

    # Should return error format
    assert result["status"] == "error"
    assert result["session_id"] == "test-789"
    assert "系统错误" in result["error_message"]


@pytest.mark.asyncio
async def test_final_status_router_no_error_message(minimal_state):
    """Test final status router provides default error message."""
    state = minimal_state.copy()
    state["status"] = "error"
    state["session_id"] = "test-000"
    state["error_message"] = None

    result = await final_status_router(state)

    # Should provide default error message
    assert result["status"] == "error"
    assert result["error_message"] == "系统错误，请稍后重试"
