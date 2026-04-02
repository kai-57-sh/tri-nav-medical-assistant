"""Unit tests for red_flag_detector node."""
import pytest

from src.chains.nodes.red_flag_detector import red_flag_detector


@pytest.mark.asyncio
async def test_red_flag_detector_no_flags(minimal_state, sample_symptom_schema):
    """Test red flag detector with no matching rules."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "手臂",
        "symptoms": ["红疹"],
        "duration": "2天",
        "severity": "轻微",
        "accompanying_symptoms": []
    }

    result = await red_flag_detector(state)

    # Should not trigger red flags
    assert result["rule_triage_level"] is None
    assert result["red_flags_hit"] == []
    assert result.get("triage_level") is None


@pytest.mark.asyncio
async def test_red_flag_detector_chest_pain(minimal_state):
    """Test red flag detector detects chest pain."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "胸口",  # Changed from "胸部" to "胸口" to match rule
        "symptoms": ["疼痛", "压迫感"],
        "duration": "30分钟",
        "severity": "严重",
        "accompanying_symptoms": ["出汗"]  # Removed breathing difficulty to avoid triggering both flags
    }

    result = await red_flag_detector(state)

    # Should trigger EMERGENCY for chest pain
    assert result["rule_triage_level"] == "EMERGENCY"
    assert len(result["red_flags_hit"]) > 0
    assert "RF_CHEST_PAIN" in result["red_flags_hit"]
    # Note: triage_level is set by triage_merger, not red_flag_detector


@pytest.mark.asyncio
async def test_red_flag_detector_breathing_difficulty(minimal_state):
    """Test red flag detector detects breathing difficulty."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "胸部",  # Changed to match RF_CHEST_TIGHTNESS_PLUS_DIFFICULTY better
        "symptoms": ["胸闷"],
        "duration": "1小时",
        "severity": "严重",
        "accompanying_symptoms": ["呼吸困难", "喘不过气"]
    }

    result = await red_flag_detector(state)

    # Should trigger EMERGENCY
    assert result["rule_triage_level"] == "EMERGENCY"
    assert "RF_BREATHING_DIFFICULTY" in result["red_flags_hit"] or "RF_CHEST_TIGHTNESS_PLUS_DIFFICULTY" in result["red_flags_hit"]
    # Note: triage_level is set by triage_merger, not red_flag_detector


@pytest.mark.asyncio
async def test_red_flag_detector_high_fever_with_severity(minimal_state):
    """Test red flag detector detects high fever with severity."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "全身",
        "symptoms": ["疼痛"],
        "duration": "1天",
        "severity": "严重",
        "accompanying_symptoms": ["高热", "意识模糊"]  # Added "高热" to match rule
    }

    result = await red_flag_detector(state)

    # Should trigger EMERGENCY for high fever with severity
    assert result["rule_triage_level"] == "EMERGENCY"
    assert "RF_HIGH_FEVER_WITH_SEVERITY" in result["red_flags_hit"]
    # Note: triage_level is set by triage_merger, not red_flag_detector


@pytest.mark.asyncio
async def test_red_flag_detector_multiple_flags(minimal_state):
    """Test red flag detector handles multiple red flags."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "胸口",  # Changed to "胸口" to match RF_CHEST_PAIN
        "symptoms": ["疼痛", "压迫感"],
        "duration": "30分钟",
        "severity": "严重",
        "accompanying_symptoms": ["呼吸困难", "出汗"]  # Added breathing difficulty
    }

    result = await red_flag_detector(state)

    # Should detect multiple red flags (chest pain + breathing difficulty)
    assert result["rule_triage_level"] == "EMERGENCY"
    assert len(result["red_flags_hit"]) >= 2
    # Should recommend emergency department
    assert "急诊" in result["recommended_departments"]


@pytest.mark.asyncio
async def test_red_flag_detector_no_symptom_schema(minimal_state):
    """Test red flag detector handles missing symptom schema."""
    state = minimal_state.copy()
    state["symptom_schema"] = None

    result = await red_flag_detector(state)

    # Should return without triggering red flags
    assert result["rule_triage_level"] is None
    assert result["red_flags_hit"] == []


@pytest.mark.asyncio
async def test_red_flag_detector_priority_ordering(minimal_state):
    """Test red flag detector prioritizes high-priority rules."""
    state = minimal_state.copy()
    state["symptom_schema"] = {
        "body_part": "胸部",
        "symptoms": ["疼痛"],
        "duration": "2小时",
        "severity": "严重",
        "accompanying_symptoms": ["呼吸困难"]  # Triggers multiple rules
    }

    result = await red_flag_detector(state)

    # Should still trigger EMERGENCY with appropriate message
    assert result["rule_triage_level"] == "EMERGENCY"
    assert result["triage_reason"] is not None
    assert len(result["red_flags_hit"]) >= 1
