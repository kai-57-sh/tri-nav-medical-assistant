"""Response Composer helper function."""
from typing import Any

from src.utils.constants import HOTLINE_TIP


def compose_response(state: dict[str, Any]) -> str:
    """Compose response from workflow state.

    Formats colloquial Chinese response with all required sections.
    Includes mandatory hotline tip per FR-044, FR-046 (disclaimer returned separately).

    Args:
        state: Current workflow state

    Returns:
        Formatted response string
    """
    # Check if clarification needed
    if state.get("need_clarify"):
        questions = state.get("clarify_questions", [])
        response_parts = ["为了更准确地评估您的情况，我需要了解以下信息：\n"]

        for i, question in enumerate(questions, 1):
            response_parts.append(f"{i}. {question}")

        response_parts.append("\n请您补充这些信息，我会立即为您评估。")
        return "".join(response_parts)

    # Compose final triage response
    response_parts = []

    # Triage level and reason
    triage_level = state.get("triage_level", "ROUTINE")
    triage_reason = state.get("triage_reason", "")

    if triage_level == "EMERGENCY":
        response_parts.append("⚠️ 紧急提醒")
    elif triage_level == "URGENT":
        response_parts.append("⏰ 尽快就医")
    elif triage_level == "ROUTINE":
        response_parts.append("🏥 常规就诊")
    else:  # SELF_CARE
        response_parts.append("💡 居家观察")

    if triage_reason:
        response_parts.append(f"\n{triage_reason}")

    # Recommended departments
    departments = state.get("recommended_departments", [])
    if departments:
        dept_list = "、".join(departments)
        response_parts.append(f"\n\n**建议科室**：{dept_list}")

    # Possible causes
    causes = state.get("possible_causes", [])
    if causes and triage_level != "EMERGENCY":
        response_parts.append("\n\n**可能原因**：")
        for cause in causes:
            response_parts.append(f"\n- {cause}")

    # Self-care tips
    tips = state.get("self_care_tips", [])
    if tips:
        response_parts.append("\n\n**护理建议**：")
        for tip in tips:
            response_parts.append(f"\n- {tip}")

    # Red flags
    red_flags = state.get("red_flags", [])
    if red_flags:
        response_parts.append("\n\n**⚠️ 警示**：")
        for flag in red_flags:
            response_parts.append(f"\n- {flag}")

    # Add navigation if available
    navigation = state.get("navigation_result")
    if navigation:
        hospitals = navigation.get("hospitals", [])
        if hospitals:
            response_parts.append("\n\n**🏥 推荐医院**：")
            for hospital in hospitals:
                rank = hospital.get("rank")
                name = hospital.get("name")
                reason = hospital.get("reason")
                response_parts.append(f"\n{rank}. {name}（{reason}）")

            # Route plan
            route_plan = navigation.get("route_plan")
            if route_plan:
                response_parts.append(f"\n**路线规划**：{route_plan.get('summary')}")

        # Weather alert
        weather = state.get("weather_alert")
        if weather:
            weather_parts = []
            condition = weather.get("condition")
            temp_c = weather.get("temp_c")
            humidity = weather.get("humidity")
            wind_speed_kmh = weather.get("wind_speed_kmh")
            tip = weather.get("tip")

            if condition:
                weather_parts.append(condition)
            if temp_c is not None:
                weather_parts.append(f"{temp_c}°C")
            if humidity is not None:
                weather_parts.append(f"湿度{humidity}%")
            if wind_speed_kmh is not None:
                weather_parts.append(f"风速{wind_speed_kmh}km/h")

            if weather_parts:
                response_parts.append(f"\n\n**🌤️ 天气提示**：{'，'.join(weather_parts)}")
            if tip:
                response_parts.append(f"\n- {tip}")

    # Evidence (if available)
    evidence = state.get("evidence_selected")
    if evidence and triage_level != "EMERGENCY":
        response_parts.append("\n\n**📚 参考文献**（仅供科普）：")
        for item in evidence[:5]:  # Max 5 for brevity
            response_parts.append(f"\n- {item.get('title')} ({item.get('year')})")

    # Mandatory hotline tip
    response_parts.append(f"\n\n**温馨提示**：{HOTLINE_TIP}")

    return "".join(response_parts)
