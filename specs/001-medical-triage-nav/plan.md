# Implementation Plan: Medical Triage and Hospital Navigation Assistant (TriNav)

**Branch**: `001-medical-triage-nav` | **Date**: 2025-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-medical-triage-nav/spec.md`
**Tech Stack**: LangChain + LangServe + Python 3.11+

## Summary

TriNav is a medical triage and hospital navigation assistant that helps users understand symptom urgency and navigate to appropriate care. The system processes text and optional image inputs, provides triage assessments (EMERGENCY/URGENT/ROUTINE/SELF_CARE), recommends medical departments, and offers hospital navigation with route planning.

**Technical Approach**: Build a LangChain-based workflow with 18 orchestrated nodes using LangGraph for state management, LangServe for deployment, Redis for session caching, and integrate external services (Amap, Weather, NCBI) with graceful degradation. All outputs are verified by dual safety checks (rule-based + LLM reasoning verifier) to enforce medical safety boundaries.

## Technical Context

**Language/Version**: Python 3.11+ (LangChain requires 3.9+, choosing 3.11 for performance and library compatibility)
**Primary Dependencies**:
- **langchain>=0.1.0** - Core framework for chain/workflow orchestration
- **langchain-core>=0.1.0** - Base abstractions for LangChain
- **langchain-openai>=0.0.5** or **langchain-community>=0.0.20** - LLM integrations (Qwen models via OpenAI-compatible API)
- **langgraph>=1.0.5** - Stateful workflow orchestration for 18-node triage pipeline
- **langserve>=0.0.40** - Deployment server for LangChain chains
- **redis>=5.0.0** - Session state management (60min TTL)
- **httpx>=0.25.0** - Async HTTP client for external API calls
- **pydantic>=2.0.0** - Data validation and JSON schema enforcement
- **python-multipart>=0.0.6** - Image upload handling
- **uvicorn[standard]>=0.24.0** - ASGI server for LangServe
- **opentelemetry-api>=1.21.0** - Distributed tracing
- **opentelemetry-sdk>=1.21.0** - Tracing SDK
- **prometheus-client>=0.19.0** - Metrics collection

**Storage**:
- **Redis** (cloud-hosted or self-managed) - Session state (60min TTL) and short-lived caching of external API results/LLM outputs; no persistent images/full text
- **No database** - Stateless architecture with ephemeral Redis storage only (privacy by design)

**Testing**:
- **pytest>=7.4.0** - Test framework
- **pytest-asyncio>=0.21.0** - Async test support
- **pytest-mock>=3.11.0** - Mocking utilities
- **httpx>=0.25.0** - External service mocking
- **pydantic>=2.0.0** - Schema validation testing

**Target Platform**: Linux server (containerized deployment with Docker)
**Project Type**: Backend API service (LangServe deployed, consumed by frontend)
**Performance Goals**:
- EMERGENCY triage: 5 seconds p95 (NCBI skipped)
- ROUTINE triage: 15 seconds p95
- 100 concurrent users baseline
- 99.5% uptime monthly

**Constraints**:
- TLS 1.3 only (HTTPS enforced)
- Session TTL: 60 minutes
- Max clarification rounds: 2
- Max questions per turn: 3
- No persistent storage of raw images/text
- External API versions pinned (x.y.z)

**Scale/Scope**:
- MVP: 100 concurrent users
- 18-node LangGraph workflow
- 3 external integrations (Amap, Weather, NCBI)
- 7 data entities
- 68 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Safety First

**Status**: PENDING

- **Requirement**: Red flag detection triggers highest priority (FR-017)
- **Requirement**: Rule engine overrides LLM when conflicted (edge case #10)
- **Requirement**: Dual verification implemented (FR-024: rule-based + LLM verifier)
- **Requirement**: No delay-care language in outputs (FR-025, CT-001 to CT-005)

**Implementation Strategy**:
- Red flag rules evaluated BEFORE LLM triage (node: `RedFlagDetector`)
- Rule engine results passed as context to LLM with "DO NOT OVERRIDE" instruction
- ReasoningVerifier node validates all outputs for prohibited language
- Post-processing ensures red flag triggers always result in EMERGENCY triage

### Principle II: Clear Boundaries

**Status**: PENDING

- **Requirement**: No diagnosis terminology (FR-020: "疑似"/"可能" qualifiers)
- **Requirement**: No prescription guidance (FR-021: non-prescriptive tips only)
- **Requirement**: Disclaimer in every response (FR-027)
- **Requirement**: Evidence for education only, not treatment (FR-028 to FR-032, entity: Evidence)

**Implementation Strategy**:
- Clinical Extraction node uses "suspected/possible" vocabulary constraints
- Response Composer node enforces disclaimer template
- Evidence Retrieval Router skips for EMERGENCY (prevents delay)
- Post-processing strips any absolute diagnostic language

### Principle III: Prompt Medical Attention

**Status**: PENDING

- **Requirement**: EMERGENCY skips NCBI (FR-029, CT-015)
- **Requirement**: All levels recommend medical care (no "no need to see doctor" - CT-003)
- **Requirement**: Hotline tip in every response (FR-044)

**Implementation Strategy**:
- EvidenceRouter node checks triage level, bypasses NCBI for EMERGENCY
- ResponseComposer ensures all outputs include "建议就近选择综合医院（三甲优先）" or more specific guidance
- Fallback for no GPS: general medical guidance instead of specific hospitals

### Principle IV: Data Minimization

**Status**: PENDING

- **Requirement**: No raw images in Redis (FR-007, CT-007)
- **Requirement**: No full text storage (FR-007, CT-008)
- **Requirement**: 60min TTL (FR-006, FR-009, CT-006)
- **Requirement**: Only structured symptom data stored (Session State entity)

**Implementation Strategy**:
- VisionExtract node extracts features, stores ONLY structured visual_findings object
- ClinicalExtractor extracts schema, stores ONLY symptom_schema object
- Redis schema: `{ session_id, turn_count, symptom_schema, clarify_questions, triage_level, case_domain, evidence_cache_key, navigation_cache_key }`
- NO fields for: raw_text, raw_image_base64, precise_gps_long_term

### Principle V: Fallback Protection and Traceability

**Status**: PENDING

- **Requirement**: External service failures don't crash system (FR-038, FR-046, FR-048)
- **Requirement**: JSON parsing retry max 2 times (FR-049)
- **Requirement**: General guidance when no GPS (FR-039)
- **Requirement**: Hotline fallback in every response (FR-044)
- **Requirement**: Explain triage reasoning (FR-045)
- **Requirement**: Explain hospital ranking (FR-046)
- **Requirement**: Versioned red flag rules (FR-065, entity: RedFlagRule)
- **Requirement**: Log decision points (FR-066: audit logs, 30-day retention)
- **Requirement**: Distributed tracing (FR-061, FR-062: correlation IDs)

**Implementation Strategy**:
- Try-except wrappers around all external API calls with `except Exception` blocks
- Default responses for Amap failure: "建议就近选择综合医院（三甲优先）"
- Default responses for Weather failure: omit weather section (not critical)
- Default responses for NCBI failure: omit evidence section
- ResponseComposer degrades gracefully if any component fails
- TriageReasonGenerator node creates "建议急诊是因为：{reason}"
- HospitalRankingExplainer node creates "三甲综合医院，距离较近，急诊/门诊齐全"
- RedFlagRule entity includes `version` field, loaded from versioned YAML/JSON
- INFO-level logging at all decision points with correlation_id
- OpenTelemetry tracing with trace propagation

### Gate Evaluation

**Result**: PENDING (constitution requires validation)

Pending re-validation against the constitution.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-medical-triage-nav/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── openapi.yaml     # OpenAPI 3.1 spec for /assistant/invoke endpoint
│   └── state-schema.yaml # LangGraph state transition schema
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# LangChain Backend Service
src/
├── chains/
│   ├── __init__.py
│   ├── triage_chain.py      # Main LangChain chain definition
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── input_validator.py       # Node 1: Validate input format
│   │   ├── session_loader.py        # Node 2: Load session from Redis
│   │   ├── image_quality_gate.py    # Node 3: Image quality gate
│   │   ├── vision_extract.py        # Node 4: Visual feature extraction
│   │   ├── clinical_extractor.py    # Node 5: Extract symptom schema
│   │   ├── red_flag_detector.py     # Node 6: Rule-based emergency detection
│   │   ├── triage_classifier.py     # Node 7: LLM triage level assignment
│   │   ├── triage_merger.py         # Node 8: Merge rule + LLM triage (rule wins)
│   │   ├── clarification_generator.py # Node 9: Generate questions if needed
│   │   ├── session_saver.py         # Node 10: Save session to Redis
│   │   ├── evidence_router.py       # Node 11: Decide NCBI retrieval
│   │   ├── ncbi_query_builder.py    # Node 12: Build NCBI query
│   │   ├── ncbi_retriever_tool.py   # Node 13: Retrieve and rank evidence
│   │   ├── domain_classifier.py     # Node 14: Classify specialty domain
│   │   ├── navigator.py             # Node 15: Hospital search + route planning
│   │   ├── weather_fetcher.py       # Node 16: Weather alerts
│   │   ├── reasoning_verifier.py    # Node 17: Safety verification (dual check)
│   │   ├── response_composer.py     # Helper for response formatting
│   │   └── final_status_router.py    # Node 18: Route to final/need_more_info/error
│   └── graph/
│       ├── __init__.py
│       └── triage_graph.py          # LangGraph StateGraph definition
├── models/
│   ├── __init__.py
│   ├── session.py                  # Session State entity (Redis schema)
│   ├── symptom_schema.py           # Symptom Schema entity
│   ├── triage_assessment.py        # Triage Assessment entity
│   ├── evidence.py                 # Evidence (Literature) entity
│   ├── navigation_result.py        # Navigation Result entity
│   ├── weather_alert.py            # Weather Alert entity
│   └── red_flag_rule.py            # Red Flag Rule entity
├── services/
│   ├── __init__.py
│   ├── redis_service.py            # Redis session management
│   ├── llm_service.py              # Qwen model API wrapper
│   ├── amap_service.py             # Amap API integration
│   ├── weather_service.py          # Weather API integration
│   ├── ncbi_service.py             # NCBI/PubMed API integration
│   └── hospital_grade_mapping.py   # Local 3A hospital mapping
├── utils/
│   ├── __init__.py
│   ├── logging_config.py           # Structured logging + correlation IDs
│   ├── telemetry.py                # OpenTelemetry tracing setup
│   ├── metrics.py                  # Prometheus metrics export
│   └── safety_filters.py           # Prohibited content detection patterns
├── config/
│   ├── __init__.py
│   ├── settings.py                 # Environment-based configuration
│   ├── red_flag_rules.yaml         # Versioned red flag rules
│   └── api_versions.yaml           # Pinned external API versions
└── server.py                       # LangServe entry point

tests/
├── contract/
│   ├── __init__.py
│   ├── test_api_contract.py        # OpenAPI contract tests
│   └── test_state_transitions.py   # LangGraph state transition tests
├── integration/
│   ├── __init__.py
│   ├── test_full_workflow.py       # End-to-end triage workflow
│   ├── test_external_services.py   # Amap/Weather/NCBI integration
│   └── test_session_management.py  # Redis session lifecycle
├── unit/
    ├── __init__.py
    ├── test_nodes/
    │   ├── test_input_validator.py
    │   ├── test_clinical_extractor.py
    │   ├── test_red_flag_detector.py
    │   ├── test_evidence_router.py
    │   └── test_reasoning_verifier.py
    ├── test_services/
    │   ├── test_redis_service.py
    │   ├── test_amap_service.py
    │   └── test_ncbi_service.py
    └── test_models/
        ├── test_session.py
        └── test_triage_assessment.py
└── load/
    ├── __init__.py
    └── test_concurrent_users.py

# Deployment
Dockerfile                      # Container image for LangServe
docker-compose.yml              # Local development (app + redis)
requirements.txt                # Python dependencies
requirements-dev.txt            # Development dependencies
langchain.json                  # LangServe CLI configuration
.env.example                    # Environment variables template

# Observability
prometheus.yml                  # Prometheus scrape config
grafana/dashboards/             # Grafana dashboard JSONs
└── tri-metrics.json

# Documentation
docs/
├── ARCHITECTURE.md              # System architecture overview
├── WORKFLOW.md                  # 18-node workflow explanation
├── SAFETY.md                    # Safety measures and compliance
└── DEPLOYMENT.md                # LangServe CLI deployment guide
```

