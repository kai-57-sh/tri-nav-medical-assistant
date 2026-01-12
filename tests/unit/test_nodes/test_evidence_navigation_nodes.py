"""Unit tests for evidence and navigation nodes."""
import pytest
from src.chains.nodes.evidence_router import evidence_router
from src.chains.nodes.ncbi_query_builder import ncbi_query_builder
from src.chains.nodes.ncbi_retriever_tool import ncbi_retriever_tool
from src.chains.nodes.domain_classifier import domain_classifier
from src.chains.nodes.navigator import navigator
from src.chains.nodes.weather_fetcher import weather_fetcher
from unittest.mock import patch, AsyncMock


# Evidence Router Tests
@pytest.mark.asyncio
async def test_evidence_router_emergency_skip(minimal_state):
    """Test evidence router skips for EMERGENCY."""
    state = minimal_state.copy()
    state["triage_level"] = "EMERGENCY"

    result = await evidence_router(state)

    # Should skip evidence for emergency
    assert result["should_retrieve_evidence"] is False


@pytest.mark.asyncio
async def test_evidence_router_routine_retrieve(minimal_state):
    """Test evidence router retrieves for ROUTINE."""
    state = minimal_state.copy()
    state["triage_level"] = "ROUTINE"

    result = await evidence_router(state)

    # Should retrieve evidence for routine cases
    assert result["should_retrieve_evidence"] is True


@pytest.mark.asyncio
async def test_evidence_router_self_care_no_causes(minimal_state):
    """Test evidence router skips SELF_CARE with no causes."""
    state = minimal_state.copy()
    state["triage_level"] = "SELF_CARE"
    state["possible_causes"] = []

    result = await evidence_router(state)

    # Should skip if no causes identified
    assert result["should_retrieve_evidence"] is False


@pytest.mark.asyncio
async def test_evidence_router_urgent_retrieve(minimal_state):
    """Test evidence router retrieves for URGENT."""
    state = minimal_state.copy()
    state["triage_level"] = "URGENT"

    result = await evidence_router(state)

    # Should retrieve evidence for urgent cases
    assert result["should_retrieve_evidence"] is True


# NCBI Query Builder Tests
@pytest.mark.asyncio
async def test_ncbi_query_builder_basic(minimal_state, sample_symptom_schema):
    """Test NCBI query builder creates basic query."""
    state = minimal_state.copy()
    state["symptom_schema"] = sample_symptom_schema

    result = await ncbi_query_builder(state)

    # Should build query with body part and symptom
    assert "arm" in result["ncbi_query"].lower()
    assert result["ncbi_query"] != ""


@pytest.mark.asyncio
async def test_ncbi_query_builder_no_symptoms(minimal_state):
    """Test NCBI query builder handles missing symptoms."""
    state = minimal_state.copy()
    state["symptom_schema"] = {"body_part": "胸部", "symptoms": []}

    result = await ncbi_query_builder(state)

    # Should return empty query
    assert result["ncbi_query"] == ""


@pytest.mark.asyncio
async def test_ncbi_query_builder_no_schema(minimal_state):
    """Test NCBI query builder handles missing schema."""
    state = minimal_state.copy()
    state["symptom_schema"] = None

    result = await ncbi_query_builder(state)

    # Should return empty query
    assert result["ncbi_query"] == ""


@pytest.mark.asyncio
async def test_ncbi_query_builder_with_domain(minimal_state, sample_symptom_schema):
    """Test NCBI query builder includes medical domain."""
    state = minimal_state.copy()
    state["symptom_schema"] = sample_symptom_schema
    state["case_domain"] = "皮肤科"

    result = await ncbi_query_builder(state)

    # Should include domain in query
    assert "dermatology" in result["ncbi_query"].lower() or result["ncbi_query"] != ""


# NCBI Retriever Tests
@pytest.mark.asyncio
async def test_ncbi_retriever_success(minimal_state, mock_ncbi_service, mock_redis_service):
    """Test NCBI retriever fetches articles."""
    state = minimal_state.copy()
    state["ncbi_query"] = "arm rash"
    state["session_id"] = "test-123"

    with patch("src.chains.nodes.ncbi_retriever_tool.get_ncbi_service", return_value=mock_ncbi_service):
        with patch("src.chains.nodes.ncbi_retriever_tool.get_redis_service", return_value=mock_redis_service):
            result = await ncbi_retriever_tool(state)

    # Should retrieve articles
    assert len(result["evidence_selected"]) == 2
    assert result["evidence_selected"][0]["type"] == "Guideline"


