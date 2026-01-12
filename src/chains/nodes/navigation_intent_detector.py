"""Navigation Intent Detector Node.

Detects if user's primary intent is hospital navigation vs medical triage.
"""
from typing import Dict, Any
from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 医院请求关键词
HOSPITAL_KEYWORDS = ["医院", "就医", "导航", "推荐医院", "挂号", "急诊"]

# 负向关键词（明确表示不想去医院）
NEGATIVE_KEYWORDS = ["不去医院", "不想去医院", "无需就医"]

# 排除典型症状关键词
SYMPTOM_KEYWORDS = ["疼", "痛", "发烧", "咳嗽", "头晕", "呕吐", "腹泻", "出血", "难受", "不适"]

# 短句阈值（纯医院请求，无症状描述）
SHORT_REQUEST_THRESHOLD = 15  # 字符数


@safe_node("NavigationIntentDetector")
async def navigation_intent_detector(state: Dict[str, Any]) -> Dict[str, Any]:
    """检测用户是否仅为医院导航请求。

    判断标准：
    1. 文本包含医院关键词
    2. 文本较短（< SHORT_REQUEST_THRESHOLD 字符）
    3. 不包含典型症状描述（通过关键词排除）

    Args:
        state: 当前工作流状态

    Returns:
        更新 navigation_only 标志
    """
    text = state.get("text", "")
    navigation_only = False

    # 检测医院关键词
    has_hospital_keyword = any(kw in text for kw in HOSPITAL_KEYWORDS)

    # 检测负向关键词
    has_negative = any(kw in text for kw in NEGATIVE_KEYWORDS)

    # 检测症状关键词
    has_symptom = any(kw in text for kw in SYMPTOM_KEYWORDS)

    # 判断为纯导航请求：
    # 1. 有医院关键词
    # 2. 无负向关键词
    # 3. 无症状关键词
    # 4. 文本较短（短句通常为请求，而非描述症状）
    if has_hospital_keyword and not has_negative and not has_symptom and len(text) < SHORT_REQUEST_THRESHOLD:
        navigation_only = True
        logger.info(
            f"Detected navigation-only request: '{text}' (length={len(text)})"
        )
    else:
        navigation_only = False
        logger.debug(
            f"Not a navigation-only request: hospital={has_hospital_keyword}, "
            f"negative={has_negative}, symptom={has_symptom}, length={len(text)}"
        )

    return {"navigation_only": navigation_only}
