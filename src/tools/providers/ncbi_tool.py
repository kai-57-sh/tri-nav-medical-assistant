"""NCBI tool adapter for TriNav v2 runtime."""

from typing import Any, cast

from src.services.ncbi_service import get_ncbi_service


async def ncbi_search_tool(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapter from generic payload to NCBI service call."""

    query = cast(str, payload.get("query", ""))
    max_results = cast(int, payload.get("max_results", 8))

    return await get_ncbi_service().search_and_retrieve(
        query=query,
        max_results=max_results,
    )
