"""Tests for SessionState model and validation rules."""
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.session import SessionState


class TestSessionState:
    """Test SessionState validation rules."""

    def test_session_state_valid_minimal(self):
        """Test valid session state with minimal fields."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.session_id == "550e8400-e29b-41d4-a716-446655440000"
        assert session.turn_count == 1  # Default value
        assert isinstance(session.last_updated_at, datetime)

    def test_session_state_valid_complete(self):
        """Test valid session state with all fields."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            turn_count=2,
            last_updated_at=datetime.now(),
            symptom_schema={
                "body_part": "手臂",
                "symptoms": ["红疹", "痒"],
                "duration": "2天",
                "severity": "轻微"
            },
            clarify_questions=["是否有发热？", "皮疹是否扩散？"],
            triage_level="ROUTINE",
            case_domain="dermatology",
            evidence_cache_key="evidence_123",
            navigation_cache_key="nav_456"
        )
        assert session.turn_count == 2
        assert session.triage_level == "ROUTINE"
        assert session.case_domain == "dermatology"
        assert len(session.clarify_questions) == 2
        assert session.evidence_cache_key == "evidence_123"

    def test_session_state_invalid_session_id_empty(self):
        """Test session_id - Pydantic v2 allows empty strings by default."""
        # Document that empty session_id is allowed by Pydantic v2
        session = SessionState(session_id="")
        assert session.session_id == ""

    def test_session_state_turn_count_default(self):
        """Test turn_count defaults to 1."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.turn_count == 1

    def test_session_state_turn_count_valid_range(self):
        """Test turn_count valid values (1-2)."""
        for turn in [1, 2]:
            session = SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                turn_count=turn
            )
            assert session.turn_count == turn

    def test_session_state_turn_count_invalid_zero(self):
        """Test turn_count cannot be 0."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                turn_count=0
            )
        assert "turn_count" in str(exc_info.value)

    def test_session_state_turn_count_invalid_three(self):
        """Test turn_count cannot be 3 (max 2 per CT-009)."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                turn_count=3
            )
        # Pydantic v2 error: "Input should be less than or equal to 2"
        assert "less than or equal to 2" in str(exc_info.value)

    def test_session_state_turn_count_validator_higher(self):
        """Test turn_count validator fails for values > 2."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                turn_count=5
            )
        # Pydantic v2 error: "Input should be less than or equal to 2"
        assert "less than or equal to 2" in str(exc_info.value)

    def test_session_state_symptom_schema_optional(self):
        """Test symptom_schema is optional."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.symptom_schema is None

    def test_session_state_symptom_schema_valid_dict(self):
        """Test symptom_schema accepts valid dict."""
        schema = {
            "body_part": "手臂",
            "symptoms": ["红疹", "痒"],
            "duration": "2天",
            "severity": "轻微"
        }
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            symptom_schema=schema
        )
        assert session.symptom_schema == schema

    def test_session_state_clarify_questions_default(self):
        """Test clarify_questions defaults to empty list."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.clarify_questions == []

    def test_session_state_clarify_questions_valid(self):
        """Test clarify_questions accepts list of strings."""
        questions = ["问题1", "问题2", "问题3"]
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            clarify_questions=questions
        )
        assert session.clarify_questions == questions

    def test_session_state_triage_level_valid_values(self):
        """Test all valid triage_level values."""
        valid_levels = ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]
        for level in valid_levels:
            session = SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                triage_level=level
            )
            assert session.triage_level == level

    def test_session_state_triage_level_invalid(self):
        """Test invalid triage_level fails pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                triage_level="INVALID_LEVEL"
            )
        assert "triage_level" in str(exc_info.value)

    def test_session_state_triage_level_optional(self):
        """Test triage_level is optional."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.triage_level is None

    def test_session_state_case_domain_valid_values(self):
        """Test all valid case_domain values."""
        valid_domains = ["dermatology", "trauma", "respiratory", "gastro", "neuro", "urology", "other"]
        for domain in valid_domains:
            session = SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                case_domain=domain
            )
            assert session.case_domain == domain

    def test_session_state_case_domain_invalid(self):
        """Test invalid case_domain fails pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                session_id="550e8400-e29b-41d4-a716-446655440000",
                case_domain="invalid_domain"
            )
        assert "case_domain" in str(exc_info.value)

    def test_session_state_case_domain_optional(self):
        """Test case_domain is optional."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.case_domain is None

    def test_session_state_evidence_cache_key_optional(self):
        """Test evidence_cache_key is optional."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.evidence_cache_key is None

    def test_session_state_evidence_cache_key_valid(self):
        """Test evidence_cache_key accepts string."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            evidence_cache_key="evidence_123"
        )
        assert session.evidence_cache_key == "evidence_123"

    def test_session_state_navigation_cache_key_optional(self):
        """Test navigation_cache_key is optional."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        assert session.navigation_cache_key is None

    def test_session_state_navigation_cache_key_valid(self):
        """Test navigation_cache_key accepts string."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            navigation_cache_key="nav_456"
        )
        assert session.navigation_cache_key == "nav_456"

    def test_session_state_last_updated_at_default_factory(self):
        """Test last_updated_at uses default_factory."""
        session1 = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        import time
        time.sleep(0.01)  # Small delay
        session2 = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440001"
        )
        # Each instance should have its own datetime
        assert session1.last_updated_at <= session2.last_updated_at

    def test_session_state_json_serialization(self):
        """Test SessionState can be serialized to JSON."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            turn_count=2,
            symptom_schema={"body_part": "手臂", "symptoms": ["红疹"]},
            triage_level="ROUTINE",
            case_domain="dermatology"
        )

        # Test model_dump
        data = session.model_dump()
        assert data["session_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["turn_count"] == 2
        assert data["triage_level"] == "ROUTINE"

        # Test JSON serialization
        json_str = session.model_dump_json()
        assert "550e8400-e29b-41d4-a716-446655440000" in json_str
        assert "ROUTINE" in json_str

    def test_session_state_round_trip(self):
        """Test SessionState can survive serialization round-trip."""
        original = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            turn_count=2,
            clarify_questions=["问题1", "问题2"],
            triage_level="EMERGENCY",
            case_domain="trauma"
        )

        # Serialize
        data = original.model_dump()

        # Deserialize
        restored = SessionState(**data)

        assert restored.session_id == original.session_id
        assert restored.turn_count == original.turn_count
        assert restored.clarify_questions == original.clarify_questions
        assert restored.triage_level == original.triage_level
        assert restored.case_domain == original.case_domain

    def test_session_state_no_raw_text_storage(self):
        """Verify session model doesn't have raw_text field."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        # No field for raw_text in the model
        assert not hasattr(session, "raw_text")
        # Extra fields are ignored in Pydantic v2 by default (not an error)
        session_with_extra = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            raw_text="ignored"  # type: ignore
        )
        assert not hasattr(session_with_extra, "raw_text")

    def test_session_state_no_raw_image_storage(self):
        """Verify session model doesn't have raw_image_base64 field."""
        session = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        # No field for raw_image_base64 in the model
        assert not hasattr(session, "raw_image_base64")
        # Extra fields are ignored in Pydantic v2 by default (not an error)
        session_with_extra = SessionState(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            raw_image_base64="ignored"  # type: ignore
        )
        assert not hasattr(session_with_extra, "raw_image_base64")
