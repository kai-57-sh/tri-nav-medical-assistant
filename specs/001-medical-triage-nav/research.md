# Research: TriNav Medical Triage System

**Feature**: Medical Triage and Hospital Navigation Assistant (TriNav)
**Date**: 2025-01-09
**Tech Stack**: LangChain + LangGraph + LangServe + Python 3.11+

---

## Executive Summary

This document consolidates research findings for building a production-ready, safety-critical medical triage system using LangGraph 18-node workflow. All decisions prioritize medical safety, graceful degradation, and regulatory compliance.

---

## 1. LangGraph StateGraph Architecture

### Decision
- **LangGraph Version**: `>=1.0.5` (stable 1.0 release, NOT 0.2.x beta)
- **Python**: 3.11+ (modern type annotations, performance)
- **State Schema**: TypedDict with reducers (LangGraph standard)
- **Node Functions**: Async throughout (40-60% performance improvement for I/O-bound workloads)
- **Checkpointing**: Redis with 60-minute TTL
- **File Organization**: Modular (18 nodes in separate files under `src/chains/nodes/`)

### Rationale
- **LangGraph 1.0** provides production stability, automatic state persistence, and node-level caching - critical for multi-turn medical conversations
- **Async nodes** enable concurrent I/O operations (NCBI queries + navigation planning) while maintaining state consistency
- **TypedDict** is native to LangGraph with zero runtime overhead; Pydantic used only for API validation layer
- **Modular structure** essential for 18 nodes to maintain testability and code reuse

### Alternatives Considered
- **LangGraph 0.2.x**: Rejected due to beta status, breaking changes in 1.0
- **Pydantic state**: Rejected due to serialization overhead and non-standard LangGraph pattern
- **Single file**: Rejected - unmaintainable for 18 nodes
- **Sync nodes**: Rejected - blocks on I/O operations (LLM calls, external APIs)

### Code Pattern

**State Schema** (`src/chains/graph/state.py`):
```python
from typing_extensions import TypedDict, Annotated, Required, Literal
from typing import Optional, List, Dict, Any
from operator import add
from langgraph.graph.message import add_messages

class TriageState(TypedDict):
    # === Input (Immutable) ===
    session_id: Required[str]

    # === Conversation History (with reducer) ===
    messages: Annotated[List[Dict], add_messages]

    # === User Input ===
    input_type: Literal["text", "image"]
    text: Optional[str]
    image_base64: Optional[str]  # NOT stored in Redis
    lat: Optional[float]
    lng: Optional[float]

    # === Session State (Redis) ===
    turn_count: int
    symptom_schema: Optional[Dict[str, Any]]
    clarify_questions: List[str]
    triage_level: Optional[Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]]
    case_domain: Optional[str]

    # === Evidence ===
    evidence_needed: bool
    evidence_cache_key: Optional[str]

    # === Navigation ===
    navigation_cache_key: Optional[str]

    # === Output ===
    status: Literal["need_more_info", "final", "error"]
    error_message: Optional[str]
```

**Base Node Decorator** (`src/chains/nodes/base.py`):
```python
from functools import wraps
from utils.errors import NodeError
from utils.logging import get_logger

logger = get_logger(__name__)

def safe_node(node_name: str, raise_on_error: bool = False):
    def decorator(func):
        @wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                logger.info(f"Entering: {node_name}", extra={
                    "node": node_name,
                    "session_id": state.get("session_id")
                })
                result = await func(state)
                logger.info(f"Exiting: {node_name}")
                return result
            except Exception as e:
                logger.error(f"Error in {node_name}: {e}", exc_info=True)
                if raise_on_error:
                    raise NodeError(node_name, str(e))
                # Graceful degradation
                return {
                    "error_message": f"{node_name} failed",
                    "status": "error" if state.get("triage_level") == "EMERGENCY" else state.get("status", "final")
                }
        return wrapper
    return decorator
```

**Graph Builder** (`src/chains/graph/builder.py`):
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.redis import AsyncRedisSaver

