"""LangGraph StateGraph for TriNav workflow.

This module builds the 18-node triage workflow using LangGraph 1.0.5+.
State is passed between nodes as a TypedDict, with conditional routing
based on triage decisions.
"""
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from ...utils.logging_config import get_logger
from ..nodes import (
    clarification_generator,
    clinical_extractor,
    domain_classifier,
    evidence_router,
    final_status_router,
    image_quality_gate,
    input_validator,
    navigation_intent_detector,
    navigator,
    ncbi_query_builder,
    ncbi_retriever_tool,
    reasoning_verifier,
    red_flag_detector,
    session_load,
    session_save,
    triage_classifier,
    triage_merger,
    vision_extract,
    weather_fetcher,
)

logger = get_logger(__name__)


class TriageState(TypedDict):
    """State for the triage workflow.

    All nodes receive this state and return updates to it.
    """
    # Input fields
    session_id: str
    text: str
    image_base64: str | None
    gps_lat: float | None
    gps_lng: float | None

    # Session state
    turn_count: int
    symptom_schema: dict[str, Any] | None
    clarify_questions: list[str]
    navigation_only: bool  # 纯导航请求标志（无需重新分诊）

    # Triage decision
    triage_level: Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"] | None
    triage_source: str | None  # "rule_engine", "llm", "merged"
    triage_reason: str | None
    recommended_departments: list[str]
    possible_causes: list[str]
    self_care_tips: list[str]
    red_flags: list[str]

    # Red flag detection (rule-based)
    rule_triage_level: str | None
    llm_triage_level: str | None
    llm_triage_reason: str | None
    llm_recommended_departments: list[str]
    llm_possible_causes: list[str]
    llm_self_care_tips: list[str]
    llm_red_flags: list[str]
    red_flags_hit: list[str]

    # Clarification
    need_clarify: bool

    # Vision processing
    image_as_valid: bool

    # Evidence retrieval
    should_retrieve_evidence: bool
    ncbi_query: str

    # External service results
    visual_findings: dict[str, Any] | None
    evidence_selected: list[dict[str, Any]] | None
    navigation_result: dict[str, Any] | None
    weather_alert: dict[str, Any] | None
    case_domain: str | None

    # Final output
    final_response: str | None
    response: str | None
    disclaimer: str | None
    status: Literal["final", "need_more_info", "error"]
    error_message: str | None


async def _should_skip_ncbi(state: TriageState) -> bool:
    """Skip NCBI retrieval for emergency cases."""
    should_retrieve = state.get("should_retrieve_evidence", False)
    return not should_retrieve


async def _should_skip_navigation(state: TriageState) -> bool:
    """Skip navigation for SELF_CARE cases."""
    triage_level = state.get("triage_level")
    return triage_level in ("SELF_CARE", None)


async def _has_error(state: TriageState) -> bool:
    """Check if workflow has errored."""
    return state.get("status") == "error"


async def _should_skip_clinical(state: TriageState) -> bool:
    """跳过临床提取，直接进入导航。

    条件：
    1. navigation_only=True（纯导航请求）
    2. 有历史分诊数据（triage_level 非空）

    Returns:
        True: 跳过临床提取，直接导航
        False: 正常走分诊流程
    """
    nav_only = state.get("navigation_only", False)
    has_triage = state.get("triage_level") is not None
    return nav_only and has_triage