**Structure Decision**: Backend-only API service following LangChain best practices. Frontend is a separate concern (assumed to exist based on spec assumptions AS-001, AS-002). Source organized into:
- `chains/`: LangChain workflow logic (18 nodes + StateGraph)
- `models/`: Pydantic data models for entities
- `services/`: External API integrations and Redis
- `utils/`: Cross-cutting concerns (logging, telemetry, safety)
- `config/`: Configuration and versioned rules
- `tests/`: Unit/integration/contract + performance/load testing (SLA & concurrency)

## Complexity Tracking

> **Pending** - Constitution check not yet re-validated; no violations documented.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Phase 0: Research

### Research Topics

1. **LangGraph StateGraph Best Practices**
   - How to structure 18-node workflow without creating unmaintainable complexity
   - State schema design for multi-turn conversations
   - Conditional routing patterns for triage logic

2. **LangServe Deployment Patterns**
   - LangChain CLI deployment workflow
   - Container configuration for production
   - Environment variable management for API keys

3. **Redis Session Management**
   - Best practices for ephemeral session storage (60min TTL)
   - Serialization strategies for complex nested objects
   - Connection pooling for concurrent requests

4. **Qwen Model Integration**
   - OpenAI-compatible API endpoints for Qwen
   - Token limits and context window management
   - Vision model (Qwen-VL) integration patterns