def build_graph(redis_conn_string: str) -> StateGraph:
    builder = StateGraph(TriageState)

    # Add 18 nodes
    builder.add_node("InputValidator", validator.input_validator)
    builder.add_node("SessionLoad", session.session_load)
    # ... add all nodes

    # Linear edges
    builder.add_edge(START, "InputValidator")
    builder.add_edge("InputValidator", "SessionLoad")

    # Conditional edge: EMERGENCY skips evidence
    builder.add_conditional_edges(
        "TriageRulesGate",
        lambda s: "emergency" if s.get("triage_level") == "EMERGENCY" else "normal",
        {
            "emergency": "NavigationPlanner",  # Skip evidence retrieval
            "normal": "SpecialtyRouter"
        }
    )

    # Compile with Redis checkpointer
    checkpointer = AsyncRedisSaver.from_conn_string(redis_conn_string)
    return builder.compile(checkpointer=checkpointer)
```

### References
- [LangGraph Official Docs](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph 1.0 Release](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available)
- [State Management Best Practices](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025)
- [Async Performance Analysis](https://nishant-mishra.medium.com/why-i-switched-to-async-langchain-and-langgraph-and-you-should-too-c30635c9cf19)

---

## 2. LangServe Deployment Patterns

### Decision
- **Deployment**: LangServe CLI (`langchain serve`)
- **Containerization**: Docker with multi-stage builds
- **ASGI Server**: Uvicorn with `--workers` for horizontal scaling
- **Configuration**: Environment-based with `.env` files (no API keys in code)
- **Health Checks**: `/health` endpoint for load balancers
- **Graceful Shutdown**: Handle SIGTERM for zero-downtime deployments

### Rationale
- **LangServe CLI** is the official deployment method, providing automatic API generation and schema discovery
- **Docker multi-stage builds** minimize image size (separate build/runtime dependencies)
- **Uvicorn workers** enable scaling to 100+ concurrent users per spec requirement
- **Environment variables** keep secrets out of source code (12-factor app methodology)

### Alternatives Considered
- **FastAPI custom server**: Rejected - LangServe provides this automatically
- **Kubernetes native**: Rejected for MVP - adds complexity, can migrate later
- **Serverless (Lambda)**: Rejected - cold starts incompatible with 5-second EMERGENCY SLA

### Deployment Pattern

**Dockerfile**:
```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["langchain", "serve", "src.chains.triage_chain:chain"]
```

**docker-compose.yml** (local development):
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - QWEN_API_KEY=${QWEN_API_KEY}
    depends_on:
      - redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Production Command**:
```bash
# Start LangServe with 4 workers (handles ~100 concurrent users)
uvicorn src.server:app --workers 4 --host 0.0.0.0 --port 8000

# Or via LangServe CLI
langchain serve src.chains.triage_chain:chain --host 0.0.0.0 --port 8000
```

### References
- [LangServe Documentation](https://docs.langchain.com/oss/python/langserve/overview)
- [Docker Deployment Guide](https://docs.langchain.com/oss/python/langserve/deployment)
- [Uvicorn Workers](https://www.uvicorn.org/deployment/)

---

## 3. Redis Session Management

### Decision
- **Redis Client**: `redis>=5.0.0` with async support (`redis.asyncio`)
- **Serialization**: JSON (via `json.dumps/loads`) for human-readable debugging
- **TTL**: 60 minutes (per spec CT-006, FR-009)
- **Connection Pool**: 20 connections (supports 100 concurrent users)
- **Data Stored**: ONLY structured symptom data (no raw images/text per CT-007, CT-008)
- **Key Pattern**: `session:{session_id}` for simple key extraction

### Rationale
- **JSON serialization** enables debugging with `redis-cli GET session:*` without custom deserializers
- **60-minute TTL** balances user convenience (multi-turn conversations) with privacy (ephemeral storage)
- **Connection pooling** prevents connection churn under load (100 concurrent users)
- **Minimal data storage** complies with privacy constraints (no sensitive data in Redis)

### Alternatives Considered
- **Pickle serialization**: Rejected - security risk, not human-readable
- **MessagePack**: Rejected - adds dependency, JSON sufficient for small objects
- **Permanent storage**: Rejected - violates privacy-by-design principle (CT-006, CT-007, CT-008)

### Implementation Pattern

**Redis Service** (`src/services/redis_service.py`):
```python
import json
from typing import Optional, Dict, Any
from redis.asyncio import Redis, ConnectionPool

