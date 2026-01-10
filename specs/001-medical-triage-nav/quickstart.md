# Quickstart Guide: TriNav Development Setup

**Feature**: Medical Triage and Hospital Navigation Assistant (TriNav)
**Date**: 2025-01-09
**Tech Stack**: LangChain + LangGraph + LangServe + Python 3.11+

---

## Prerequisites

Before starting, ensure you have:

1. **Python 3.11+** installed
   ```bash
   python --version  # Should be 3.11.x or higher
   ```

2. **Redis** running locally or Docker installed
   ```bash
   # Option 1: Redis server
   redis-server --version

   # Option 2: Docker
   docker --version
   ```

3. **Qwen API Access** (Alibaba Cloud DashScope or compatible endpoint)
   - API key available
   - Endpoint URL documented

4. **External API Keys** (optional for development)
   - Amap (高德地图) API key for hospital navigation
   - Weather service API key

5. **Git** for version control
   ```bash
   git --version
   ```

---

## Project Setup

### 1. Clone Repository and Create Virtual Environment

```bash
# Navigate to project root
cd /path/to/TriNav

# Create virtual environment
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

**Expected `requirements.txt` content**:
```txt
# Core LangChain stack
langchain>=0.1.0
langchain-core>=0.1.0
langchain-openai>=0.0.5
langgraph>=1.0.5
langserve>=0.0.40

# Data and validation
pydantic>=2.0.0
python-multipart>=0.0.6

# Redis and caching
redis>=5.0.0

# Async HTTP client
httpx>=0.25.0

# ASGI server
uvicorn[standard]>=0.24.0

# Observability
opentelemetry-api>=1.21.0
opentelemetry-sdk>=1.21.0
prometheus-client>=0.19.0
```

**Expected `requirements-dev.txt` content**:
```txt
# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0

# Code quality
black>=23.0.0
ruff>=0.1.0
mypy>=1.0.0

# Development utilities
ipython>=8.0.0
jupyter>=1.0.0
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Expected `.env.example` content**:
```bash
# === Qwen Models ===
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=your_qwen_api_key_here

# === Redis ===
REDIS_URL=redis://localhost:6379

# === External APIs ===
AMAP_API_KEY=your_amap_api_key_here
WEATHER_API_URL=https://api.weather.example.com
WEATHER_API_KEY=your_weather_api_key_here

# === NCBI/PubMed (no API key required) ===
NCBI_BASE_URL=https://eutils.ncbi.nlm.nih.gov/entrez/eutils

# === Observability ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here  # Optional
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # Optional for local Jaeger
```

**Fill in your actual values**:
- `QWEN_API_KEY`: Your Alibaba Cloud DashScope API key
- `REDIS_URL`: `redis://localhost:6379` for local development
- `AMAP_API_KEY`: Your Amap (高德地图) API key
- `WEATHER_API_KEY`: Your weather service API key (optional)

---

## Local Development

### 1. Start Redis (Docker)

```bash
# Using Docker Compose (recommended)
docker-compose up -d redis

# Or using plain Docker
docker run -d -p 6379:6379 redis:7-alpine

# Verify Redis is running
redis-cli ping  # Should return PONG
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_nodes/test_red_flag_detector.py

# Run async tests
pytest tests/integration/ -v
```

### 3. Start LangServe Development Server

```bash
# Option 1: Using LangChain CLI
langchain serve src.chains.triage_chain:chain --port 8000

# Option 2: Using Uvicorn directly
uvicorn src.server:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 4. Verify API is Running

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"1.0.0","timestamp":"2025-01-09T10:30:00Z"}
```

---

## Making Your First API Call

### 1. Routine Triage Example (Text Only)

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "手臂出现红疹，有点痒，持续2天"
  }'
```

**Expected response** (excerpt):
```json
{
  "status": "final",
  "triage_level": "ROUTINE",
  "recommended_departments": ["皮肤科"],
  "possible_causes": [
    "过敏相关皮疹（疑似）",
    "接触性皮炎（疑似）"
  ],
  "self_care_tips": [
    "避免抓挠患处",
    "记录皮疹变化"
  ],
  "red_flags": [
    "如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"
  ],
  "disclaimer": "本建议仅供参考，不替代专业医疗诊断",
  "hotline_tip": "如果你不确定症状严重程度，或者情况在变重，建议你也可以拨打当地医疗热线或直接拨打医院电话先确认"
}
```

### 2. Emergency Triage Example

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440001",
    "text": "胸口闷，呼吸困难，喘不过气"
  }'
```

**Expected response** (excerpt):
```json
{
  "status": "final",
  "triage_level": "EMERGENCY",
  "recommended_departments": ["急诊"],
  "possible_causes": [
    "可能的心脏问题（疑似）",
    "呼吸系统问题（疑似）"
  ],
  "red_flags": [
    "症状紧急，建议立即急诊/呼叫急救"
  ]
}
```

### 3. With GPS Navigation

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440002",
    "text": "手臂出现红疹，有点痒，持续2天",
    "lat": 39.9042,
    "lng": 116.4074
  }'