5. **External API Resilience Patterns**
   - Retry policies with exponential backoff
   - Circuit breaker patterns for external services
   - Timeout configuration strategies

6. **Safety Verification Architecture**
   - Rule-based red flag detection implementation
   - LLM-based reasoning verifier design
   - Conflict resolution (rule overrides LLM)

### Research Deliverables

**File**: `specs/001-medical-triage-nav/research.md`

For each topic:
- **Decision**: Chosen approach with specific library versions
- **Rationale**: Why this approach fits TriNav's requirements
- **Alternatives Considered**: What else was evaluated and rejected
- **References**: Links to documentation, best practices, examples

---

## Phase 1: Design & Contracts

### Data Model

**File**: `specs/001-medical-triage-nav/data-model.md`

Extract 7 entities from spec:
1. **Session State** (Redis schema)
2. **Symptom Schema** (Clinical extraction output)
3. **Triage Assessment** (Triage decision)
4. **Evidence** (Literature references)
5. **Navigation Result** (Hospitals + routes)
6. **Weather Alert** (Weather tips)
7. **Red Flag Rule** (Emergency detection rules)

For each entity:
- Pydantic model definition (Python type hints)
- Validation rules (from FRs)
- JSON Schema representation
- Redis serialization strategy
- Lifecycle/state transitions