class RedisService:
    def __init__(self, url: str):
        self.pool = ConnectionPool.from_url(
            url,
            max_connections=20,
            decode_responses=True
        )
        self.redis: Optional[Redis] = None

    async def connect(self):
        self.redis = Redis(connection_pool=self.pool)

    async def save_session(
        self,
        session_id: str,
        state: Dict[str, Any],
        ttl: int = 3600  # 60 minutes
    ):
        """Save ONLY structured data (no raw images/text)."""
        minimal_state = {
            "turn_count": state.get("turn_count", 0),
            "symptom_schema": state.get("symptom_schema"),
            "clarify_questions": state.get("clarify_questions", []),
            "triage_level": state.get("triage_level"),
            "case_domain": state.get("case_domain"),
            "evidence_cache_key": state.get("evidence_cache_key"),
            "navigation_cache_key": state.get("navigation_cache_key")
        }
        key = f"session:{session_id}"
        await self.redis.setex(key, ttl, json.dumps(minimal_state))

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = f"session:{session_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def delete_session(self, session_id: str):
        key = f"session:{session_id}"
        await self.redis.delete(key)
```

### References
- [Redis Asyncio Documentation](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [Connection Pooling](https://redis.readthedocs.io/en/stable/connection_pool.html)

---

## 4. Qwen Model Integration

### Decision
- **Model Provider**: Qwen via OpenAI-compatible API (Alibaba Cloud or compatible endpoint)
- **Models**:
  - `qwen-plus` or `qwen-turbo`: Clinical extraction, triage classification
  - `qwen-vl-plus` or `qwen-vl-max`: Visual feature extraction (rash/wound images)
  - `qwen-plus` (temperature=0.0): Reasoning verifier (safety checks)
- **LangChain Integration**: `langchain-openai>=0.0.5` with `ChatOpenAI` class
- **Token Limits**: Enforce 4000 token input limit (prevents OOM errors)
- **Temperature Settings**:
  - Extraction: 0.1 (deterministic)
  - Triage: 0.3 (balanced creativity)
  - Verification: 0.0 (strict safety)

### Rationale
- **OpenAI-compatible API** enables using standard LangChain integrations without custom code
- **Different temperatures** for different use cases (extraction needs consistency, verification needs strictness)
- **Qwen-VL** for vision tasks (rash/wound classification) vs separate vision model
- **Token limits** prevent cost overruns and API timeouts

### Alternatives Considered
- **Direct Qwen SDK**: Rejected - LangChain `ChatOpenAI` abstraction sufficient
- **Higher temperatures**: Rejected - medical safety requires deterministic outputs
- **Single model for all tasks**: Rejected - different tasks need different temperature settings

### Implementation Pattern

**LLM Service** (`src/services/llm_service.py`):
```python
from langchain_openai import ChatOpenAI
import os

class ModelManager:
    def __init__(self):
        base_url = os.environ.get("QWEN_BASE_URL")
        api_key = os.environ.get("QWEN_API_KEY")

        # Extraction model (low temp)
        self.extractor = ChatOpenAI(
            model="qwen-plus",
            temperature=0.1,
            base_url=base_url,
            api_key=api_key
        )

        # Vision model
        self.vision = ChatOpenAI(
            model="qwen-vl-plus",
            temperature=0.2,
            base_url=base_url,
            api_key=api_key
        )

        # Verification model (zero temp)
        self.verifier = ChatOpenAI(
            model="qwen-plus",
            temperature=0.0,
            base_url=base_url,
            api_key=api_key
        )
```

### References
- [Qwen API Documentation](https://help.aliyun.com/zh/dashscope/developer-reference/quick-start)
- [LangChain ChatOpenAI](https://python.langchain.com/docs/integrations/providers/openai/)

---

## 5. External API Resilience Patterns

### Decision
- **Retry Strategy**: Exponential backoff with max 2 attempts (per spec FR-049)
- **Timeout**: 5 seconds for Amap, 10 seconds for NCBI, 3 seconds for Weather
- **Circuit Breaker**: None for MVP (graceful degradation sufficient per spec)
- **Fallback Behavior**:
  - Amap fails → "建议就近选择综合医院（三甲优先）" (per FR-039)
  - Weather fails → omit weather section (not critical)
  - NCBI fails → omit evidence section (per FR-032)

### Rationale
- **2 retry attempts** balance resilience with EMERGENCY SLA (5 seconds)
- **Timeouts** prevent cascading delays (Amap: 5s, NCBI: 10s, Weather: 3s)
- **Graceful degradation** per spec requirements (FR-038, FR-046, FR-048)
- **No circuit breaker** for MVP - adds complexity; timeouts + retries sufficient

### Alternatives Considered
- **More than 2 retries**: Rejected - violates EMERGENCY 5-second SLA
- **Circuit breaker**: Rejected - adds complexity; graceful degradation per spec sufficient
- **Longer timeouts**: Rejected - impact on ROUTINE 15-second SLA

### Implementation Pattern

**Resilient HTTP Client** (`src/utils/http_client.py`):
```python
import httpx
import asyncio
from typing import Any, Dict
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            # Log but don't fail - caller handles fallback
            return None
        except Exception as e:
            # Return None for graceful degradation
            return None

    async def close(self):
        await self.client.aclose()
