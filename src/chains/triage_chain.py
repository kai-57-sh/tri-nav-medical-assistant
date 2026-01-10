"""Main TriNav chain export for LangServe."""
from langchain_core.runnables import RunnableConfig
from .graph.triage_graph import build_graph, TriageState

# Build and compile the graph
graph = build_graph()
chain = graph


async def invoke_chain(
    session_id: str,
    text: str,
    image_base64: str = None,
    gps_lat: float = None,
    gps_lng: float = None,
    config: RunnableConfig = None,
) -> dict:
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
        "status": "error",
        "error_message": None,
    }

    # Invoke the graph
    result = await graph.ainvoke(initial_state, config=config)

    # Extract final output
    return {
        "status": result.get("status"),
        "session_id": result.get("session_id"),
        "response": result.get("final_response"),
        "triage_level": result.get("triage_level"),
        "recommended_departments": result.get("recommended_departments", []),
        "possible_causes": result.get("possible_causes", []),
        "self_care_tips": result.get("self_care_tips", []),
        "red_flags": result.get("red_flags", []),
        "clarify_questions": result.get("clarify_questions", []),
        "navigation": result.get("navigation_result"),
        "evidence": result.get("evidence_selected"),
        "error_message": result.get("error_message"),
    }


__all__ = ["chain", "invoke_chain"]
