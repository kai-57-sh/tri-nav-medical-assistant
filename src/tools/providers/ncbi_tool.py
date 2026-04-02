"""NCBI tool adapter for TriNav v2 runtime."""

from typing import Any

from src.services.ncbi_service import get_ncbi_service

_NCBI_MIN_RESULTS = 1
_NCBI_MAX_RESULTS = 50


def _validate_query(payload: dict[str, Any]) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "payload['query'] must be a non-empty string, "
            "for example {'query': 'dermatitis'}"
        )
    return query.strip()


def _validate_max_results(payload: dict[str, Any]) -> int:
    max_results = payload.get("max_results", 8)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        raise ValueError(
            "payload['max_results'] must be an integer in range "
            f"[{_NCBI_MIN_RESULTS}, {_NCBI_MAX_RESULTS}]"
        )
    if max_results < _NCBI_MIN_RESULTS or max_results > _NCBI_MAX_RESULTS:
        raise ValueError(
            "payload['max_results'] out of range; expected "
            f"[{_NCBI_MIN_RESULTS}, {_NCBI_MAX_RESULTS}], got {max_results}"
        )
    return max_results


async def ncbi_search_tool(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapter from generic payload to NCBI service call."""

    query = _validate_query(payload)
    max_results = _validate_max_results(payload)

    return await get_ncbi_service().search_and_retrieve(
        query=query,
        max_results=max_results,
    )
