"""LLM service for Qwen model integration via OpenAI-compatible API."""
import json
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config.settings import get_settings
from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)

settings = get_settings()


class LLMService:
    """LLM service for Qwen model integration with retry and graceful degradation."""

    def __init__(self) -> None:
        """Initialize LLM service with multiple model instances."""
        self._healthy = True
        self._extractor: BaseChatModel | None = None
        self._vision: BaseChatModel | None = None
        self._verifier: BaseChatModel | None = None
        self._triage: BaseChatModel | None = None

        self._setup_models()

    def _setup_models(self) -> None:
        """Setup different model instances for different use cases."""
        common_config: dict[str, Any] = {
            "base_url": settings.qwen_base_url,
            "api_key": settings.qwen_api_key,
            "timeout": settings.llm_timeout,
        }
        # Reasoning models (e.g. Zhipu GLM-5-turbo) spend many seconds on a hidden
        # "thinking" phase, blowing past per-node timeouts. Must use extra_body (NOT
        # model_kwargs): langchain_openai spreads model_kwargs as top-level kwargs into
        # openai's create(), which rejects unknown 'thinking' with TypeError; extra_body
        # merges it into the request JSON the provider actually receives.
        if settings.llm_disable_thinking:
            common_config["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            # Extraction model (low temp for consistency)
            self._extractor = ChatOpenAI(
                **common_config,
                model=settings.llm_extractor_model,
                temperature=0.1
            )

            # Vision model (multimodal)
            self._vision = ChatOpenAI(
                **common_config,
                model=settings.llm_vision_model,
                temperature=0.2
            )

            # Verification model (zero temp for strict safety)
            self._verifier = ChatOpenAI(
                **common_config,
                model=settings.llm_verifier_model,
                temperature=0.0
            )

            # Triage model (balanced creativity)
            self._triage = ChatOpenAI(
                **common_config,
                model=settings.llm_triage_model,
                temperature=0.3
            )

            logger.info("LLM models initialized successfully")

        except Exception as e:
            self._healthy = False
            set_external_service_health("qwen", False)
            logger.error(f"Failed to initialize LLM models: {e}")

    def _require_model(self, model: BaseChatModel | None, model_name: str) -> BaseChatModel:
        """Guarantee model is initialized before invocation."""
        if model is None:
            raise RuntimeError(f"LLM model not initialized: {model_name}")
        return model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def _invoke_with_retry(
        self,
        model: BaseChatModel,
        messages: list[Any],
        max_retries: int = 2
    ) -> str:
        """Invoke LLM with retry logic per FR-049.

        Args:
            model: LangChain model instance
            messages: List of messages
            max_retries: Maximum retry attempts for JSON parsing

        Returns:
            Model response text

        Raises:
            Exception: If all retries exhausted
        """
        try:
            response = await model.ainvoke(messages)
            content = response.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                    for item in content
                )
            return str(content)

        except Exception as e:
            set_external_service_health("qwen", False)
            logger.error(f"LLM invocation failed: {e}")
            raise

    async def extract_symptoms(
        self,
        text: str,
        visual_findings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract structured symptom schema from text.

        Uses low temperature (0.1) for consistent extraction.

        Args:
            text: User's symptom description
            visual_findings: Optional visual findings from image

        Returns:
            Structured symptom schema dict
        """
        system_prompt = """你是一个医疗信息提取专家。请从用户描述中提取结构化的症状信息。

规则：
1. 身体部位：提取具体部位（如"手臂"、"胸口"）
2. 症状列表：提取所有症状（1-10个）
3. 持续时间：如用户提供（如"2天"、"1周"）
4. 严重程度：轻微/中度/严重（如用户提供）
5. 伴随症状：其他相关症状
6. 起病方式：突然/逐渐（如可推断）

重要：
- 只提取明确提到的信息，不要猜测
- 使用口语化词汇，不要使用医学术语
- 必须返回JSON格式，字段名使用英文

输出格式示例：
{
  "body_part": "手臂",
  "symptoms": ["红疹", "痒"],
  "duration": "2天",
  "severity": "轻微",
  "accompanying_symptoms": [],
  "onset": "逐渐"
}"""

        user_prompt = f"用户描述：{text}"

        if visual_findings:
            user_prompt += f"\n图片观察：{visual_findings.get('summary', '')}"

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._extractor, "extractor"),
                messages,
            )

            # Try to parse JSON response
            try:
                # Extract JSON from response (in case of extra text)
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                symptom_schema = cast(dict[str, Any], json.loads(json_str))
                return symptom_schema

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                # Return minimal schema on parse failure
                return {
                    "body_part": "未知",
                    "symptoms": [text[:50]],
                    "duration": None,
                    "severity": None,
                    "accompanying_symptoms": [],
                    "onset": None
                }

        except Exception as e:
            logger.error(f"Symptom extraction failed: {e}")
            raise

    async def classify_triage(
        self,
        symptom_schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Classify triage level using LLM.

        Uses medium temperature (0.3) for nuanced classification.
        Conservative bias: when uncertain, escalate to higher urgency.

        Args:
            symptom_schema: Structured symptom information

        Returns:
            Triage decision dict with level, reason, departments
        """
        system_prompt = """你是一个医疗分诊专家。请根据症状信息评估紧急程度，给出分诊建议。

分诊级别定义：
- EMERGENCY：生命危险，需立即急诊/呼叫急救
- URGENT：需尽快就医（当天或数小时内）
- ROUTINE：可常规预约就诊（数天内）
- SELF_CARE：可居家观察（但仍建议就医确认）

规则：
1. 保守原则：不确定时选择更高级别
2. 必须推荐1-3个科室
3. 可能原因最多3个，必须用"疑似"、"可能"或"相关"
4. 自我护理建议不可含药物剂量/用法
5. 红旗警示：告知何时需立即急诊

输出格式（JSON）：
{
  "triage_level": "ROUTINE",
  "triage_reason": "症状轻微，无明显危险信号",
  "recommended_departments": ["皮肤科"],
  "possible_causes": [
    "过敏相关皮疹（疑似）",
    "接触性皮炎（疑似）"
  ],
  "self_care_tips": [
    "避免抓挠患处",
    "记录皮疹变化"
  ],
  "red_flags": [
    "如果出现呼吸困难/脸唇肿胀，请立刻急诊"
  ]
}"""

        user_prompt = f"""症状信息：
{json.dumps(symptom_schema, ensure_ascii=False)}

请评估分诊级别并给出建议。"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._triage, "triage"),
                messages,
            )

            # Parse JSON response
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                triage_decision = cast(dict[str, Any], json.loads(json_str))
                return triage_decision

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse triage JSON response: {e}")
                # Return conservative default
                return {
                    "triage_level": "URGENT",
                    "triage_reason": "评估失败，建议就医确认",
                    "recommended_departments": ["急诊"],
                    "possible_causes": [],
                    "self_care_tips": [],
                    "red_flags": ["如症状加重请立即急诊"]
                }

        except Exception as e:
            logger.error(f"Triage classification failed: {e}")
            raise

    async def verify_safety(
        self,
        draft_response: str
    ) -> dict[str, Any]:
        """Verify response for safety violations using LLM reasoning verifier.

        Uses zero temperature (0.0) for strict safety checking.

        Args:
            draft_response: Draft response to verify

        Returns:
            Verification result with is_safe flag and sanitized content
        """
        system_prompt = """你是一个医疗内容安全审核专家。请检查响应内容是否符合以下规则：

禁止内容：
1. 诊断性语言：确诊、诊断、你得的是、是XX病、患有、得了
2. 处方性语言：mg剂量、每次X片、服药、用药、注射
3. 延误就医：不用就医、不用看医生、肯定没事、无需治疗、可以不用管

审核要求：
- 严格禁止任何形式的绝对诊断
- 禁止任何药物剂量和用法建议
- 禁止任何"不用看医生"的建议
- 所有医疗建议必须保持谨慎和保守

输出格式（JSON）：
{
  "is_safe": true,
  "violations": [],
  "sanitized_content": "原内容或修改后内容"
}

如果发现违规，请在sanitized_content中提供符合规范的修改建议。"""

        user_prompt = f"""请审核以下响应内容：

{draft_response}

给出审核结果。"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._verifier, "verifier"),
                messages,
            )

            # Parse JSON response
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                verification = cast(dict[str, Any], json.loads(json_str))
                return verification

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse verification JSON response: {e}")
                # On parse error, flag as unsafe but return original
                return {
                    "is_safe": False,
                    "violations": ["parse_error"],
                    "sanitized_content": draft_response
                }

        except Exception as e:
            logger.error(f"Safety verification failed: {e}")
            # On error, be conservative and flag as unsafe
            return {
                "is_safe": False,
                "violations": ["verification_error"],
                "sanitized_content": draft_response
            }

    async def extract_visual_features(
        self,
        image_base64: str,
        text: str | None = None
    ) -> dict[str, Any]:
        """Extract visual features from image using Qwen-VL.

        Args:
            image_base64: Base64-encoded image
            text: Optional text context

        Returns:
            Visual findings dict with type, summary, features, confidence
        """
        system_prompt = """你是一个医疗图像分析专家。请从图片中提取视觉特征，但不做诊断。

规则：
1. 类型：rash（皮疹）/wound（伤口）/unknown
2. 摘要：客观描述可见特征（50字内）
3. 特征：列举可见特征（红斑、丘疹、肿胀、出血等）
4. 置信度：0.0-1.0

重要：
- 只描述可见特征，不做诊断
- 不使用医学术语（如"荨麻疹"、"湿疹"等）
- 如果图片不清晰，置信度应低于0.5

输出格式（JSON）：
{
  "type": "rash",
  "summary": "手臂红斑伴丘疹",
  "features": ["红斑", "丘疹", "肿胀"],
  "confidence": 0.85
}"""

        # Prepare multimodal message
        user_content: list[dict[str, Any]] = []
        if text:
            user_content.append({"type": "text", "text": f"用户描述：{text}"})

        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}"
            }
        })
        user_content.append({
            "type": "text",
            "text": "请分析这张图片的视觉特征。"
        })

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=cast(list[str | dict[Any, Any]], user_content))
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._vision, "vision"),
                messages,
            )

            # Parse JSON response
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                visual_findings = cast(dict[str, Any], json.loads(json_str))
                return visual_findings

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse visual findings JSON: {e}")
                # Return minimal schema on parse failure
                return {
                    "type": "unknown",
                    "summary": "图片分析失败",
                    "features": [],
                    "confidence": 0.0
                }

        except Exception as e:
            logger.error(f"Visual feature extraction failed: {e}")
            raise

    async def classify_domain(
        self,
        symptom_schema: dict[str, Any]
    ) -> str:
        """Classify medical specialty domain.

        Uses low temperature (0.1) for consistent classification.

        Args:
            symptom_schema: Structured symptom information

        Returns:
            Domain string (dermatology/trauma/respiratory/gastro/neuro/urology/other)
        """
        system_prompt = """你是一个医疗分科专家。请根据症状信息判断最可能的科室。

科室类别：
- dermatology：皮肤科（皮疹、红肿、瘙痒等）
- trauma：外伤/骨科（骨折、扭伤、外伤出血等）
- respiratory：呼吸科（咳嗽、呼吸困难、胸闷等）
- gastro：消化科（腹痛、恶心、呕吐等）
- neuro：神经科（头痛、头晕、意识障碍等）
- urology：泌尿科（尿频、尿急、尿痛等）
- other：其他或不确定

输出要求：
- 只输出科室英文名称，不要输出其他内容
- 如果症状涉及多个科室，选择最主要的"""

        user_prompt = f"""症状信息：
{json.dumps(symptom_schema, ensure_ascii=False)}

请判断最合适的科室。"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._extractor, "extractor"),
                messages,
            )

            # Extract domain (should be single word)
            domain = response.strip().lower()
            valid_domains = [
                "dermatology", "trauma", "respiratory", "gastro",
                "neuro", "urology", "other"
            ]

            if domain in valid_domains:
                return domain
            else:
                logger.warning(f"Invalid domain '{domain}', defaulting to 'other'")
                return "other"

        except Exception as e:
            logger.error(f"Domain classification failed: {e}")
            return "other"

    async def generate_clarification_questions(
        self,
        symptom_schema: dict[str, Any],
        turn_count: int
    ) -> list[str]:
        """Generate clarification questions.

        Args:
            symptom_schema: Current symptom information
            turn_count: Current turn number (1 or 2)

        Returns:
            List of 1-3 clarification questions
        """
        system_prompt = f"""你是一个医疗问诊专家。请根据现有症状信息，生成{settings.max_clarification_questions}个澄清问题以获得更准确的评估。

