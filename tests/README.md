# TriNav Test Suite

This directory contains unit tests for all TriNav components.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── unit/
│   └── test_nodes/            # Unit tests for LangGraph nodes
│       ├── test_input_validator.py
│       ├── test_session_loader.py
│       ├── test_red_flag_detector.py
│       ├── test_triage_classifier.py
│       ├── test_triage_merger.py
│       ├── test_clarification_generator.py
│       ├── test_vision_nodes.py
│       ├── test_evidence_navigation_nodes.py
│       └── test_final_nodes.py
└── (future) integration/       # Integration tests
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Only Unit Tests
```bash
pytest tests/unit/
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Run Specific Test File
```bash
pytest tests/unit/test_nodes/test_input_validator.py
```

### Run Specific Test
```bash
pytest tests/unit/test_nodes/test_input_validator.py::test_input_validator_valid_text
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Marker
```bash
pytest -m unit        # Run only unit tests
pytest -m integration # Run only integration tests
pytest -m slow        # Run only slow tests
```

## Test Coverage Goals

- **Target**: 80% code coverage
- **Current**: ~60% (node tests complete, service tests pending)

## What's Tested

### ✅ LangGraph Nodes (All 18 nodes)
- Input validation and error handling
- Session management
- Red flag detection
- Triage classification and merging
- Clarification generation
- Vision processing
- Evidence retrieval
- Domain classification
- Navigation and weather
- Safety verification
- Response composition

### ⏳ Services (Pending)
- Redis service
- LLM service
- Amap service
- NCBI service
- Weather service

### ⏳ Integration Tests (Pending)
- End-to-end workflow
- API contract tests
- State transition tests

## Writing New Tests

1. Create test file in appropriate directory
2. Import fixtures from `conftest.py`
3. Use `@pytest.mark.asyncio` for async tests
4. Mock external dependencies
5. Test both success and failure cases
6. Test edge cases and error handling

Example:
```python
import pytest
from src.chains.nodes.my_node import my_node

@pytest.mark.asyncio
async def test_my_node_success(minimal_state):
    """Test my_node with valid input."""
    result = await my_node(minimal_state)
    assert result["expected_field"] is not None
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every commit to main branch
- Daily scheduled runs

Coverage is tracked and reported in CI/CD pipeline.
