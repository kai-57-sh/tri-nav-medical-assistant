# TriNav - Medical Triage and Hospital Navigation Assistant

**Status**: ✅ Production Ready

A LangChain-based medical triage system that helps users understand symptom urgency and navigate to appropriate care. The public `POST /assistant/invoke` envelope remains stable, but the service now defaults internally to the v3 runtime baseline, with the legacy LangGraph path retained for fallback and shadow comparison. Integrated external services include Amap navigation, Open-Meteo weather, and NCBI evidence retrieval.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Redis (local or Docker)
- Qwen API access (Alibaba Cloud DashScope)

### Installation

```bash
# Clone repository
cd /AII-wuqi/AII_home/fq_775/TriNav

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
# Edit .env with the required API keys
# No weather-specific env vars are required; weather uses Open-Meteo
```

### Development Setup

```bash
# Start Redis (local or Docker)
redis-server
# or: docker run --name trinav-redis -p 6379:6379 redis:7-alpine

# Optional: start the full local stack with the checked-in container assets
docker compose up --build

# Run tests
pytest

# Start API server
python -m src.server
```

### Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

### Logs

- Default log file: `logs/trinav.log` (override with `TRINAV_LOG_FILE`)

---

## Project Structure

```
TriNav/
├── src/
│   ├── chains/           # LangChain workflow (18 nodes)
│   │   ├── nodes/        # Individual workflow nodes
│   │   └── graph/        # LangGraph StateGraph
│   ├── models/           # Pydantic data models (7 entities)
│   ├── services/         # External API integrations
│   ├── utils/            # Logging, telemetry, metrics, safety
│   └── config/           # Settings and versioned rules
├── tests/                # Unit, integration, contract tests
├── docs/                 # Architecture, workflow, safety docs
├── specs/                # Feature specifications
│   └── 001-medical-triage-nav/
└── requirements.txt      # Python dependencies
```

---

## Implementation Status

✅ **Complete**:
- 18-node LangGraph workflow and FastAPI compat API surface
- `/assistant/invoke` compat envelope backed by the v3 runtime baseline
- Legacy LangGraph execution retained for fallback/shadow validation, not as the default path
- External services: Redis, Qwen LLM, Amap navigation, Open-Meteo weather, NCBI evidence
- Frontend UI (Vite + React)
- Structured logging and metrics

See [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for details.

---

## Architecture

**Technology Stack**:
- LangChain + LangGraph 1.0.5+ (legacy workflow fallback and shadow path)
- FastAPI + compat envelope at `/assistant/invoke`, defaulting internally to the v3 runtime
- Python 3.11+ (async/await)
- Redis 5.0+ (session storage, 60min TTL)
- Pydantic v2 (data validation)
- Qwen models (LLM via OpenAI-compatible API)

**18-Node Workflow**:
1. Input Validator → 2. Session Load → 3. Image Quality Gate → 4. Vision Extract
→ 5. Clinical Extractor → 6. Red Flag Detector → 7. Triage Classifier
→ 8. Triage Merger → 9. Clarification Generator → 10. Session Save
→ 11. Evidence Router → 12. NCBI Query Builder → 13. NCBI Retriever
→ 14. Domain Classifier → 15. Navigator → 16. Weather Fetcher
→ 17. Reasoning Verifier → 18. Response Composer → Final Status Router

---

## Safety & Compliance

✅ **Constitution Aligned**:
- **Safety First**: Red flag rules override LLM decisions
- **Clear Boundaries**: No diagnosis/prescription language
- **Prompt Care**: All levels recommend medical attention
- **Data Minimization**: Only structured data in Redis (60min TTL)
- **Fallback Protection**: Graceful degradation on external service failures

**Safety Mechanisms**:
- Dual verification (rule-based + LLM reasoning verifier)
- Prohibited content filters (diagnosis, prescription, delay-care)
- Qualified language enforcement ("疑似", "可能")
- 15 versioned red flag rules

---

## API Usage

### Text-Only Triage (US1)

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "text": "手臂出现红疹，有点痒，持续2天"
    }
  }'
```

**Response** (excerpt):
```json
{
  "status": "final",
  "triage_level": "ROUTINE",
  "recommended_departments": ["皮肤科"],
  "possible_causes": [
    "过敏相关皮疹（疑似）",
    "接触性皮炎（疑似）"
  ],
  "red_flags": ["如果出现呼吸困难/脸唇肿胀，请立刻急诊"],
  "disclaimer": "本建议仅供参考，不替代专业医疗诊断"
}
```

### With GPS Navigation (US3)

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "550e8400-e29b-41d4-a716-446655440002",
      "text": "手臂出现红疹，有点痒，持续2天",
      "gps_lat": 39.9042,
      "gps_lng": 116.4074
    }
  }'
```

**Response includes**:
- 3 hospital recommendations (3A prioritized)
- Route plan to top hospital
- Weather alert from Open-Meteo (if available, no API key required)
> Note: navigation uses Amap and primarily covers mainland China. Non-China coordinates may return no hospitals.

---

## Development Workflow

### Running Tests

```bash
# Unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (require Redis and mock external APIs)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

### Adding a New Node

1. Create file in `src/chains/nodes/`
2. Implement async node function with `@safe_node` decorator
3. Register in `src/chains/graph/triage_graph.py`
4. Add unit tests in `tests/unit/test_nodes/`

---

## Performance Targets

- EMERGENCY triage: ≤5 seconds p95 (NCBI skipped)
- ROUTINE triage: ≤15 seconds p95
- 100 concurrent users (baseline)
- 99.5% uptime monthly

---

## Documentation

- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) - Detailed implementation status
- [specs/001-medical-triage-nav/spec.md](./specs/001-medical-triage-nav/spec.md) - Feature specification
- [specs/001-medical-triage-nav/plan.md](./specs/001-medical-triage-nav/plan.md) - Technical plan
- [specs/001-medical-triage-nav/tasks.md](./specs/001-medical-triage-nav/tasks.md) - Implementation tasks
- [specs/001-medical-triage-nav/data-model.md](./specs/001-medical-triage-nav/data-model.md) - Data models
- [specs/001-medical-triage-nav/quickstart.md](./specs/001-medical-triage-nav/quickstart.md) - Developer guide

---

## Contributing

This project follows the SpecKit development workflow:
1. Feature specification (`spec.md`)
2. Implementation planning (`/speckit.plan`)
3. Task breakdown (`/speckit.tasks`)
4. Implementation (`/speckit.implement`)

---

## License

[Your License Here]

---

## Support

For issues or questions:
- Review [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for current progress
- Check `docs/SAFETY.md` for safety-related concerns (when created)
- Review technical plan in `specs/001-medical-triage-nav/plan.md`