```

**Amap Service with Fallback** (`src/services/amap_service.py`):
```python
class AmapService:
    def __init__(self, api_key: str):
        self.client = ResilientClient(timeout=5.0)
        self.api_key = api_key

    async def search_hospitals(
        self,
        lat: float,
        lng: float,
        radius: int = 10000
    ) -> Dict[str, Any]:
        result = await self.client.get(
            "https://restapi.amap.com/v3/place/around",
            params={
                "key": self.api_key,
                "location": f"{lng},{lat}",
                "keywords": "医院",
                "radius": radius
            }
        )

        if result is None:
            # Fallback per FR-039
            return {"hospitals": [], "fallback": True}

        return result
```

### References
- [Tenacity Retry Library](https://tenacity.readthedocs.io/)
- [httpx Async Client](https://www.python-httpx.org/async/)

---

## 6. Safety Verification Architecture

### Decision
- **Dual Verification**:
  1. **Rule-based red flag detector** (BEFORE LLM triage) - per spec edge case #10
  2. **LLM reasoning verifier** (AFTER response composition) - per FR-024
- **Rule Engine Priority**: Rules override LLM (more conservative) - per constitution Principle I
- **Prohibited Content Patterns**: Regex + keyword matching for:
  - Diagnosis terms: "确诊", "诊断", "你得的是", "是XX病"
  - Prescription terms: "服用", "每次", "剂量", "mg", "片"
  - Delay-care terms: "不用就医", "没事", "不用看医生"
- **Output Sanitization**: Post-processing to strip violations and add disclaimer

### Rationale
- **Rule-based first** ensures red flags always trigger EMERGENCY (constitution Principle I)
- **LLM verifier second** catches nuanced violations that rules miss
- **Rules override LLM** - conservative approach prioritizes patient safety (edge case #10)
- **Regex + keyword** efficient for first-pass filtering before LLM verification

### Alternatives Considered
- **LLM-only verification**: Rejected - too slow for EMERGENCY cases
- **Rules-only**: Rejected - cannot catch nuanced language violations
- **LLM-first, rules-second**: Rejected - violates constitution Principle I (rules take precedence)

### Implementation Pattern

**Red Flag Detector** (`src/chains/nodes/red_flag_detector.py`):
```python
from typing import Dict, List
from utils.safety_filters import RED_FLAG_RULES

