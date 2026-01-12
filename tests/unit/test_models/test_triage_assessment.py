"""Tests for TriageAssessment model and validation rules."""
import pytest
from pydantic import ValidationError

from src.models.triage_assessment import TriageAssessment


class TestTriageAssessment:
    """Test TriageAssessment validation rules."""

    def test_triage_assessment_valid_emergency(self):
        """Test valid emergency triage assessment."""
        assessment = TriageAssessment(
            triage_level="EMERGENCY",
            triage_reason="检测到胸痛症状，建议立即急诊",
            triage_source="rule_engine",
            recommended_departments=["急诊科", "心内科"],
            possible_causes=["疑似心肌梗死"],
            self_care_tips=[],
            red_flags=["如出现呼吸困难/意识丧失，请立即呼叫急救"]
        )
        assert assessment.triage_level == "EMERGENCY"
        assert assessment.triage_source == "rule_engine"
        assert len(assessment.recommended_departments) == 2

    def test_triage_assessment_valid_urgent(self):
        """Test valid urgent triage assessment."""
        assessment = TriageAssessment(
            triage_level="URGENT",
            triage_reason="症状明显，需尽快就医",
            triage_source="llm",
            recommended_departments=["皮肤科"],
            possible_causes=["疑似过敏反应", "可能接触性皮炎"],
            self_care_tips=["避免抓挠患处"],
            red_flags=[]
        )
        assert assessment.triage_level == "URGENT"
        assert "尽快就医" in assessment.triage_reason

    def test_triage_assessment_valid_routine(self):
        """Test valid routine triage assessment."""
        assessment = TriageAssessment(
            triage_level="ROUTINE",
            triage_reason="症状轻微，无危险信号",
            triage_source="llm",
            recommended_departments=["皮肤科"],
            possible_causes=["疑似轻微皮炎", "相关过敏反应"],
            self_care_tips=["保持清洁", "避免刺激"],
            red_flags=["如症状加重请就医"]
        )
        assert assessment.triage_level == "ROUTINE"

    def test_triage_assessment_valid_self_care(self):
        """Test valid self-care triage assessment."""
        assessment = TriageAssessment(
            triage_level="SELF_CARE",
            triage_reason="症状轻微，可居家观察",
            triage_source="merged",
            recommended_departments=["全科"],
            possible_causes=["可能轻微皮疹"],
            self_care_tips=["保持休息", "多喝水", "观察症状变化"],
            red_flags=[]
        )
        assert assessment.triage_level == "SELF_CARE"

    def test_triage_assessment_invalid_triage_level(self):
        """Test invalid triage level."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="INVALID",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "triage_level" in str(exc_info.value)

    def test_triage_assessment_invalid_triage_reason_empty(self):
        """Test triage_reason cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "triage_reason" in str(exc_info.value)

    def test_triage_assessment_invalid_triage_reason_too_long(self):
        """Test triage_reason max length 500."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="a" * 501,
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "triage_reason" in str(exc_info.value)

    def test_triage_assessment_invalid_triage_source(self):
        """Test invalid triage_source."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="invalid",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "triage_source" in str(exc_info.value)

    def test_triage_assessment_invalid_departments_empty(self):
        """Test recommended_departments cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=[],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "recommended_departments" in str(exc_info.value)

    def test_triage_assessment_invalid_departments_too_many(self):
        """Test recommended_departments max is 5."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["科1", "科2", "科3", "科4", "科5", "科6"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
        assert "recommended_departments" in str(exc_info.value)

    def test_triage_assessment_invalid_possible_causes_too_many(self):
        """Test possible_causes max is 3."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=["疑似1", "疑似2", "疑似3", "疑似4"],
                self_care_tips=[],
                red_flags=[]
            )
        assert "possible_causes" in str(exc_info.value)

    def test_triage_assessment_qualified_language_pass(self):
        """Test validator: qualified language passes."""
        assessment = TriageAssessment(
            triage_level="ROUTINE",
            triage_reason="Test",
            triage_source="llm",
            recommended_departments=["全科"],
            possible_causes=["疑似过敏", "可能皮炎", "相关感染"],
            self_care_tips=[],
            red_flags=[]
        )
        assert len(assessment.possible_causes) == 3

    def test_triage_assessment_qualified_language_fail_no_qualifier(self):
        """Test validator: missing qualified language fails."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=["过敏反应", "皮炎"],
                self_care_tips=[],
                red_flags=[]
            )
        assert "Cause must use qualified language" in str(exc_info.value)

    def test_triage_assessment_qualified_language_fail_unqualified(self):
        """Test validator: '确诊' is not qualified."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=["确诊感冒"],
                self_care_tips=[],
                red_flags=[]
            )
        assert "Cause must use qualified language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_pass(self):
        """Test validator: non-prescriptive tips pass."""
        assessment = TriageAssessment(
            triage_level="SELF_CARE",
            triage_reason="Test",
            triage_source="llm",
            recommended_departments=["全科"],
            possible_causes=[],
            self_care_tips=["保持休息", "多喝水", "观察症状"],
            red_flags=[]
        )
        assert len(assessment.self_care_tips) == 3

    def test_triage_assessment_self_care_tips_fail_mg_dosage(self):
        """Test validator: 'mg' dosage is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["服用500mg药物"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_fail_次_dosage(self):
        """Test validator: '每次' is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["每次2片"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_fail_dosage(self):
        """Test validator: '剂量' is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["按照剂量服用"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_fail_片(self):
        """Test validator: '片' is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["服用2片药"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_fail_服用(self):
        """Test validator: '服用' is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["建议服用药物"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_fail_用药(self):
        """Test validator: '用药' is prescriptive."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=["按时用药"],
                red_flags=[]
            )
        assert "Self-care tip cannot contain prescriptive language" in str(exc_info.value)

    def test_triage_assessment_self_care_tips_too_many(self):
        """Test self_care_tips max is 10."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[f"建议{i}" for i in range(11)],
                red_flags=[]
            )
        assert "self_care_tips" in str(exc_info.value)

    def test_triage_assessment_red_flags_too_many(self):
        """Test red_flags max is 10."""
        with pytest.raises(ValidationError) as exc_info:
            TriageAssessment(
                triage_level="SELF_CARE",
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[f"警告{i}" for i in range(11)]
            )
        assert "red_flags" in str(exc_info.value)

    def test_triage_assessment_red_flags_hit_default(self):
        """Test red_flags_hit defaults to empty list."""
        assessment = TriageAssessment(
            triage_level="ROUTINE",
            triage_reason="Test",
            triage_source="llm",
            recommended_departments=["全科"],
            possible_causes=[],
            self_care_tips=[],
            red_flags=[]
        )
        assert assessment.red_flags_hit == []

    def test_triage_assessment_red_flags_hit_custom(self):
        """Test red_flags_hit can be set."""
        assessment = TriageAssessment(
            triage_level="EMERGENCY",
            triage_reason="Test",
            triage_source="rule_engine",
            recommended_departments=["急诊科"],
            possible_causes=[],
            self_care_tips=[],
            red_flags=["立即就医"],
            red_flags_hit=["RF_CHEST_PAIN", "RF_BREATHING_DIFFICULTY"]
        )
        assert len(assessment.red_flags_hit) == 2
        assert "RF_CHEST_PAIN" in assessment.red_flags_hit

    def test_triage_assessment_all_triage_sources(self):
        """Test all valid triage_source values."""
        valid_sources = ["rule_engine", "llm", "merged"]
        for source in valid_sources:
            assessment = TriageAssessment(
                triage_level="ROUTINE",
                triage_reason="Test",
                triage_source=source,
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
            assert assessment.triage_source == source

    def test_triage_assessment_all_triage_levels(self):
        """Test all valid triage_level values."""
        valid_levels = ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]
        for level in valid_levels:
            assessment = TriageAssessment(
                triage_level=level,
                triage_reason="Test",
                triage_source="llm",
                recommended_departments=["全科"],
                possible_causes=[],
                self_care_tips=[],
                red_flags=[]
            )
            assert assessment.triage_level == level

    def test_triage_assessment_json_serialization(self):
        """Test TriageAssessment can be serialized to JSON."""
        assessment = TriageAssessment(
            triage_level="ROUTINE",
            triage_reason="症状轻微",
            triage_source="llm",
            recommended_departments=["皮肤科"],
            possible_causes=["疑似过敏"],
            self_care_tips=["保持清洁"],
            red_flags=["如症状加重请就医"],
            red_flags_hit=["RF_ALLERGY_REACTION"]
        )

        # Test model_dump
        data = assessment.model_dump()
        assert data["triage_level"] == "ROUTINE"
        assert data["red_flags_hit"] == ["RF_ALLERGY_REACTION"]

        # Test JSON serialization
        json_str = assessment.model_dump_json()
        assert "ROUTINE" in json_str
        assert "RF_ALLERGY_REACTION" in json_str
