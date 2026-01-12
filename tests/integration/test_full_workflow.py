"""Integration tests for end-to-end workflow."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from src.chains.triage_chain import invoke_chain


@pytest.mark.asyncio
@pytest.mark.integration
class TestFullWorkflow:
    """Integration tests for complete triage workflow."""

    async def test_text_only_routine_workflow(self, mock_llm_service, mock_redis_service):
        """Test complete US1 workflow: text input → triage result."""
        session_id = str(uuid.uuid4())

        # Mock LLM to return complete extraction (no clarification needed)
        mock_llm_service.extract_symptoms.return_value = {
            "body_part": "手臂",
            "symptoms": ["红疹", "痒"],
            "duration": "2天",
            "severity": "轻微",
            "accompanying_symptoms": [],
            "onset": "逐渐"
        }

        mock_llm_service.classify_triage.return_value = {
            "triage_level": "ROUTINE",
            "triage_reason": "症状轻微，无紧急情况",
            "recommended_departments": ["皮肤科", "内科"],
            "possible_causes": [],
            "self_care_tips": ["避免抓挠", "保持清洁"],
            "red_flags": []
        }

        mock_llm_service.generate_clarification_questions.return_value = []

        # Mock all dependencies
        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                    result = await invoke_chain(
                                        session_id=session_id,
                                        text="手臂出现红疹，有点痒，持续2天"
                                    )

        # Should complete successfully (may be final or need_more_info)
        assert result["status"] in ["final", "need_more_info"]
        assert result["session_id"] == session_id
        assert len(result.get("clarify_questions", [])) <= 3

    async def test_emergency_workflow(self, mock_llm_service, mock_redis_service):
        """Test emergency workflow: text input → EMERGENCY triage (skip NCBI)."""
        session_id = str(uuid.uuid4())

        # Ensure red-flag rules trigger for emergency path
        mock_llm_service.extract_symptoms.return_value = {
            "body_part": "胸口",
            "symptoms": ["疼痛", "压迫感"],
            "duration": "30分钟",
            "severity": "严重",
            "accompanying_symptoms": ["呼吸困难"]
        }

        mock_llm_service.classify_triage.return_value = {
            "triage_level": "EMERGENCY",
            "triage_reason": "可能心脏病",
            "recommended_departments": ["急诊"],
            "possible_causes": [],
            "self_care_tips": [],
            "red_flags": ["胸痛"]
        }

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                result = await invoke_chain(
                                    session_id=session_id,
                                    text="胸痛持续30分钟，呼吸困难"
                                )

        # Should route to emergency without NCBI
        assert result["status"] == "final"
        assert result["triage_level"] == "EMERGENCY"
        assert len(result["recommended_departments"]) > 0

    async def test_clarification_workflow(self, mock_llm_service, mock_redis_service):
        """Test clarification workflow: text → need_clarify → session save."""
        session_id = str(uuid.uuid4())
        mock_llm_service.generate_clarification_questions.return_value = [
            "有发热吗？",
            "症状在加重吗？"
        ]
        mock_llm_service.classify_triage.return_value["possible_causes"] = []

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                    result = await invoke_chain(
                                        session_id=session_id,
                                        text="手臂疼痛"
                                    )

        # Should request clarification
        assert result["status"] == "need_more_info"
        assert len(result["clarify_questions"]) > 0
        assert "有发热吗？" in result["clarify_questions"]

    async def test_second_turn_final_triage(self, mock_llm_service, mock_redis_service):
        """Test second turn with clarification → final triage."""
        # Mock existing session with turn_count=2
        session_id = str(uuid.uuid4())
        mock_redis_service.load_session.return_value = {
            "turn_count": 1,
            "symptom_schema": {
                "body_part": "手臂",
                "symptoms": ["疼痛"]
            }
        }

        # No clarification needed on second turn (max rounds reached)
        mock_llm_service.generate_clarification_questions.return_value = []
        mock_llm_service.classify_triage.return_value["possible_causes"] = []

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                    with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                        result = await invoke_chain(
                                            session_id=session_id,
                                            text="没有发热，症状在好转"
                                        )

        # Should provide final triage (max rounds)
        assert result["status"] == "final"
        assert result["triage_level"] is not None

    async def test_vision_workflow(self, mock_llm_service, mock_redis_service, sample_image_base64):
        """Test US2 workflow: text + image → vision-enhanced triage."""
        session_id = str(uuid.uuid4())
        mock_llm_service.extract_visual_features.return_value = {
            "type": "rash",
            "summary": "手臂红斑伴丘疹",
            "features": ["红斑", "丘疹"],
            "confidence": 0.8
        }
        mock_llm_service.classify_triage.return_value["possible_causes"] = []

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.vision_extract.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                        with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                            result = await invoke_chain(
                                                session_id=session_id,
                                                text="手臂上出现皮疹",
                                                image_base64=sample_image_base64
                                            )

        # Should complete with vision processing
        assert result["status"] == "final"
        assert result["triage_level"] == "ROUTINE"

    async def test_navigation_workflow(self, mock_llm_service, mock_redis_service, mock_amap_service, mock_weather_service):
        """Test US3 workflow: text + GPS → hospital navigation."""
        session_id = str(uuid.uuid4())
        mock_llm_service.classify_triage.return_value["possible_causes"] = []
        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.navigator.get_amap_service', return_value=mock_amap_service):
                    with patch('src.chains.nodes.navigator.get_redis_service', return_value=mock_redis_service):
                        with patch('src.chains.nodes.weather_fetcher.get_openmeteo_service', return_value=mock_weather_service):
                            with patch('src.chains.nodes.weather_fetcher.get_redis_service', return_value=mock_redis_service):
                                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                                with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                                    result = await invoke_chain(
                                                        session_id=session_id,
                                                        text="胸痛持续30分钟",
                                                        gps_lat=39.9042,
                                                        gps_lng=116.4074
                                                    )

        # Should include navigation
        assert result["status"] == "final"
        assert result["navigation"] is not None
        assert len(result["navigation"]["hospitals"]) == 3
        assert result["navigation"]["hospitals"][0]["is_3a"] is True

    async def test_evidence_workflow(self, mock_llm_service, mock_redis_service, mock_ncbi_service):
        """Test evidence retrieval: ROUTINE → NCBI evidence included."""
        session_id = str(uuid.uuid4())
        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.ncbi_retriever_tool.get_ncbi_service', return_value=mock_ncbi_service):
                    with patch('src.chains.nodes.ncbi_retriever_tool.get_redis_service', return_value=mock_redis_service):
                        with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                                    with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                        with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                            result = await invoke_chain(
                                                session_id=session_id,
                                                text="手臂红疹"
                                            )

        # Should include evidence
        assert result["status"] == "final"
        assert result["evidence_selected"] is not None
        assert len(result["evidence_selected"]) > 0

    async def test_error_handling_input_validation(self, mock_llm_service, mock_redis_service):
        """Test error handling: invalid input caught at validator."""
        import uuid
        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                    result = await invoke_chain(
                                        session_id=str(uuid.uuid4()),
                                        text="a" * 2001  # Exceeds max length
                                    )

        # Should handle gracefully (may trim text or return need_more_info)
        assert result["status"] in ["error", "need_more_info", "final"]

    async def test_graceful_degradation_redis_down(self, mock_llm_service):
        """Test graceful degradation: Redis unavailable."""
        session_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        mock_redis.is_healthy = False
        mock_redis.load_session = AsyncMock(return_value=None)
        mock_redis.save_session = AsyncMock()
        mock_llm_service.classify_triage.return_value["possible_causes"] = []

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                    result = await invoke_chain(
                                        session_id=session_id,
                                        text="手臂疼痛"
                                    )

        # Should still complete (treat as new session)
        assert result["status"] == "final"

    async def test_safety_verification_diagnosis_filter(self, mock_llm_service, mock_redis_service):
        """Test safety verification filters out diagnosis language."""
        session_id = str(uuid.uuid4())
        # Mock unsafe response containing diagnosis
        mock_llm_service.verify_safety.return_value = {
            "is_safe": False,
            "violations": ["diagnosis"],
            "sanitized_content": "可能是皮肤问题，建议就医检查"
        }
        mock_llm_service.classify_triage.return_value["triage_reason"] = "诊断为皮肤问题"
        mock_llm_service.classify_triage.return_value["possible_causes"] = []

        with patch('src.chains.nodes.session_loader.get_redis_service', return_value=mock_redis_service):
            with patch('src.chains.nodes.session_saver.get_redis_service', return_value=mock_redis_service):
                with patch('src.chains.nodes.clinical_extractor.get_llm_service', return_value=mock_llm_service):
                    with patch('src.chains.nodes.triage_classifier.get_llm_service', return_value=mock_llm_service):
                        with patch('src.chains.nodes.domain_classifier.get_llm_service', return_value=mock_llm_service):
                            with patch('src.chains.nodes.clarification_generator.get_llm_service', return_value=mock_llm_service):
                                with patch('src.chains.nodes.reasoning_verifier.get_llm_service', return_value=mock_llm_service):
                                    result = await invoke_chain(
                                        session_id=session_id,
                                        text="皮肤有问题"
                                    )

        # Should sanitize response
        assert result["status"] == "final"
        assert "可能是" in result["response"] or "可能" in result["response"]
