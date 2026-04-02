"""NCBI Retriever Tool node (Node 13).

Retrieves and ranks PubMed literature using NCBI service.
Returns top 5-8 articles per FR-031 with priority ordering.
"""
from typing import Any

from src.chains.nodes.base import safe_node
from src.services.ncbi_service import get_ncbi_service
from src.services.redis_service import get_redis_service
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("NCBIRetriever")
async def ncbi_retriever_tool(state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve and rank PubMed literature.

    Uses NCBI service to search PubMed with the built query.
    Implements caching per FR-056 (30min TTL) to avoid redundant calls.

    Returns 5-8 articles per FR-031, prioritized by:
    1. Guidelines (highest priority)
    2. Systematic Reviews
    3. Reviews
    4. RCTs
    5. Case Reports (lowest priority)

    Args:
        state: Current workflow state

    Returns:
        Updated state with evidence_selected list
    """
    ncbi_query = state.get("ncbi_query", "")
    session_id = state.get("session_id")

    if not ncbi_query:
        logger.info(
            "No NCBI query provided, skipping evidence retrieval",
            extra={"session_id": session_id}
        )
        return {"evidence_selected": []}

    try:
        # Check Redis cache first (per FR-056)
        redis_service = await get_redis_service()
        cache_key = f"ncbi:{hash(ncbi_query)}"

        if redis_service.is_healthy:
            cached_result = await redis_service.load_cached_result(cache_key)
            if cached_result:
                logger.info(
                    "Returning cached NCBI results",
                    extra={"session_id": session_id, "cache_key": cache_key}
                )
                return {"evidence_selected": cached_result.get("articles", [])}

        # Retrieve from NCBI service
        logger.info(
            f"Retrieving NCBI evidence: {ncbi_query}",
            extra={"session_id": session_id}
        )

        ncbi_service = get_ncbi_service()
        articles = await ncbi_service.search_and_retrieve(
            query=ncbi_query,
            max_results=8  # Return up to 8, will be ranked down to 5-8
        )

        logger.info(
            f"Retrieved {len(articles)} articles from NCBI",
            extra={"session_id": session_id}
        )

        # Cache results (30min TTL per FR-056)
        if redis_service.is_healthy and articles:
            await redis_service.cache_external_result(
                cache_key=cache_key,
                result={"articles": articles},
                ttl=1800
            )

        return {"evidence_selected": articles}

    except Exception as e:
        # Graceful degradation per FR-032
        logger.warning(
            f"NCBI retrieval failed: {e}, continuing without evidence",
            extra={"session_id": session_id}
        )
        return {"evidence_selected": []}
