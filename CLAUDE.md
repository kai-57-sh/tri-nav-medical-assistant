# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TriNav is a medical triage and hospital navigation assistant built with LangChain/LangGraph. It uses an 18-node stateful workflow to analyze symptoms (text + images), classify urgency, and provide hospital recommendations with navigation. The system emphasizes safety through dual verification (rule-based red flag detection + LLM reasoning verification).

## Technology Stack

**Backend:**
- Python 3.11+ (async/await)
- LangChain + LangGraph 1.0.5+ (18-node StateGraph workflow)
- LangServe (FastAPI-based API deployment)
- Pydantic v2 (data validation)
- Redis 5.0+ (session storage, 60min TTL)
- Qwen LLM models (via Alibaba DashScope OpenAI-compatible API)
- httpx (async HTTP client)
- Uvicorn (ASGI server)

**Frontend:**
- React 18.3.1 + TypeScript
- Vite (build tool)
- Tailwind CSS
- @assistant-ui/react with LangGraph integration

**Development Tools:**
- pytest (testing with unit/integration/contract separation)
- black (code formatting)
- ruff (linting)
- OpenTelemetry + Prometheus (observability)

## Architecture

### LangGraph Workflow (18 Nodes)

The core is a LangGraph StateGraph in `src/chains/graph/triage_graph.py`. State flows through these nodes:

```
Input Validator → Session Load → Navigation Detection → Image Quality Gate →
Vision Extract → Clinical Extract → Red Flag Detector → Triage Classifier →
Domain Classifier → Clarification Generator → Session Save →
Evidence Router (conditional) → NCBI Query Builder → NCBI Retriever →
Navigator → Weather Fetcher → Reasoning Verifier → Session Save →
Response Composer → Final Status Router
```

Key patterns:
- All nodes are async functions decorated with `@safe_node` for consistent error handling
- State is a dict with ~40 keys tracking the entire workflow
- Conditional edges route based on red flags, clarification needs, and evidence retrieval
- Session continuity via Redis with max 2 clarification rounds per session

### Dual Safety Architecture

1. **Rule-based red flag engine** (`src/config/red_flag_rules.yaml`): 15+ YAML-configured emergency detection patterns that override LLM decisions
2. **LLM reasoning verifier**: Final node that double-checks all outputs for prohibited content (diagnosis, prescription, delay-care language)
3. Both must pass for a response to be returned

### State Management

The workflow state dict includes:
- Input: `session_id`, `text`, `image_base64`, `gps_lat`, `gps_lng`
- Intermediate: `symptom_schema`, `visual_findings`, `red_flags_hit`, `llm_triage_level`, `rule_triage_level`
- Output: `triage_level`, `recommended_departments`, `possible_causes`, `navigation_result`, `weather_alert`, `final_response`

### External Services (with Graceful Degradation)

- **Amap (高德地图)**: Hospital search (10km radius, 3A prioritized) + route planning
- **Open-Meteo**: Weather alerts for travel advisories
- **NCBI E-utilities**: PubMed literature search (optional, skipped for emergencies)
- All services can fail without crashing the system

## Development Commands

### Backend
```bash
cd /AII-wuqi/AII_home/fq_775/TriNav

# Set up environment
cp .env.example .env  # Edit with API keys
docker-compose up -d redis  # Start Redis

# Run server (development)
langchain serve src.chains.triage_chain:chain --port 8000
# Or: cd src && python -m server

# Testing
pytest                           # All tests
pytest tests/unit/              # Unit tests only (fast, no external deps)
pytest tests/integration/       # Integration tests (require Redis + mocks)
pytest tests/unit/test_nodes/test_input_validator.py -v  # Single test file

# Code quality
black src/ tests/               # Format code
ruff check src/ tests/          # Lint code
```

### Frontend
```bash
cd frontend
npm install
npm run dev                     # Development server
npm run build                   # Production build
npm run lint                    # ESLint
```

## Key Files to Understand

- `src/chains/graph/triage_graph.py` - LangGraph workflow definition, node connections, conditional routing
- `src/chains/nodes/` - Individual node implementations (all use `@safe_node` decorator)
- `src/models/` - Pydantic models for input/output (NavigationResult, WeatherAlert, etc.)
- `src/services/` - External API integrations (LLM, Redis, Amap, NCBI, Weather)
- `src/config/red_flag_rules.yaml` - Emergency detection patterns (versioned, rule-based)
- `src/utils/safety.py` - Prohibited content filters and sanitization
- `tests/conftest.py` - Shared fixtures (minimal_state, mock services, sample data)

## Important Patterns

### Adding a New Node
1. Create async function in `src/chains/nodes/` with `@safe_node` decorator
2. Accept `state: dict` parameter, return updated `state`
3. Handle errors gracefully (return state with `error_message` key)
4. Register in `src/chains/graph/triage_graph.py` with appropriate edges
5. Add unit tests in `tests/unit/test_nodes/`

### Session Management
- Sessions stored in Redis with 60-minute TTL
- Only structured, non-sensitive data persisted (no raw images)
- Multi-turn conversations with max 2 clarification rounds
- Use `tests/conftest.py::minimal_state` fixture for test state templates

### Error Handling
- All nodes use `@safe_node` decorator for try/except wrapping
- External service failures are logged and handled gracefully
- State includes `error_message` key for failure tracking
- System remains operational even when Redis/Amap/NCBI are down

### Safety Requirements
- Never provide medical diagnoses or prescriptions
- Always recommend professional medical consultation
- Use qualified language ("疑似", "可能") for symptom analysis
- Red flag rules override LLM triage decisions
- All final outputs verified by reasoning_verifier node

## Test Structure

```
tests/
├── unit/              # Fast, isolated tests with mocks
│   ├── test_nodes/    # Individual node tests
│   ├── test_services/ # Service layer tests
│   └── test_utils/    # Utility function tests
└── integration/       # End-to-end workflow tests
```

All tests use pytest fixtures from `conftest.py`. External services are mocked to avoid dependencies.

## Environment Variables

Required in `.env`:
- `QWEN_API_KEY` - Alibaba DashScope API key for LLM
- `QWEN_BASE_URL` - Qwen API endpoint
- `REDIS_URL` - Redis connection string
- `AMAP_API_KEY` - Amap (高德) API key for navigation
- `LANGCHAIN_TRACING_V2` - Set to "false" during tests