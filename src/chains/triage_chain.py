"""Main TriNav chain export for LangServe."""
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from .graph.triage_graph import TriageState, build_graph

# Build and compile the graph
chain: Any = build_graph()
graph = chain


async def invoke_chain(
    session_id: str,
    text: str,
    image_base64: str | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Invoke the triage chain with user input.

    Args:
        session_id: Session identifier (UUID format)
        text: User's symptom description (max 2000 chars)
        image_base64: Optional image data (base64 encoded, max 5MB)
        gps_lat: Optional GPS latitude (-90 to 90)
        gps_lng: Optional GPS longitude (-180 to 180)
        config: Optional RunnableConfig for LangChain

    Returns:
        dict: Final response with status and data
    """
    # Build initial state
    initial_state: TriageState = {
        "session_id": session_id,
        "text": text,
        "image_base64": image_base64,
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
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
        "evidence_selected": None,
        "navigation_result": None,
        "weather_alert": None,
        "case_domain": None,
        "final_response": None,
        "response": None,
        "disclaimer": None,
        "status": "error",
        "error_message": None,
    }

    # Invoke the graph
    result = cast(dict[str, Any], await graph.ainvoke(initial_state, config=config))

    # Extract final output
    return {
        "status": result.get("status"),
        "session_id": result.get("session_id"),
        "response": result.get("final_response"),
        "triage_level": result.get("triage_level"),
        "triage_reason": result.get("triage_reason"),
        "triage_source": result.get("triage_source"),
        "recommended_departments": result.get("recommended_departments", []),
        "possible_causes": result.get("possible_causes", []),
        "self_care_tips": result.get("self_care_tips", []),
        "red_flags": result.get("red_flags", []),
        "clarify_questions": result.get("clarify_questions", []),
        "navigation": result.get("navigation_result"),
        "evidence_selected": result.get("evidence_selected"),
        "weather_alert": result.get("weather_alert"),
        "visual_findings": result.get("visual_findings"),
        "disclaimer": result.get("disclaimer"),
        "error_message": result.get("error_message"),
    }


__all__ = ["chain", "invoke_chain"]
