"""Shared fixtures and configuration for tests."""
import os
import sys
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def sample_session_id():
    """Sample session ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_text_input():
    """Sample text input for testing."""
    return "手臂出现红疹，有点痒，持续2天"


@pytest.fixture
def sample_gps_coords():
    """Sample GPS coordinates for testing."""
    return {"lat": 39.9042, "lng": 116.4074}  # Beijing


@pytest.fixture
def sample_image_base64():
    """Sample base64 encoded image for testing."""
    # Minimal 1x1 red PNG in base64
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


@pytest.fixture
def sample_large_image_base64():
    """Sample larger base64 encoded image (>10KB) for testing."""
    # Create a base64 string that's larger than 10KB by repeating the small image
    small_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    # Repeat to make it larger than 10KB (need ~13.7KB base64 to get 10KB decoded)
    return small_image * 200  # ~14KB base64


@pytest.fixture
def minimal_state(sample_session_id, sample_text_input):
    """Minimal state for node testing."""
    return {
        "session_id": sample_session_id,
        "text": sample_text_input,
        "image_base64": None,
        "lat": None,
        "lng": None,
        "turn_count": 1,
        "symptom_schema": None,
        "clarify_questions": [],
        "triage_level": None,
        "triage_source": None,
        "triage_reason": None,
        "recommended_departments": [],
        "possible_causes": [],
        "self_care_tips": [],
        "red_flags": [],
        "rule_triage_level": None,
        "llm_triage_level": None,
        "red_flags_hit": [],
        "need_clarify": False,
        "image_as_valid": False,
        "should_retrieve_evidence": False,
        "ncbi_query": "",
        "visual_findings": None,
        "evidence_selected": None,
        "navigation_result": None,
        "weather_alert": None,
        "case_domain": None,
        "final_response": None,
        "status": "processing",
        "error_message": None,
    }


@pytest.fixture
def sample_symptom_schema():
    """Sample symptom schema for testing."""
    return {
        "body_part": "手臂",
        "symptoms": ["红疹", "瘙痒"],
        "duration": "2天",
        "severity": "轻微",
        "accompanying_symptoms": ["发热"],
        "visual_findings": None
    }


@pytest.fixture
def sample_visual_findings():
    """Sample visual findings for testing."""
    return {
        "body_part": "手臂",
        "visual_symptoms": ["红斑", "丘疹"],
        "distribution": "散在",
        "severity": "轻微"
    }


@pytest.fixture
def mock_redis_service():
    """Mock Redis service for testing."""
    mock = AsyncMock()
    mock.is_healthy = True
    mock.load_session = AsyncMock(return_value=None)
    mock.save_session = AsyncMock()
    mock.load_cached_result = AsyncMock(return_value=None)
    mock.cache_external_result = AsyncMock()
    return mock


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = AsyncMock()
    mock.extract_symptoms = AsyncMock(return_value={
        "body_part": "手臂",
        "symptoms": ["红疹"],
        "duration": "2天",
        "severity": "轻微",
        "accompanying_symptoms": []
    })
    mock.classify_triage = AsyncMock(return_value={
        "triage_level": "ROUTINE",
        "triage_reason": "症状轻微，无紧急指征",
        "recommended_departments": ["皮肤科"],
        "possible_causes": ["过敏性皮炎", "湿疹"],
        "self_care_tips": ["避免抓挠", "保持清洁"],
        "red_flags": []
    })
    mock.verify_safety = AsyncMock(return_value={
        "is_safe": True,
        "violations": [],
        "sanitized_content": "Safe response"
    })
    mock.extract_visual_features = AsyncMock(return_value={
        "body_part": "手臂",
        "visual_symptoms": ["红斑"],
        "distribution": "局限性"
    })
    mock.generate_clarification_questions = AsyncMock(return_value=[
        "有发热吗？",
        "症状在加重吗？"
    ])
    mock.classify_domain = AsyncMock(return_value="皮肤科")
    return mock


@pytest.fixture
def mock_amap_service():
    """Mock Amap service for testing."""
    mock = AsyncMock()
    mock.search_hospitals = AsyncMock(return_value=[
        {
            "rank": 1,
            "is_3a": True,
            "name": "北京协和医院",
            "distance_m": 1500,
            "location": {"lat": 39.9139, "lng": 116.4170},
            "reason": "三甲医院，距离最近，综合实力强"
        },
        {
            "rank": 2,
            "is_3a": True,
            "name": "北京医院",
            "distance_m": 2500,
            "location": {"lat": 39.9042, "lng": 116.4074},
            "reason": "三甲医院，交通便利"
        },
        {
            "rank": 3,
            "is_3a": False,
            "name": "东城区社区卫生服务中心",
            "distance_m": 500,
            "location": {"lat": 39.9100, "lng": 116.4100},
            "reason": "社区医院，距离近"
        }
    ])
    mock.get_route = AsyncMock(return_value={
        "distance": 1500,
        "duration": 300,
        "summary": "距离1.5公里，约5分钟车程"
    })
    return mock


@pytest.fixture
def mock_ncbi_service():
    """Mock NCBI service for testing."""
    mock = AsyncMock()
    mock.search_and_retrieve = AsyncMock(return_value=[
        {
            "pmid": "12345678",
            "title": "Guidelines for dermatitis management",
            "year": "2023",
            "source": "Journal of Dermatology",
            "type": "Guideline"
        },
        {
            "pmid": "87654321",
            "title": "Systematic review of allergic reactions",
            "year": "2022",
            "source": "Allergy Journal",
            "type": "SystematicReview"
        }
    ])
    return mock


@pytest.fixture
def mock_weather_service():
    """Mock Weather service for testing."""
    mock = AsyncMock()
    mock.get_weather = AsyncMock(return_value={
        "summary": "阴天，气温15°C",
        "tips": ["注意保暖", "路面湿滑"]
    })
    return mock


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("QWEN_API_KEY", "test-api-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("AMAP_API_KEY", "test-amap-key")