### API Contracts

**Directory**: `specs/001-medical-triage-nav/contracts/`

1. **OpenAPI Specification** (`openapi.yaml`)
   - POST `/assistant/invoke` endpoint (LangServe standard)
   - Request schema: `{ text, image_base64?, gps_coordinates?, session_id? }`
   - Response schema: `{ status, triage_level, departments, causes, tips, red_flags, navigation?, disclaimer, hotline_tip, error? }`
   - Error responses: 400, 500, 503 (external service degraded)

2. **State Schema** (`state-schema.yaml`)
   - LangGraph StateGraph state definition
   - 18 nodes with input/output schemas
   - Conditional edge definitions
   - Transition validation rules

### Quickstart Guide

**File**: `specs/001-medical-triage-nav/quickstart.md`

Developer onboarding:
- Prerequisites (Python 3.11+, Redis, Qwen API access)
- Local development setup (docker-compose up)
- Running tests (pytest)
- LangServe local deployment (langchain serve)
- Making first API call (curl example)
- Debugging workflow (LangSmith integration)

### Agent Context Update

```bash
.specify/scripts/bash/update-agent-context.sh claude
```

Update `.claude/CLAUDE.md` with:
- LangChain and LangServe basics
- LangGraph StateGraph patterns
- Redis session management
- Qwen model API integration
- External service resilience patterns

---

## Phase 2: Implementation Planning

**Output**: `specs/001-medical-triage-nav/tasks.md` (created by `/speckit.tasks` command)

Task breakdown by user story (US1-US3; US4 clarification in Phase 3; evidence retrieval optional):
- **Phase 1**: Setup (project structure, dependencies, linting)
- **Phase 2**: Foundational (models, services, config)
- **Phase 3-5**: User Story implementation (US1-US3)
- **Phase 6**: Evidence retrieval (optional enhancement)
- **Phase 7**: Polish & cross-cutting (testing, docs, monitoring)

---

## Next Steps

1. Constitution Check: **PENDING**
2. → Phase 0: Execute research tasks (generate `research.md`)
3. → Phase 1: Generate data model and contracts (generate `data-model.md`, `contracts/`, `quickstart.md`)
4. → Phase 1: Update agent context (run `update-agent-context.sh`)
5. ⏹️ Report completion and stop (Phase 2 is separate `/speckit.tasks` command)