规则：
1. 最多{settings.max_clarification_questions}个问题
2. 问题要具体、可回答
3. 不要问已经明确的信息
4. 第{turn_count}轮澄清，优先询问关键信息（持续时间、严重程度、伴随症状）
5. 避免过多问题，不要让用户感到负担

输出格式（JSON）：
{{
  "questions": [
    "症状持续多久了？",
    "有没有发热或头痛？",
    "疼痛程度如何？"
  ]
}}"""

        user_prompt = f"""已知症状信息：
{json.dumps(symptom_schema, ensure_ascii=False)}

请生成澄清问题。"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self._invoke_with_retry(
                self._require_model(self._extractor, "extractor"),
                messages,
            )

            # Parse JSON response
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
                result = cast(dict[str, Any], json.loads(json_str))
                raw_questions = result.get("questions", [])
                if not isinstance(raw_questions, list):
                    return ["请提供更多症状细节"]
                questions = [str(item) for item in raw_questions if isinstance(item, str)]
                return questions[:settings.max_clarification_questions]

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse questions JSON: {e}")
                return ["请提供更多症状细节"]

        except Exception as e:
            logger.error(f"Clarification question generation failed: {e}")
            return ["请描述更多症状信息"]

    @property
    def is_healthy(self) -> bool:
        """Check if LLM service is healthy."""
        return self._healthy


# Global LLM service instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create global LLM service instance.

    Returns:
        LLMService instance
    """
    global _llm_service

    if _llm_service is None:
        _llm_service = LLMService()

    return _llm_service