```

**Expected response** includes `navigation` field with 3 hospitals and route plan.

### 4. Multi-Turn Conversation

```bash
# Turn 1: Insufficient information
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440003",
    "text": "头痛"
  }'

# Response: status=need_more_info, clarify_questions=["头痛持续多久?", ...]

# Turn 2: Provide clarification
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440003",
    "text": "从昨天开始，持续痛，没有发烧"
  }'

# Response: status=final with triage assessment
```

---

## Development Workflow

### 1. Code Organization

```
TriNav/
├── src/
│   ├── chains/          # LangChain workflow
│   ├── models/          # Pydantic entities
│   ├── services/        # External API integrations
│   ├── utils/           # Shared utilities
│   └── config/          # Configuration files
├── tests/               # Test suites
├── docs/                # Documentation
└── specs/               # Feature specifications
```

### 2. Running Tests

```bash
# Unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (require Redis and mock external APIs)
pytest tests/integration/ -v

# Contract tests (validate OpenAPI schema)
pytest tests/contract/ -v

# All tests with coverage
pytest --cov=src --cov-report=html
```

### 3. Code Quality Checks

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/
```

### 4. Debugging with LangSmith (Optional)

If you have a LangSmith API key:

```bash
# Set in .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=trinav-dev

# Run server
langchain serve src.chains.triage_chain:chain

# View traces at https://smith.langchain.com
```

---

## Common Development Tasks

### Adding a New Node to the Workflow

1. **Create node file** in `src/chains/nodes/`:
```bash
# Example: Add a new node for drug interaction checking
touch src/chains/nodes/safety/drug_checker.py
```

2. **Implement node function**:
```python
# src/chains/nodes/safety/drug_checker.py
from typing import Dict, Any
from ..base import safe_node

@safe_node("DrugChecker")
async def drug_checker(state: Dict[str, Any]) -> Dict[str, Any]:
    # Your logic here
    return {"drug_interactions": []}
```

3. **Register in graph builder**:
```python
# src/chains/graph/builder.py
from nodes.safety.drug_checker import drug_checker

def build_graph(redis_conn_string: str) -> StateGraph:
    builder = StateGraph(TriageState)
    builder.add_node("DrugChecker", drug_checker)
    # ... add edges
```

### Modifying Red Flag Rules

Edit `config/red_flag_rules.yaml`:
```yaml
- id: RF_NEW_RULE
  priority: high
  version: 1.0.0
  conditions:
    - field: symptoms
      op: contains_any
      value: ["新症状"]
  triage_level: EMERGENCY
  user_message: "新的危险信号描述"
  department: ["急诊"]
```

Rules are version-controlled (per FR-054) and require medical advisor sign-off (per SC-008).

### Testing External Service Integrations

```bash
# Mock external services in tests
export MOCK_AMAP=true
export MOCK_NCBI=true

# Run tests with mocks
pytest tests/integration/test_external_services.py -v
```

---

## Troubleshooting

### Issue: "Module not found" errors

```bash
# Ensure virtual environment is activated
which python  # Should point to .venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: Redis connection refused

```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Start Redis if not running
docker-compose up -d redis
```

### Issue: API key errors

```bash
# Verify .env file is loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('QWEN_API_KEY'))"

# Check .env file exists and is not in .gitignore
ls -la .env
```

### Issue: Tests failing with import errors

```bash
# Ensure you're running tests from project root
cd /path/to/TriNav
pytest tests/  # NOT from inside tests/ directory
```

---

## Production Deployment

### Using LangServe CLI

```bash
# Build Docker image
docker build -t trinav:latest .

# Run with Docker Compose (production mode)
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables for Production

```bash
# Required
QWEN_API_KEY=<production-key>
REDIS_URL=redis://production-redis:6379

# Optional but recommended
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=trinav-prod
OTEL_EXPORTER_OTLP_ENDPOINT=<jaeger-collector-url>
```

### Scaling to 100 Concurrent Users

```bash
# Start 4 Uvicorn workers (handles ~100 concurrent users)
uvicorn src.server:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## Next Steps

1. ✅ Complete local development setup
2. ✅ Run tests and verify all pass
3. ✅ Make first API call successfully
4. → Review system architecture: `docs/ARCHITECTURE.md`
5. → Review 18-node workflow: `docs/WORKFLOW.md`
6. → Review safety measures: `docs/SAFETY.md`

---

## Additional Resources

- **LangChain Documentation**: https://python.langchain.com/
- **LangGraph Guide**: https://python.langchain.com/docs/langgraph
- **LangServe Deployment**: https://python.langchain.com/docs/langserve
- **Qwen Models**: https://help.aliyun.com/zh/dashscope/
- **Redis for Python**: https://redis.readthedocs.io/en/stable/
- **Pydantic v2**: https://docs.pydantic.dev/latest/

---

## Support

For issues or questions:
- Check `docs/SAFETY.md` for safety-related concerns
- Review `specs/001-medical-triage-nav/plan.md` for technical decisions
- Open an issue in the repository (if available)