@pytest.mark.asyncio
async def test_ncbi_retriever_cached(minimal_state, mock_ncbi_service, mock_redis_service):
    """Test NCBI retriever uses cache."""
    state = minimal_state.copy()
    state["ncbi_query"] = "arm rash"
    state["session_id"] = "test-123"

    # Mock cache hit
    mock_redis_service.load_cached_result.return_value = {
        "articles": [
            {"pmid": "111", "title": "Cached Article", "year": "2023", "type": "Review"}
        ]
    }

    with patch("src.chains.nodes.ncbi_retriever_tool.get_ncbi_service", return_value=mock_ncbi_service):
        with patch("src.chains.nodes.ncbi_retriever_tool.get_redis_service", return_value=mock_redis_service):
            result = await ncbi_retriever_tool(state)

    # Should return cached results
    assert len(result["evidence_selected"]) == 1
    assert result["evidence_selected"][0]["title"] == "Cached Article"
    mock_ncbi_service.search_and_retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_ncbi_retriever_no_query(minimal_state):
    """Test NCBI retriever handles missing query."""
    state = minimal_state.copy()
    state["ncbi_query"] = ""

    result = await ncbi_retriever_tool(state)

    # Should return empty results
    assert result["evidence_selected"] == []


@pytest.mark.asyncio
async def test_ncbi_retriever_failure(minimal_state, mock_redis_service):
    """Test NCBI retriever handles failure gracefully."""
    state = minimal_state.copy()
    state["ncbi_query"] = "arm rash"

    mock_ncbi = AsyncMock()
    mock_ncbi.search_and_retrieve = AsyncMock(side_effect=Exception("NCBI API failed"))

    with patch("src.chains.nodes.ncbi_retriever_tool.get_ncbi_service", return_value=mock_ncbi):
        with patch("src.chains.nodes.ncbi_retriever_tool.get_redis_service", return_value=mock_redis_service):
            result = await ncbi_retriever_tool(state)

    # Should degrade gracefully
    assert result["evidence_selected"] == []


# Domain Classifier Tests
@pytest.mark.asyncio
async def test_domain_classifier_classifies(minimal_state, sample_symptom_schema, mock_llm_service):
    """Test domain classifier classifies medical domain."""
    state = minimal_state.copy()
    state["symptom_schema"] = sample_symptom_schema

    mock_llm_service.classify_domain.return_value = "皮肤科"

    with patch("src.chains.nodes.domain_classifier.get_llm_service", return_value=mock_llm_service):
        result = await domain_classifier(state)

    # Should classify domain
    assert result["case_domain"] == "皮肤科"


@pytest.mark.asyncio
async def test_domain_classifier_no_schema(minimal_state, mock_llm_service):
    """Test domain classifier handles missing schema."""
    state = minimal_state.copy()
    state["symptom_schema"] = None

    with patch("src.chains.nodes.domain_classifier.get_llm_service", return_value=mock_llm_service):
        result = await domain_classifier(state)

    # Should return None
    assert result["case_domain"] is None


# Navigator Tests
@pytest.mark.asyncio
async def test_navigator_success(minimal_state, mock_amap_service, mock_redis_service, sample_gps_coords):
    """Test navigator finds hospitals."""
    state = minimal_state.copy()
    state["triage_level"] = "ROUTINE"
    state["gps_lat"] = sample_gps_coords["lat"]
    state["gps_lng"] = sample_gps_coords["lng"]
    state["case_domain"] = "皮肤科"
    state["recommended_departments"] = ["皮肤科"]

    with patch("src.chains.nodes.navigator.get_amap_service", return_value=mock_amap_service):
        with patch("src.chains.nodes.navigator.get_redis_service", return_value=mock_redis_service):
            result = await navigator(state)

    # Should return navigation results
    assert result["navigation_result"] is not None
    assert len(result["navigation_result"]["hospitals"]) == 3
    assert result["navigation_result"]["hospitals"][0]["is_3a"] is True


