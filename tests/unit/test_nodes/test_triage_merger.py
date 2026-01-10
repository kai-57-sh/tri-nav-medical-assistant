"""Unit tests for triage_merger node."""
import pytest
from src.chains.nodes.triage_merger import triage_merger


@pytest.mark.asyncio
async def test_triage_merger_rule_overrides_llm(minimal_state):
    """Test triage merger prioritizes rule-based emergency."""
    state = minimal_state.copy()
    state["rule_triage_level"] = "EMERGENCY"
    state["llm_triage_level"] = "ROUTINE"
    state["red_flags_hit"] = ["RF_CHEST_PAIN"]
    state["triage_reason"] = "检测到胸痛红牌警报"
    state["recommended_departments"] = ["急诊科"]

    result = await triage_merger(state)

    # Rule should override LLM (more conservative)
    assert result["triage_level"] == "EMERGENCY"
    assert result["triage_source"] == "rule_engine"
    assert "急诊科" in result["recommended_departments"]


@pytest.mark.asyncio
async def test_triage_merger_llm_when_no_rule(minimal_state):
    """Test triage merger uses LLM when no rule triggered."""
    state = minimal_state.copy()
    state["rule_triage_level"] = None
    state["llm_triage_level"] = "ROUTINE"
    state["llm_triage_reason"] = "症状轻微，建议常规就诊"
    state["llm_recommended_departments"] = ["皮肤科"]
    state["llm_possible_causes"] = ["过敏性皮炎"]
    state["llm_self_care_tips"] = ["避免抓挠"]
    state["llm_red_flags"] = []

    result = await triage_merger(state)

    # Should use LLM classification
    assert result["triage_level"] == "ROUTINE"
    assert result["triage_source"] == "llm"
    assert result["triage_reason"] == "症状轻微，建议常规就诊"
    assert "皮肤科" in result["recommended_departments"]


@pytest.mark.asyncio
async def test_triage_merger_both_emergency(minimal_state):
    """Test triage merger when both rule and LLM say EMERGENCY."""
    state = minimal_state.copy()
    state["rule_triage_level"] = "EMERGENCY"
    state["llm_triage_level"] = "EMERGENCY"
    state["red_flags_hit"] = ["RF_CHEST_PAIN"]
    state["triage_reason"] = "检测到紧急情况"
    state["llm_triage_reason"] = "症状提示紧急情况"
    state["recommended_departments"] = ["急诊科"]
    state["llm_recommended_departments"] = ["急诊科", "心血管内科"]

    result = await triage_merger(state)

    # Should be EMERGENCY with rule_engine source
    assert result["triage_level"] == "EMERGENCY"
    assert result["triage_source"] == "rule_engine"


@pytest.mark.asyncio
async def test_triage_merger_default_when_uncertain(minimal_state):
    """Test triage merger defaults to URGENT when uncertain."""
    state = minimal_state.copy()
    state["rule_triage_level"] = None
    state["llm_triage_level"] = None

    result = await triage_merger(state)

    # Should default to URGENT (conservative)
    assert result["triage_level"] == "URGENT"
    assert result["triage_source"] == "default"


@pytest.mark.asyncio
async def test_triage_merger_preserves_llm_data(minimal_state):
    """Test triage merger preserves LLM-provided data."""
    state = minimal_state.copy()
    state["rule_triage_level"] = None
    state["llm_triage_level"] = "ROUTINE"
    state["llm_triage_reason"] = "轻微症状"
    state["llm_recommended_departments"] = ["皮肤科", "变态反应科"]
    state["llm_possible_causes"] = ["湿疹", "过敏性皮炎"]
    state["llm_self_care_tips"] = ["避免抓挠", "保持清洁", "使用温和护肤品"]
    state["llm_red_flags"] = ["如症状加重请就医"]

    result = await triage_merger(state)

    # Should preserve all LLM data
    assert result["triage_level"] == "ROUTINE"
    assert result["triage_reason"] == "轻微症状"
    assert "皮肤科" in result["recommended_departments"]
    assert len(result["possible_causes"]) == 2
    assert len(result["self_care_tips"]) == 3
    assert len(result["red_flags"]) == 1


@pytest.mark.asyncio
async def test_triage_merger_merges_departments(minimal_state):
    """Test triage merger merges department recommendations."""
    state = minimal_state.copy()
    state["rule_triage_level"] = "EMERGENCY"
    state["llm_triage_level"] = "EMERGENCY"
    state["recommended_departments"] = ["急诊科"]  # From rule
    state["llm_recommended_departments"] = ["急诊科", "心血管内科"]  # From LLM

    result = await triage_merger(state)

    # Should merge departments (rule takes precedence)
    assert "急诊科" in result["recommended_departments"]
    # May include additional departments from LLM


@pytest.mark.asyncio
async def test_triage_merger_uses_rule_reason(minimal_state):
    """Test triage merger uses rule-provided reason when available."""
    state = minimal_state.copy()
    state["rule_triage_level"] = "EMERGENCY"
    state["llm_triage_level"] = "ROUTINE"
    state["triage_reason"] = "检测到胸痛红牌警报，需要立即就医"
    state["llm_triage_reason"] = "可能肌肉拉伤"
    state["recommended_departments"] = ["急诊科"]

    result = await triage_merger(state)

    # Should use rule reason (more specific for emergency)
    assert result["triage_reason"] == "检测到胸痛红牌警报，需要立即就医"
    assert result["triage_source"] == "rule_engine"
