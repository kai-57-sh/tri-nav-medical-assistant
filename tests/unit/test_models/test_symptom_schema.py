"""Tests for SymptomSchema and VisualFindings models."""
import pytest
from pydantic import ValidationError

from src.models.symptom_schema import SymptomSchema, VisualFindings


class TestVisualFindings:
    """Test VisualFindings validation rules."""

    def test_visual_findings_valid_rash(self):
        """Test valid visual findings for rash type."""
        findings = VisualFindings(
            type="rash",
            summary="手臂红斑伴丘疹",
            features=["红斑", "丘疹", "肿胀"],
            confidence=0.85
        )
        assert findings.type == "rash"
        assert findings.confidence == 0.85

    def test_visual_findings_valid_wound(self):
        """Test valid visual findings for wound type."""
        findings = VisualFindings(
            type="wound",
            summary="手臂外伤伤口",
            features=["出血", "伤口长度3cm"],
            confidence=0.92
        )
        assert findings.type == "wound"

    def test_visual_findings_valid_unknown(self):
        """Test valid visual findings for unknown type."""
        findings = VisualFindings(
            type="unknown",
            summary="无法确定类型的皮损",
            features=["红肿"],
            confidence=0.5
        )
        assert findings.type == "unknown"

    def test_visual_findings_invalid_type(self):
        """Test invalid type value."""
        with pytest.raises(ValidationError) as exc_info:
            VisualFindings(
                type="burn",  # Invalid, not in enum
                summary="Test",
                features=[],
                confidence=0.8
            )
        assert "type" in str(exc_info.value)

    def test_visual_findings_invalid_summary_empty(self):
        """Test summary cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            VisualFindings(
                type="rash",
                summary="",
                features=[],
                confidence=0.8
            )
        assert "summary" in str(exc_info.value)

    def test_visual_findings_invalid_summary_too_long(self):
        """Test summary max length 500."""
        with pytest.raises(ValidationError) as exc_info:
            VisualFindings(
                type="rash",
                summary="a" * 501,
                features=[],
                confidence=0.8
            )
        assert "summary" in str(exc_info.value)

    def test_visual_findings_invalid_confidence_too_high(self):
        """Test confidence max is 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            VisualFindings(
                type="rash",
                summary="Test",
                features=[],
                confidence=1.5
            )
        assert "confidence" in str(exc_info.value)

    def test_visual_findings_invalid_confidence_too_low(self):
        """Test confidence min is 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            VisualFindings(
                type="rash",
                summary="Test",
                features=[],
                confidence=-0.1
            )
        assert "confidence" in str(exc_info.value)

    def test_visual_findings_features_default(self):
        """Test features defaults to empty list."""
        findings = VisualFindings(
            type="rash",
            summary="Test",
            confidence=0.8
        )
        assert findings.features == []

    def test_visual_findings_features_valid(self):
        """Test features accepts list of strings."""
        features = ["红斑", "丘疹", "水疱", "脱屑"]
        findings = VisualFindings(
            type="rash",
            summary="Test",
            features=features,
            confidence=0.9
        )
        assert findings.features == features

    def test_visual_findings_confidence_boundaries(self):
        """Test confidence boundary values."""
        # Test 0.0
        findings = VisualFindings(
            type="unknown",
            summary="Very uncertain",
            features=[],
            confidence=0.0
        )
        assert findings.confidence == 0.0

        # Test 1.0
        findings = VisualFindings(
            type="rash",
            summary="Very certain",
            features=[],
            confidence=1.0
        )
        assert findings.confidence == 1.0


class TestSymptomSchema:
    """Test SymptomSchema validation rules."""

    def test_symptom_schema_valid_minimal(self):
        """Test valid symptom schema with minimal required fields."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹", "痒"]
        )
        assert schema.body_part == "手臂"
        assert len(schema.symptoms) == 2
        assert schema.duration is None
        assert schema.severity is None

    def test_symptom_schema_valid_complete(self):
        """Test valid symptom schema with all fields."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹", "痒"],
            duration="2天",
            severity="轻微",
            accompanying_symptoms=["发热", "头痛"],
            onset="逐渐",
            visual_findings=VisualFindings(
                type="rash",
                summary="手臂红斑伴丘疹",
                features=["红斑", "丘疹"],
                confidence=0.85
            )
        )
        assert schema.duration == "2天"
        assert schema.severity == "轻微"
        assert len(schema.accompanying_symptoms) == 2
        assert schema.onset == "逐渐"
        assert schema.visual_findings is not None

    def test_symptom_schema_invalid_body_part_empty(self):
        """Test body_part cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="",
                symptoms=["红疹"]
            )
        assert "body_part" in str(exc_info.value)

    def test_symptom_schema_invalid_body_part_too_long(self):
        """Test body_part max length 50."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="a" * 51,
                symptoms=["红疹"]
            )
        assert "body_part" in str(exc_info.value)

    def test_symptom_schema_invalid_symptoms_empty(self):
        """Test symptoms cannot be empty list."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=[]
            )
        assert "symptoms" in str(exc_info.value)

    def test_symptom_schema_invalid_symptoms_too_many(self):
        """Test symptoms max is 10."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=[f"症状{i}" for i in range(11)]
            )
        assert "symptoms" in str(exc_info.value)

    def test_symptom_schema_invalid_duration_too_long(self):
        """Test duration max length 50."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=["红疹"],
                duration="a" * 51
            )
        assert "duration" in str(exc_info.value)

    def test_symptom_schema_valid_severity_values(self):
        """Test all valid severity values."""
        valid_severities = ["轻微", "中度", "严重"]
        for severity in valid_severities:
            schema = SymptomSchema(
                body_part="手臂",
                symptoms=["红疹"],
                severity=severity
            )
            assert schema.severity == severity

    def test_symptom_schema_invalid_severity(self):
        """Test invalid severity fails pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=["红疹"],
                severity="疼痛"  # Not in enum
            )
        assert "severity" in str(exc_info.value)

    def test_symptom_schema_accompanying_symptoms_default(self):
        """Test accompanying_symptoms defaults to empty list."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹"]
        )
        assert schema.accompanying_symptoms == []

    def test_symptom_schema_accompanying_symptoms_valid(self):
        """Test accompanying_symptoms accepts list."""
        symptoms = ["发热", "头痛", "乏力"]
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹"],
            accompanying_symptoms=symptoms
        )
        assert schema.accompanying_symptoms == symptoms

    def test_symptom_schema_valid_onset_values(self):
        """Test all valid onset values."""
        valid_onsets = ["突然", "逐渐"]
        for onset in valid_onsets:
            schema = SymptomSchema(
                body_part="手臂",
                symptoms=["红疹"],
                onset=onset
            )
            assert schema.onset == onset

    def test_symptom_schema_invalid_onset(self):
        """Test invalid onset fails pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=["红疹"],
                onset="快速"  # Not in enum
            )
        assert "onset" in str(exc_info.value)

    def test_symptom_schema_visual_findings_optional(self):
        """Test visual_findings is optional."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹"]
        )
        assert schema.visual_findings is None

    def test_symptom_schema_visual_findings_valid(self):
        """Test visual_findings accepts VisualFindings."""
        findings = VisualFindings(
            type="rash",
            summary="Test",
            features=["test"],
            confidence=0.9
        )
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹"],
            visual_findings=findings
        )
        assert schema.visual_findings.type == "rash"

    def test_symptom_schema_symptoms_min_items(self):
        """Test symptoms requires at least 1 item."""
        with pytest.raises(ValidationError) as exc_info:
            SymptomSchema(
                body_part="手臂",
                symptoms=[]
            )
        assert "symptoms" in str(exc_info.value)

    def test_symptom_schema_all_optional_fields_null(self):
        """Test all optional fields can be None."""
        schema = SymptomSchema(
            body_part="胸口",
            symptoms=["痛"]
        )
        assert schema.duration is None
        assert schema.severity is None
        assert schema.accompanying_symptoms == []
        assert schema.onset is None
        assert schema.visual_findings is None

    def test_symptom_schema_json_serialization(self):
        """Test SymptomSchema can be serialized to JSON."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹", "痒"],
            duration="2天",
            severity="轻微",
            accompanying_symptoms=["发热"],
            onset="逐渐",
            visual_findings=VisualFindings(
                type="rash",
                summary="手臂红斑",
                features=["红斑"],
                confidence=0.85
            )
        )

        # Test model_dump
        data = schema.model_dump()
        assert data["body_part"] == "手臂"
        assert len(data["symptoms"]) == 2
        assert data["severity"] == "轻微"
        assert "visual_findings" in data

        # Test JSON serialization
        json_str = schema.model_dump_json()
        assert "手臂" in json_str
        assert "红疹" in json_str

    def test_symptom_schema_round_trip(self):
        """Test SymptomSchema can survive serialization round-trip."""
        original = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹", "痒"],
            duration="2天",
            severity="轻微"
        )

        # Serialize
        data = original.model_dump()

        # Deserialize
        restored = SymptomSchema(**data)

        assert restored.body_part == original.body_part
        assert restored.symptoms == original.symptoms
        assert restored.duration == original.duration
        assert restored.severity == original.severity

    def test_visual_findings_json_serialization(self):
        """Test VisualFindings can be serialized to JSON."""
        findings = VisualFindings(
            type="rash",
            summary="手臂红斑伴丘疹",
            features=["红斑", "丘疹", "肿胀"],
            confidence=0.85
        )

        # Test model_dump
        data = findings.model_dump()
        assert data["type"] == "rash"
        assert len(data["features"]) == 3
        assert data["confidence"] == 0.85

        # Test JSON serialization
        json_str = findings.model_dump_json()
        assert "rash" in json_str
        assert "红斑" in json_str

    def test_symptom_schema_combined_with_visual_findings(self):
        """Test SymptomSchema with VisualFindings for image-based workflow."""
        schema = SymptomSchema(
            body_part="手臂",
            symptoms=["红疹", "痒"],
            duration="3天",
            severity="中度",
            accompanying_symptoms=["轻微发热"],
            onset="逐渐",
            visual_findings=VisualFindings(
                type="rash",
                summary="手臂散在红斑伴丘疹，部分区域有水疱",
                features=["红斑", "丘疹", "水疱", "肿胀"],
                confidence=0.92
            )
        )

        assert schema.visual_findings is not None
        assert schema.visual_findings.type == "rash"
        assert len(schema.visual_findings.features) == 4
        assert schema.visual_findings.confidence == 0.92
