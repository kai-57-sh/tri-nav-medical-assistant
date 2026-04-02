"""Unit tests for triage_classifier node."""
from unittest.mock import patch

import pytest

from src.chains.nodes.triage_classifier import triage_classifier


@pytest.mark.asyncio
async def test_triage_classifier_routine(minimal_state, sample_symptom_schema, mock_llm_service):
    """Test triage classifier returns ROUTINE level."""
    state = minimal_state.copy()
    state["symptom_schema"] = sample_symptom_schema

    with patch("src.chains.nodes.triage_classifier.get_llm_service", return_value=mock_llm_service):
        result = await triage_classifier(state)

    # Should classify as ROUTINE
    assert result["llm_triage_level"] == "ROUTINE"
    assert result["llm_triage_reason"] is not None  # Changed from triage_reason to llm_triage_reason
    assert len(result["llm_recommended_departments"]) > 0
    assert len(result["llm_possible_causes"]) > 0
    assert len(result["llm_self_care_tips"]) > 0


@pytest.mark.asyncio
async def test_triage_classifier_emergency(minimal_state, mock_llm_service):
    """Test triage classifier returns EMERGENCY level."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "胸部",
        "symptoms": ["剧烈疼痛"],
        "duration": "30分钟",
        "severity": "严重",
        "accompanying_symptoms": ["呼吸困难", "出汗"]
    }

    mock_llm_service.classify_triage.return_value = {
        "triage_level": "EMERGENCY",
        "triage_reason": "症状提示可能的心脏紧急情况",
        "recommended_departments": ["急诊科", "心血管内科"],
        "possible_causes": [],
        "self_care_tips": [],
        "red_flags": ["胸痛超过30分钟", "伴随呼吸困难"]
    }

    with patch("src.chains.nodes.triage_classifier.get_llm_service", return_value=mock_llm_service):
        result = await triage_classifier(state)

    # Should classify as EMERGENCY
    assert result["llm_triage_level"] == "EMERGENCY"
    assert "急诊科" in result["llm_recommended_departments"]


@pytest.mark.asyncio
async def test_triage_classifier_self_care(minimal_state, sample_symptom_schema, mock_llm_service):
    """Test triage classifier returns SELF_CARE level."""
    state = minimal_state.copy()
    state["symptom_schema"] = sample_symptom_schema

    mock_llm_service.classify_triage.return_value = {
        "triage_level": "SELF_CARE",
        "triage_reason": "症状轻微，可居家观察",
        "recommended_departments": [],
        "possible_causes": ["轻微过敏"],
        "self_care_tips": ["避免接触过敏原", "多喝水"],
        "red_flags": []
    }

    with patch("src.chains.nodes.triage_classifier.get_llm_service", return_value=mock_llm_service):
        result = await triage_classifier(state)

    # Should classify as SELF_CARE
    assert result["llm_triage_level"] == "SELF_CARE"
    assert len(result["llm_self_care_tips"]) > 0


@pytest.mark.asyncio
async def test_triage_classifier_no_symptom_schema(minimal_state, mock_llm_service):
    """Test triage classifier handles missing symptom schema."""
    state = minimal_state.copy()
    state["symptom_schema"] = None

    with patch("src.chains.nodes.triage_classifier.get_llm_service", return_value=mock_llm_service):
        result = await triage_classifier(state)

    # Should NOT call LLM when no symptom schema (raises ValueError)
    mock_llm_service.classify_triage.assert_not_called()
    # Should return error status (ValueError caught by safe_node decorator)
    assert result.get("status") == "error"


@pytest.mark.asyncio
async def test_triage_classifier_conservative_bias(minimal_state, mock_llm_service):
    """Test triage classifier uses conservative bias."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "腹部",
        "symptoms": ["疼痛"],
        "duration": "2小时",
        "severity": "中度",
        "accompanying_symptoms": []
    }

    # LLM returns uncertain classification
    mock_llm_service.classify_triage.return_value = {
        "triage_level": "URGENT",  # Conservative escalation
        "triage_reason": "症状不典型，建议尽快就医",
        "recommended_departments": ["消化内科", "急诊科"],
        "possible_causes": ["可能胃炎", "可能阑尾炎"],
        "self_care_tips": ["暂禁食", "观察症状变化"],
        "red_flags": ["如疼痛加剧立即就医"]
    }

    with patch("src.chains.nodes.triage_classifier.get_llm_service", return_value=mock_llm_service):
        result = await triage_classifier(state)

    # Should use conservative classification
    assert result["llm_triage_level"] == "URGENT"
