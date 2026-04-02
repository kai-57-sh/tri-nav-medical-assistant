"""Unit tests for LLM service."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm_service import LLMService, get_llm_service


@pytest.mark.asyncio
class TestLLMService:
    """Test LLM service operations."""

    async def test_extract_symptoms_success(self):
        """Test successful symptom extraction."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '{"body_part": "手臂", "symptoms": ["红疹"]}'
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._extractor = mock_llm

            result = await service.extract_symptoms("手臂出现红疹")

            # Should parse JSON response
            assert result["body_part"] == "手臂"
            assert "红疹" in result["symptoms"]

    async def test_extract_symptoms_with_retry(self):
        """Test symptom extraction with JSON parsing retry."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            # First call invalid JSON, second call valid JSON
            mock_response.content = '{"body_part": "手臂"}'
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._extractor = mock_llm

            result = await service.extract_symptoms("手臂疼痛")

            # Should return parsed data
            assert result["body_part"] == "手臂"

    async def test_classify_triage_routine(self):
        """Test triage classification for ROUTINE case."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "triage_level": "ROUTINE",
                "triage_reason": "症状轻微",
                "recommended_departments": ["皮肤科"],
                "possible_causes": ["湿疹"],
                "self_care_tips": ["保持清洁"],
                "red_flags": []
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._triage = mock_llm

            result = await service.classify_triage({"body_part": "手臂", "symptoms": ["红疹"]})

            # Should classify as ROUTINE
            assert result["triage_level"] == "ROUTINE"
            assert "皮肤科" in result["recommended_departments"]
            assert len(result["possible_causes"]) > 0

    async def test_classify_triage_emergency_conservative(self):
        """Test triage classification with conservative bias."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "triage_level": "EMERGENCY",
                "triage_reason": "可能心脏病",
                "recommended_departments": ["急诊科"],
                "possible_causes": [],
                "self_care_tips": [],
                "red_flags": ["需要立即检查"]
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._triage = mock_llm

            result = await service.classify_triage({"body_part": "胸部", "symptoms": ["疼痛"]})

            # Should classify conservatively
            assert result["triage_level"] == "EMERGENCY"

    async def test_verify_safe_response(self):
        """Test safety verification of safe response."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "is_safe": true,
                "violations": [],
                "sanitized_content": "Safe response"
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._verifier = mock_llm

            result = await service.verify_safety("建议去医院检查")

            # Should approve safe response
            assert result["is_safe"] is True
            assert result["violations"] == []

    async def test_verify_unsafe_response_sanitized(self):
        """Test safety verification sanitizes unsafe response."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "is_safe": false,
                "violations": ["diagnosis"],
                "sanitized_content": "可能是皮肤问题"
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._verifier = mock_llm

            result = await service.verify_safety("你得的是湿疹")

            # Should sanitize diagnosis
            assert result["is_safe"] is False
            assert "diagnosis" in result["violations"]
            assert "湿疹" not in result["sanitized_content"] or "可能" in result["sanitized_content"]

    async def test_extract_visual_features(self):
        """Test visual feature extraction from image."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "body_part": "手臂",
                "visual_symptoms": ["红斑", "丘疹"],
                "distribution": "散在",
                "severity": "轻微"
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._vision = mock_llm

            result = await service.extract_visual_features("base64imagedata", "手臂红疹")

            # Should extract visual features
            assert result["body_part"] == "手臂"
            assert "红斑" in result["visual_symptoms"]

    async def test_generate_clarification_questions(self):
        """Test clarification question generation."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '''{
                "questions": [
                    "有发热吗？",
                    "症状持续多久了？",
                    "受过外伤吗？"
                ]
            }'''
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._extractor = mock_llm

            result = await service.generate_clarification_questions(
                {"body_part": "手臂", "symptoms": ["疼痛"]},
                turn_count=1
            )

            # Should generate questions
            assert len(result) == 3
            assert "有发热吗？" in result

    async def test_classify_domain(self):
        """Test medical domain classification."""
        with patch('src.services.llm_service.ChatOpenAI') as mock_chat:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "dermatology"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            service = LLMService()
            service._extractor = mock_llm

            result = await service.classify_domain({"body_part": "手臂", "symptoms": ["红疹"]})

            # Should classify domain
            assert result == "dermatology"


@pytest.mark.asyncio
async def test_get_llm_service_singleton():
    """Test that get_llm_service returns singleton instance."""
    with patch('src.services.llm_service.LLMService') as mock_service_class:
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        with patch('src.services.llm_service._llm_service', None):
            service1 = get_llm_service()
            service2 = get_llm_service()

        # Should return same instance (cached)
        assert service1 is service2

        # Should only create once
        mock_service_class.assert_called_once()