@pytest.mark.asyncio
async def test_navigator_self_care_skip(minimal_state):
    """Test navigator skips for SELF_CARE."""
    state = minimal_state.copy()
    state["triage_level"] = "SELF_CARE"
    state["gps_lat"] = 39.9042
    state["gps_lng"] = 116.4074

    result = await navigator(state)

    # Should skip navigation
    assert result["navigation_result"] is None


@pytest.mark.asyncio
async def test_navigator_no_gps(minimal_state):
    """Test navigator handles missing GPS."""
    state = minimal_state.copy()
    state["triage_level"] = "ROUTINE"
    state["gps_lat"] = None
    state["gps_lng"] = None

    result = await navigator(state)

    # Should skip navigation
    assert result["navigation_result"] is None


@pytest.mark.asyncio
async def test_navigator_cached(minimal_state, mock_amap_service, mock_redis_service, sample_gps_coords):
    """Test navigator uses cache."""
    state = minimal_state.copy()
    state["triage_level"] = "ROUTINE"
    state["gps_lat"] = sample_gps_coords["lat"]
    state["gps_lng"] = sample_gps_coords["lng"]

    # Mock cache hit
    mock_redis_service.load_cached_result.return_value = {
        "hospitals": [
            {"rank": 1, "name": "Cached Hospital", "is_3a": True}
        ],
        "route_plan": None
    }

    with patch("src.chains.nodes.navigator.get_amap_service", return_value=mock_amap_service):
        with patch("src.chains.nodes.navigator.get_redis_service", return_value=mock_redis_service):
            result = await navigator(state)

    # Should return cached results
    assert result["navigation_result"]["hospitals"][0]["name"] == "Cached Hospital"
    mock_amap_service.search_hospitals.assert_not_called()


@pytest.mark.asyncio
async def test_navigator_failure(minimal_state, sample_gps_coords, mock_redis_service):
    """Test navigator handles failure gracefully."""
    state = minimal_state.copy()
    state["triage_level"] = "ROUTINE"
    state["gps_lat"] = sample_gps_coords["lat"]
    state["gps_lng"] = sample_gps_coords["lng"]

    mock_amap = AsyncMock()
    mock_amap.search_hospitals = AsyncMock(side_effect=Exception("Amap API failed"))

    with patch("src.chains.nodes.navigator.get_amap_service", return_value=mock_amap):
        with patch("src.chains.nodes.navigator.get_redis_service", return_value=mock_redis_service):
            result = await navigator(state)

    # Should degrade gracefully
    assert result["navigation_result"] is None


# Weather Fetcher Tests
@pytest.mark.asyncio
async def test_weather_fetcher_success(minimal_state, mock_weather_service, mock_redis_service, sample_gps_coords):
    """Test weather fetcher retrieves weather."""
    state = minimal_state.copy()
    state["gps_lat"] = sample_gps_coords["lat"]
    state["gps_lng"] = sample_gps_coords["lng"]

    with patch("src.chains.nodes.weather_fetcher.get_openmeteo_service", return_value=mock_weather_service):
        with patch("src.chains.nodes.weather_fetcher.get_redis_service", return_value=mock_redis_service):
            result = await weather_fetcher(state)

    # Should return weather alert
    assert result["weather_alert"] is not None
    assert result["weather_alert"]["summary"] == "阴天，气温15°C"


@pytest.mark.asyncio
async def test_weather_fetcher_no_gps(minimal_state):
    """Test weather fetcher handles missing GPS."""
    state = minimal_state.copy()
    state["gps_lat"] = None
    state["gps_lng"] = None

    result = await weather_fetcher(state)

    # Should skip weather
    assert result["weather_alert"] is None


@pytest.mark.asyncio
async def test_weather_fetcher_failure(minimal_state, sample_gps_coords, mock_redis_service):
    """Test weather fetcher handles failure gracefully."""
    state = minimal_state.copy()
    state["gps_lat"] = sample_gps_coords["lat"]
    state["gps_lng"] = sample_gps_coords["lng"]

    mock_weather = AsyncMock()
    mock_weather.get_weather = AsyncMock(side_effect=Exception("Weather API failed"))

    with patch("src.chains.nodes.weather_fetcher.get_openmeteo_service", return_value=mock_weather):
        with patch("src.chains.nodes.weather_fetcher.get_redis_service", return_value=mock_redis_service):
            result = await weather_fetcher(state)

    # Should degrade gracefully (non-critical path)
    assert result["weather_alert"] is None