def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for triage workflow.

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create state graph
    graph = StateGraph(TriageState)

    # === Add all nodes ===
    graph.add_node("input_validator", input_validator)
    graph.add_node("session_loader", session_load)
    graph.add_node("navigation_intent_detector", navigation_intent_detector)
    graph.add_node("image_quality_gate", image_quality_gate)
    graph.add_node("vision_extract", vision_extract)
    graph.add_node("clinical_extractor", clinical_extractor)
    graph.add_node("red_flag_detector", red_flag_detector)
    graph.add_node("triage_classifier", triage_classifier)
    graph.add_node("triage_merger", triage_merger)
    graph.add_node("clarification_generator", clarification_generator)
    graph.add_node("evidence_router", evidence_router)
    graph.add_node("ncbi_query_builder", ncbi_query_builder)
    graph.add_node("ncbi_retriever_tool", ncbi_retriever_tool)
    graph.add_node("domain_classifier", domain_classifier)
    graph.add_node("navigator", navigator)
    graph.add_node("weather_fetcher", weather_fetcher)
    graph.add_node("session_saver", session_save)
    graph.add_node("reasoning_verifier", reasoning_verifier)
    graph.add_node("final_status_router", final_status_router)

    # === Define edges (full workflow with US1, US2, US3) ===

    # Start → input validation
    graph.set_entry_point("input_validator")

    # Input validation → session loader
    graph.add_edge("input_validator", "session_loader")

    # Session loader → navigation intent detector
    graph.add_edge("session_loader", "navigation_intent_detector")

    # Navigation intent detector → conditional routing
    # 如果是纯导航请求且有历史分诊，跳过临床提取，直接导航
    # 否则正常走分诊流程
    graph.add_conditional_edges(
        "navigation_intent_detector",
        _should_skip_clinical,
        {
            True: "navigator",  # 跳过临床提取，直接导航
            False: "image_quality_gate"  # 正常分诊流程
        }
    )

    # Image quality gate → vision extract (conditional, US2)
    graph.add_edge("image_quality_gate", "vision_extract")

    # Vision extract → clinical extractor (merge text + vision)
    graph.add_edge("vision_extract", "clinical_extractor")

    # Clinical extractor → red flag detector
    graph.add_edge("clinical_extractor", "red_flag_detector")

    # Red flag detector → triage classifier
    graph.add_edge("red_flag_detector", "triage_classifier")

    # Triage classifier → triage merger
    graph.add_edge("triage_classifier", "triage_merger")

    # Triage merger → domain classifier (for better routing)
    graph.add_edge("triage_merger", "domain_classifier")

    # Domain classifier → clarification generator
    graph.add_edge("domain_classifier", "clarification_generator")

    # Clarification generator → evidence routing
    # Both clarification and final paths continue through evidence routing,
    # so a direct edge avoids redundant conditional branching.
    graph.add_edge("clarification_generator", "evidence_router")

    # Evidence router → conditional routing (US1 evidence)
    graph.add_conditional_edges(
        "evidence_router",
        _should_skip_ncbi,
        {
            True: "navigator",  # Skip evidence → go to navigation
            False: "ncbi_query_builder"  # Retrieve evidence → build query
        }
    )

    # NCBI query builder → NCBI retriever
    graph.add_edge("ncbi_query_builder", "ncbi_retriever_tool")

    # NCBI retriever → navigator (US3 navigation)
    graph.add_edge("ncbi_retriever_tool", "navigator")

    # Navigator → weather fetcher
    graph.add_edge("navigator", "weather_fetcher")

    # Weather fetcher → reasoning verifier
    graph.add_edge("weather_fetcher", "reasoning_verifier")

    # Reasoning verifier → session saver
    graph.add_edge("reasoning_verifier", "session_saver")

    # Session saver → final status router
    graph.add_edge("session_saver", "final_status_router")

    # Final status router → END
    graph.add_edge("final_status_router", END)

    # Compile the graph
    compiled = graph.compile()

    logger.info("LangGraph StateGraph built successfully")

    return compiled


def get_graph_mermaid() -> str:
    """Generate Mermaid diagram of the workflow.

    Returns:
        Mermaid diagram string
    """
    return """
    graph TD
        A[Start] --> B[input_validator]
        B --> C[session_loader]
        C --> D[image_quality_gate]
        D --> E[vision_extract]
        E --> F[clinical_extractor]
        F --> G[red_flag_detector]
        G --> H[triage_classifier]
        H --> I[triage_merger]
        I --> J[domain_classifier]
        J --> K{clarification_generator}
        K -->|need_clarify=True| L[session_saver]
        K -->|need_clarify=False| M{evidence_router}
        M -->|skip_evidence=True| N[navigator]
        M -->|skip_evidence=False| O[ncbi_query_builder]
        O --> P[ncbi_retriever_tool]
        P --> N
        N --> Q[weather_fetcher]
        Q --> R[reasoning_verifier]
        R --> L
        L --> S[final_status_router]
        S --> T[END]

        style G fill:#ff9999
        style K fill:#99ccff
        style M fill:#ffcc99
        style S fill:#99ff99
    """