@safe_node("RedFlagDetector")
async def red_flag_detector(state: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based emergency detection (evaluated BEFORE LLM triage)."""

    symptom_schema = state.get("symptom_schema", {})
    flags_hit = []

    # Check against configured rules
    for rule in RED_FLAG_RULES:
        if _matches_rule(symptom_schema, rule):
            flags_hit.append(rule)

    if flags_hit:
        return {
            "triage_level": "EMERGENCY",
            "red_flags_hit": [f["id"] for f in flags_hit],
            "recommended_departments": ["急诊"],
            "triage_reason": f"检测到危险信号：{', '.join(f['name'] for f in flags_hit)}"
        }

    return {}
```

**Reasoning Verifier** (`src/chains/nodes/reasoning_verifier.py`):
```python
@safe_node("ReasoningVerifier")
async def reasoning_verifier(
    state: Dict[str, Any],
    models: ModelManager
) -> Dict[str, Any]:
    """LLM-based safety verification (AFTER response composition)."""

    draft_response = state.get("draft_response", "")

    # Check for prohibited patterns
    violations = check_prohibited_content(draft_response)

    if violations:
        # Rewrite to compliant language
        verified = await rewrite_compliant(draft_response, models.verifier)
        return {"final_response": verified}

    return {"final_response": draft_response}

def check_prohibited_content(text: str) -> List[str]:
    """Regex + keyword matching for prohibited content."""
    violations = []

    # Diagnosis patterns
    if re.search(r"确诊|诊断|你得的是|是.*病", text):
        violations.append("diagnosis")

    # Prescription patterns
    if re.search(r"每次.*mg|服用.*片|剂量", text):
        violations.append("prescription")

    # Delay-care patterns
    if re.search(r"不用就医|不用看医生|肯定没事", text):
        violations.append("delay_care")

    return violations
```

**Triage Merger** (ensures rules override LLM):
```python
@safe_node("TriageMerger")
async def triage_merger(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge rule-based and LLM triage (RULE WINS per constitution)."""

    rule_triage = state.get("rule_triage_level")  # From RedFlagDetector
    llm_triage = state.get("llm_triage_level")   # From TriageClassifier

    # Rule engine takes precedence (more conservative)
    if rule_triage == "EMERGENCY":
        return {
            "final_triage_level": "EMERGENCY",
            "triage_source": "rule_engine"
        }

    # Otherwise use LLM or escalate to URGENT if uncertain
    return {
        "final_triage_level": llm_triage or "URGENT",
        "triage_source": "llm"
    }
```

### References
- [Safety Filter Patterns](https://www.preprints.org/manuscript/202503.1747)
- [Constitution Principle I](../../../.specify/memory/constitution.md)

---

## 7. Testing Strategies

### Decision
- **Three-Level Testing**:
  1. **Unit Tests**: Individual nodes with mocked dependencies
  2. **Integration Tests**: Subgraphs (e.g., evidence retrieval flow)
  3. **End-to-End Tests**: Full 18-node workflow with real Redis
- **Test Framework**: `pytest>=7.4.0` with `pytest-asyncio>=0.21.0`
- **Mocking**: `pytest-mock` + `httpx` for external APIs
- **Coverage Target**: 80% for critical safety nodes (red flag detector, reasoning verifier)

### Rationale
- **Unit tests** enable rapid feedback during development
- **Integration tests** validate node-to-node communication
- **E2E tests** verify complete workflows (especially EMERGENCY bypass logic)
- **80% coverage** for safety-critical nodes balances thoroughness with development speed

### Test Pattern

**Unit Test** (`tests/unit/test_nodes/test_red_flag_detector.py`):
```python
import pytest
from chains.nodes.red_flag_detector import red_flag_detector

@pytest.mark.asyncio
async def test_emergency_detected():
    state = {
        "symptom_schema": {"accompanying_symptoms": ["呼吸困难"]}
    }
    result = await red_flag_detector(state)
    assert result["triage_level"] == "EMERGENCY"
```

**Integration Test** (`tests/integration/test_evidence_flow.py`):
```python
@pytest.mark.asyncio
async def test_evidence_retrieval_skips_for_emergency():
    """Verify EMERGENCY cases skip NCBI per spec."""
    graph = build_graph("redis://localhost")
    state = {
        "symptom_schema": {"symptoms": ["呼吸困难"]},
        "triage_level": "EMERGENCY"
    }
    result = await graph.ainvoke(state)
    assert result.get("evidence") is None  # Should skip
```

### References
- [LangGraph Testing Guide](https://docs.langchain.com/oss/python/langgraph/testing)
- [Pytest Asyncio](https://pytest-asyncio.readthedocs.io/)

---

## Summary of Key Decisions

| Area | Decision | Version/Approach |
|------|----------|------------------|
| **LangGraph** | 1.0.5+ (stable) | `>=1.0.5` |
| **Python** | 3.11+ | Modern type hints |
| **State Schema** | TypedDict | Native LangGraph |
| **Nodes** | Async | 40-60% faster I/O |
| **File Structure** | Modular | 18 nodes in separate files |
| **Checkpointing** | Redis | 60-minute TTL |
| **Deployment** | LangServe CLI | Docker + Uvicorn |
| **Models** | Qwen via OpenAI API | Different temps for tasks |
| **Retries** | Max 2 attempts | Exponential backoff |
| **Safety** | Dual verification | Rules + LLM |
| **Testing** | Three-level | Unit/Integration/E2E |

---

## Next Steps

1. ✅ Research complete - all technical decisions documented
2. → Generate data models (`data-model.md`)
3. → Generate API contracts (`contracts/openapi.yaml`, `contracts/state-schema.yaml`)
4. → Generate quickstart guide (`quickstart.md`)
5. → Update agent context (`update-agent-context.sh`)
