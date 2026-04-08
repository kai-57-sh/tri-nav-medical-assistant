"""Shared test fixtures for TriNav."""
import asyncio
import base64
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Disable LangSmith tracing during tests to avoid background executor threads.
os.environ["LANGCHAIN_TRACING_V2"] = "false"


@pytest.fixture
def event_loop():
    """Create an event loop that shuts down the default executor on teardown."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())
    loop.close()
    asyncio.set_event_loop(None)

@pytest.fixture
def sample_symptom_schema():
    """Sample symptom schema for tests."""
    return {
        "body_part": "手臂",
        "symptoms": ["红疹", "瘙痒"],
        "duration": "2天",
        "severity": "轻微",
        "accompanying_symptoms": [],
        "onset": "逐渐",
    }


@pytest.fixture
def minimal_state():
    """Minimal workflow state with required keys."""
    return {
        "session_id": "00000000-0000-0000-0000-000000000000",
        "text": "手臂红疹",
        "image_base64": None,
        "gps_lat": None,
        "gps_lng": None,
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
        "llm_triage_reason": None,
        "llm_recommended_departments": [],
        "llm_possible_causes": [],
        "llm_self_care_tips": [],
        "llm_red_flags": [],
        "red_flags_hit": [],
        "need_clarify": False,
        "navigation_only": False,
        "image_as_valid": False,
        "should_retrieve_evidence": False,
        "ncbi_query": "",
        "visual_findings": None,
        "evidence_selected": [],
        "navigation_result": None,
        "weather_alert": None,
        "case_domain": None,
        "final_response": None,
        "response": None,
        "disclaimer": None,
        "status": "processing",
        "error_message": None,
    }


@pytest.fixture
def mock_llm_service(sample_symptom_schema):
    """Mock LLM service with sane defaults."""
    mock = MagicMock()
    mock.extract_symptoms = AsyncMock(return_value=sample_symptom_schema)
    mock.classify_triage = AsyncMock(return_value={
        "triage_level": "ROUTINE",
        "triage_reason": "症状较轻，建议常规就诊",
        "recommended_departments": ["皮肤科"],
        "possible_causes": ["可能为过敏性皮炎"],
        "self_care_tips": ["避免抓挠", "保持清洁"],
        "red_flags": ["如出现呼吸困难请立即急诊"],
    })
    mock.generate_clarification_questions = AsyncMock(return_value=[])
    mock.extract_visual_features = AsyncMock(return_value={
        "type": "rash",
        "summary": "手臂红斑伴丘疹",
        "features": ["红斑", "丘疹"],
        "confidence": 0.8,
    })
    mock.verify_safety = AsyncMock(return_value={
        "is_safe": True,
        "violations": [],
        "sanitized_content": "安全响应",
    })
    mock.classify_domain = AsyncMock(return_value="皮肤科")
    return mock


@pytest.fixture
def mock_redis_service():
    """Mock Redis service with healthy defaults."""
    mock = MagicMock()
    mock.is_healthy = True
    mock.load_session = AsyncMock(return_value=None)
    mock.save_session = AsyncMock(return_value=True)
    mock.load_cached_result = AsyncMock(return_value=None)
    mock.cache_external_result = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_amap_service():
    """Mock Amap service for navigation."""
    mock = MagicMock()
    mock.search_hospitals = AsyncMock(return_value=[
        {
            "rank": 1,
            "name": "北京协和医院",
            "is_3a": True,
            "reason": "三甲综合医院，距离较近",
            "location": {"lat": 39.9139, "lng": 116.4170},
        },
        {
            "rank": 2,
            "name": "北京医院",
            "is_3a": True,
            "reason": "三甲综合医院",
            "location": {"lat": 39.9100, "lng": 116.4000},
        },
        {
            "rank": 3,
            "name": "朝阳医院",
            "is_3a": False,
            "reason": "距离较近，可作为备选",
            "location": {"lat": 39.9200, "lng": 116.4300},
        },
    ])
    mock.get_route = AsyncMock(return_value={
        "summary": "约5分钟车程",
        "distance": 1500,
        "duration": 300,
    })
    return mock


@pytest.fixture
def mock_weather_service():
    """Mock weather service for Open-Meteo."""
    mock = MagicMock()
    mock.get_weather = AsyncMock(return_value={
        "condition": "阴天",
        "temp_c": 15,
        "humidity": 70,
        "wind_speed_kmh": 12,
        "tip": "注意保暖",
    })
    return mock


@pytest.fixture
def mock_ncbi_service():
    """Mock NCBI service with sample articles."""
    mock = MagicMock()
    mock.search_and_retrieve = AsyncMock(return_value=[
        {"title": "Skin rash guideline", "year": "2022", "source": "Guideline J", "type": "Guideline"},
        {"title": "Dermatitis review", "year": "2023", "source": "Med J", "type": "Review"},
    ])
    return mock


@pytest.fixture
def sample_gps_coords():
    """Sample GPS coordinates (Beijing)."""
    return {"lat": 39.9042, "lng": 116.4074}


@pytest.fixture
def sample_image_base64():
    """Valid 1x1 PNG base64 string."""
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`"
        b"\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")


def parse_sse_frames(body: str) -> list[dict]:
    """Parse an SSE response body into structured frame dicts."""
    assert body.endswith("\n\n")
    raw_frames = [frame for frame in body.split("\n\n") if frame]
    parsed: list[dict] = []
    for frame in raw_frames:
        lines = frame.split("\n")
        entry: dict = {"raw": frame, "lines": lines}
        for line in lines:
            if line.startswith("event: "):
                entry["event"] = line.removeprefix("event: ")
            if line.startswith("data: "):
                entry["data"] = line.removeprefix("data: ")
        parsed.append(entry)
    return parsed
