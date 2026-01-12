"""Integration test patches to avoid external calls."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_ncbi_services(mock_ncbi_service, mock_redis_service):
    """Patch NCBI and Redis services for integration tests."""
    with patch("src.chains.nodes.ncbi_retriever_tool.get_ncbi_service", return_value=mock_ncbi_service):
        with patch("src.chains.nodes.ncbi_retriever_tool.get_redis_service", return_value=mock_redis_service):
            yield
