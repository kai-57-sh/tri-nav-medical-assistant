# Implementation Tasks: Medical Triage and Hospital Navigation Assistant (TriNav)

**Feature Branch**: `001-medical-triage-nav`
**Date**: 2025-01-09
**Tech Stack**: LangChain + LangGraph + LangServe + Python 3.11+
**Total Phases**: 7
**Total Tasks**: 121

---

## Task Legend

- **Task ID**: Unique identifier (e.g., T001)
- **Priority**: P0 (blocking), P1 (high), P2 (medium), P3 (low)
- **Story**: User Story reference (US1-US4) or "Foundation" for cross-cutting
- **Dependencies**: Tasks that must complete before this task can start
- **Estimated Complexity**: Small (S), Medium (M), Large (L), Extra Large (XL)

---

## Phase 1: Project Setup (Foundation)

**Goal**: Initialize project structure, dependencies, and development environment

**Deliverables**: Working development environment with all tools configured

### 1.1 Project Structure

- [X] [T001] [P0] [Foundation] Create root project directory structure with src/, tests/, docs/ folders (S)
  - File: `src/`, `tests/`, `docs/`, `specs/`
  - Create all subdirectories per plan.md
  - Initialize git repository with .gitignore (Python, IDE, secrets)

- [X] [T002] [P0] [Foundation] Create src/chains/ subdirectories for 18 nodes (S)
  - File: `src/chains/nodes/`, `src/chains/graph/`
  - Create placeholder __init__.py files
  - Structure: 18 node files, graph builder file

- [X] [T003] [P0] [Foundation] Create src/models/, src/services/, src/utils/, src/config/ directories (S)
  - File: `src/models/`, `src/services/`, `src/utils/`, `src/config/`
  - Create placeholder __init__.py files
  - Prepare for 7 Pydantic models

- [X] [T004] [P0] [Foundation] Create tests/ subdirectories for three-tier testing (S)
  - File: `tests/unit/`, `tests/integration/`, `tests/contract/`
  - Create placeholder __init__.py files
  - Structure: test_nodes/, test_services/, test_models/

### 1.2 Dependencies

- [X] [T005] [P0] [Foundation] Create requirements.txt with production dependencies (M)
  - File: `requirements.txt`
  - Dependencies: langchain>=0.1.0, langchain-core>=0.1.0, langchain-openai>=0.0.5, langgraph>=1.0.5, langserve>=0.0.40, redis>=5.0.0, pydantic>=2.0.0, httpx>=0.25.0, uvicorn[standard]>=0.24.0, opentelemetry-api>=1.21.0, opentelemetry-sdk>=1.21.0, prometheus-client>=0.19.0
  - Reference: plan.md Section "Primary Dependencies"

- [X] [T006] [P0] [Foundation] Create requirements-dev.txt with development dependencies (S)
  - File: `requirements-dev.txt`
  - Dependencies: pytest>=7.4.0, pytest-asyncio>=0.21.0, pytest-mock>=3.11.0, black>=23.0.0, ruff>=0.1.0, mypy>=1.0.0, ipython>=8.0.0, jupyter>=1.0.0

- [X] [T007] [P1] [Foundation] Create .env.example with all environment variables (M)
  - File: `.env.example`
  - Variables: QWEN_BASE_URL, QWEN_API_KEY, REDIS_URL, AMAP_API_KEY, WEATHER_API_URL, WEATHER_API_KEY, NCBI_BASE_URL, LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, OTEL_EXPORTER_OTLP_ENDPOINT
  - Reference: quickstart.md Section 3

### 1.3 Development Tools

- [X] [T008] [P1] [Foundation] Configure Black code formatter (S)
  - File: `pyproject.toml`
  - Settings: line-length=100, target-version=py311
  - Create pre-commit hook for auto-formatting

- [X] [T009] [P1] [Foundation] Configure Ruff linter (S)
  - File: `pyproject.toml`
  - Enable: all rules, target Python 3.11
  - Ignore: tests/ for certain rules (test-specific patterns)

- [X] [T010] [P2] [Foundation] Configure mypy type checker (M)
  - File: `pyproject.toml`
  - Settings: strict mode, warn_return_any, warn_unused_configs
  - Add type stubs for third-party packages

- [X] [T011] [P2] [Foundation] Create pytest.ini with test configuration (S)
  - File: `pytest.ini`
  - Settings: asyncio_mode=auto, testpaths=tests, python_files=test_*.py
  - Add markers: unit, integration, contract

### 1.4 Docker & Deployment

- [ ] [T012] [P1] [Foundation] Create Dockerfile for LangServe deployment (M)
  - File: `Dockerfile`
  - Base: python:3.11-slim
  - Expose port 8000
  - Health check endpoint
  - Non-root user for security

- [ ] [T013] [P1] [Foundation] Create docker-compose.yml for local development (M)
  - File: `docker-compose.yml`
  - Services: app (LangServe), redis (session storage)
  - Networks: isolated network for services
  - Volumes: mount source code for hot reload

- [ ] [T014] [P2] [Foundation] Create langchain.json for LangServe CLI (S)
  - File: `langchain.json`
  - Configure chain path: src.chains.triage_chain:chain
  - Set environment variables

---

## Phase 2: Foundational Models & Services (Foundation)

**Goal**: Implement core data models, configuration, and services that all user stories depend on

**Deliverables**: 7 Pydantic entities, 5 services, configuration system

### 2.1 Configuration System

- [ ] [T015] [P0] [Foundation] Create settings.py with environment-based configuration (M)
  - File: `src/config/settings.py`
  - Use pydantic-settings for env var loading
  - Validate API keys on startup
  - Configure: Qwen models, Redis, external API endpoints, timeout values
  - Reference: plan.md Section "Primary Dependencies"

- [ ] [T016] [P1] [Foundation] Create api_versions.yaml with pinned external API versions (S)
  - File: `src/config/api_versions.yaml`
  - Pin Amap API to v3.x.x specific version
  - Pin Weather API to specific version
  - Pin NCBI E-utilities to specific version
  - Add version update procedure in comments

- [ ] [T017] [P1] [Foundation] Create red_flag_rules.yaml with versioned rules (M)
  - File: `src/config/red_flag_rules.yaml`
  - Define 10-15 red flag rules (breathing difficulty, chest pain, severe bleeding, etc.)
  - Each rule: id, priority, version, conditions, triage_level, user_message, department
  - Reference: spec.md Section "Red Flag Rule" entity

### 2.2 Pydantic Data Models

- [ ] [T018] [P0] [Foundation] Create session.py model for Redis schema (M)
  - File: `src/models/session.py`
  - Fields: session_id, turn_count (1-2), symptom_schema, clarify_questions, triage_level, case_domain, evidence_cache_key, navigation_cache_key
  - Validation: turn_count max 2, triage_level enum
  - Reference: data-model.md Section "Session State"

- [ ] [T019] [P0] [Foundation] Create symptom_schema.py model (M)
  - File: `src/models/symptom_schema.py`
  - Fields: body_part, symptoms, duration, severity, accompanying_symptoms, onset, visual_findings (optional)
  - Validation: required fields for clinical extraction
  - Reference: data-model.md Section "Symptom Schema"

- [ ] [T020] [P0] [Foundation] Create triage_assessment.py model (M)
  - File: `src/models/triage_assessment.py`
  - Fields: triage_level, recommended_departments, possible_causes (max 3), triage_reason, self_care_tips, red_flags, red_flags_hit
  - Validation: possible_causes must use qualified language ("疑似"/"可能")
  - Reference: data-model.md Section "Triage Assessment"

- [ ] [T021] [P1] [US2] Create visual_findings.py model for image extraction (S)
  - File: `src/models/visual_findings.py`
  - Fields: type (rash/wound/unknown), summary, features (list), confidence (0.0-1.0)
  - Validation: confidence range, type enum
  - Reference: data-model.md Section "Symptom Schema" visual_findings

- [ ] [T022] [P1] [Foundation] Create evidence.py model for literature references (S)
  - File: `src/models/evidence.py`
  - Fields: pmid, title, year, source, type, note (optional)
  - Validation: year format, PMID format
  - Reference: data-model.md Section "Evidence (Literature)"

- [ ] [T023] [P1] [US3] Create navigation_result.py model (M)
  - File: `src/models/navigation_result.py`
  - Fields: radius_km, hospitals (exactly 3), route_plan
  - Validation: hospitals must have exactly 3 items
  - Reference: data-model.md Section "Navigation Result"

- [ ] [T024] [P2] [US3] Create weather_alert.py model (S)
  - File: `src/models/weather_alert.py`
  - Fields: summary, tips (list)
  - Reference: data-model.md Section "Weather Alert"

- [ ] [T025] [P0] [Foundation] Create red_flag_rule.py model for rule loading (M)
  - File: `src/models/red_flag_rule.py`
  - Fields: id, priority, conditions (list), triage_level, user_message, department, version
  - Method: evaluate(symptom_schema) -> bool
  - Reference: data-model.md Section "Red Flag Rule"

### 2.3 Service Layer

- [ ] [T026] [P0] [Foundation] Create redis_service.py for session management (L)
  - File: `src/services/redis_service.py`
  - Class: RedisService
  - Methods: save_session(session_id, state), load_session(session_id), delete_session(session_id)
  - TTL: 60 minutes
  - Error handling: treat failures as new session (graceful degradation)
  - Reference: plan.md Section "Storage"

- [ ] [T027] [P0] [Foundation] Create llm_service.py for Qwen model integration (L)
  - File: `src/services/llm_service.py`
  - Class: LLMService
  - Methods: chat_completion(messages, temperature=0.3), vision_completion(image_base64, text, temperature=0.1)
  - Support: Qwen text model, Qwen-VL vision model, Qwen reasoning model
  - Error handling: retry up to 2 times, then degrade gracefully
  - Reference: research.md Section "Qwen Model Integration"

- [ ] [T028] [P1] [US3] Create amap_service.py for hospital navigation (L)
  - File: `src/services/amap_service.py`
  - Class: AmapService
  - Methods: search_hospitals(lat, lng, radius_km=10), get_route(origin_lat, origin_lng, dest_lat, dest_lng)
  - Ranking: prioritize 3A hospitals, then by distance
  - Error handling: return empty hospitals list on failure (graceful degradation)
  - Reference: spec.md FR-033 to FR-036

- [ ] [T029] [P2] [US3] Create weather_service.py for weather alerts (M)
  - File: `src/services/weather_service.py`
  - Class: WeatherService
  - Methods: get_weather(lat, lng)
  - Output: summary + relevant tips (umbrella, warm clothing, etc.)
  - Error handling: return None on failure (not critical path)
  - Reference: spec.md FR-037

- [ ] [T030] [P1] [Foundation] Create ncbi_service.py for PubMed/NCBI (L)
  - File: `src/services/ncbi_service.py`
  - Class: NCBIService
  - Methods: search_pubmed(query, max_results=20), fetch_article_details(pmid_list)
  - Filters: last 10 years, preference for guidelines/reviews
  - Error handling: return empty list on failure (graceful degradation)
  - Reference: spec.md FR-030 to FR-032

- [ ] [T113] [P1] [Foundation] Implement Redis caching for external service results and LLM extraction with TTLs (M)
  - Files: `src/services/redis_service.py`, `src/services/*`
  - Cache: external API responses (Amap/Weather/NCBI) and LLM extraction results
  - TTL: short-lived, configurable per service
  - Tests: `tests/unit/test_services/test_cache.py`
  - Reference: spec.md FR-056

- [ ] [T031] [P2] [US3] Create hospital_grade_mapping.py local data (S)
  - File: `src/services/hospital_grade_mapping.py`
  - Dictionary: hospital_name -> is_3a boolean
  - Fallback for when Amap API doesn't return stable 3A field
  - Reference: spec.md CT-018

### 2.4 Utility Functions

- [ ] [T032] [P1] [Foundation] Create logging_config.py with structured logging (M)
  - File: `src/utils/logging_config.py`
  - Configure: INFO level for operational events, ERROR for failures, WARN for degraded scenarios
  - Include: correlation_id in all log entries
  - Output: JSON format for parsing
  - Reference: spec.md FR-057 to FR-059

- [ ] [T033] [P2] [Foundation] Create telemetry.py for OpenTelemetry tracing (M)
  - File: `src/utils/telemetry.py`
  - Initialize: OpenTelemetry tracer provider
  - Propagate: trace correlation IDs across service calls
  - Export: OTLP format (Jaeger-compatible)
  - Reference: spec.md FR-061, FR-062

- [ ] [T034] [P2] [Foundation] Create metrics.py for Prometheus metrics (M)
  - File: `src/utils/metrics.py`
  - Metrics: response time (p50/p95/p99), error rate, request rate, queue depth, external service health
  - Endpoint: /metrics for Prometheus scraping
  - Reference: spec.md FR-060

- [ ] [T035] [P1] [Foundation] Create safety_filters.py for prohibited content (M)
  - File: `src/utils/safety_filters.py`
  - Patterns: diagnosis terms, prescription phrases, delay-care language
  - Functions: contains_diagnosis(text), contains_prescription(text), contains_delay_care(text)
  - Reference: spec.md FR-025, CT-001 to CT-005

---

## Phase 3: User Story 1 - Symptom Triage with Text Input (P1)

**Goal**: Core MVP - text-only triage with no images or GPS

**Deliverables**: Working end-to-end triage for text input

**Acceptance**: User submits "手臂出现红疹，有点痒，持续2天" → receives ROUTINE triage with departments, causes (qualified), tips, red flags, disclaimer

### 3.1 LangGraph Nodes (Input & Session)

- [ ] [T036] [P0] [US1] Create input_validator.py node (Node 1) (M)
  - File: `src/chains/nodes/input_validator.py`
  - Function: input_validator(state)
  - Validate: text max 2000 chars, lat/lng ranges, session_id format (UUID)
  - Generate: new UUID if session_id not provided
  - Reference: spec.md FR-001 to FR-005

- [ ] [T037] [P0] [US1] Create session_loader.py node (Node 2) (M)
  - File: `src/chains/nodes/session_loader.py`
  - Function: session_load(state)
  - Load: session from Redis using session_id
  - Initialize: new session if not found (turn_count=1)
  - Error handling: treat Redis failure as new session
  - Reference: spec.md FR-006 to FR-009

### 3.2 LangGraph Nodes (Clinical Triage)

- [ ] [T038] [P0] [US1] Create clinical_extractor.py node (Node 5) (M)
  - File: `src/chains/nodes/clinical_extractor.py`
  - Function: clinical_extractor(state)
  - Input: text, visual_findings (optional)
  - Output: symptom_schema (structured extraction)
  - Use: LLM with temperature=0.1 for consistent extraction
  - Reference: spec.md FR-015, FR-020, FR-021

- [ ] [T039] [P0] [US1] Create red_flag_detector.py node (Node 6) (L)
  - File: `src/chains/nodes/red_flag_detector.py`
  - Function: red_flag_detector(state)
  - Input: symptom_schema
  - Logic: evaluate all red flag rules from config/red_flag_rules.yaml
  - Output: red_flags_hit (list of rule IDs), rule_triage_level, recommended_departments
  - Rule engine takes precedence over LLM (constitution Principle I)
  - Reference: spec.md FR-017

- [ ] [T040] [P0] [US1] Create triage_classifier.py node (Node 7) (M)
  - File: `src/chains/nodes/triage_classifier.py`
  - Function: triage_classifier(state)
  - Input: symptom_schema
  - Output: llm_triage_level (EMERGENCY/URGENT/ROUTINE/SELF_CARE)
  - Use: LLM with temperature=0.3 for nuanced classification
  - Prompt engineering: conservative bias, avoid under-triaging
  - Reference: spec.md FR-018

- [ ] [T041] [P0] [US1] Create triage_merger.py node (Node 8) (M)
  - File: `src/chains/nodes/triage_merger.py`
  - Function: triage_merger(state)
  - Input: rule_triage_level, llm_triage_level
  - Logic: RULE WINS (more conservative)
  - Output: triage_level (final), triage_reason, triage_source ("rule" or "llm" or "merged")
  - Reference: spec.md edge case #10, state-schema.yaml Node 8

- [ ] [T042] [P0] [US1] Create clarification_generator.py node (Node 9) (M)
  - File: `src/chains/nodes/clarification_generator.py`
  - Function: clarification_generator(state)
  - Input: symptom_schema, turn_count, triage_level
  - Logic: determine if clarification needed (insufficient information)
  - Output: clarify_questions (max 3), need_clarify (bool)
  - Stop: if turn_count >= 2, force final triage
  - Reference: spec.md FR-016, CT-009

### 3.3 LangGraph Nodes (Session Persistence)

- [ ] [T043] [P0] [US1] Create session_saver.py node (Node 10) (M)
  - File: `src/chains/nodes/session_saver.py`
  - Function: session_save(state)
  - Input: all session state fields
  - Logic: save minimal state to Redis (no raw text/images)
  - TTL: 60 minutes
  - Reference: spec.md FR-007, CT-007, CT-008

### 3.4 LangGraph Nodes (Safety Verification)

- [ ] [T044] [P0] [US1] Create reasoning_verifier.py node (Node 17) (L)
  - File: `src/chains/nodes/reasoning_verifier.py`
  - Function: reasoning_verifier(state)
  - Dual check: rule-based (safety_filters.py) + LLM reasoning verification
  - Detect: diagnosis terms, prescription language, delay-care phrases
  - Output: sanitized_final_response, status (final/need_more_info/error)
  - Rewrite: remove or flag non-compliant content
  - Reference: spec.md FR-024 to FR-027

- [ ] [T045] [P0] [US1] Create response_composer.py helper for response formatting (M)
  - File: `src/chains/nodes/response_composer.py`
  - Function: compose_response(state)
  - Used by: reasoning_verifier before final output
  - Sections: triage_level, recommended_departments, possible_causes, self_care_tips, red_flags, disclaimer, hotline_tip
  - Format: colloquial Chinese (口语化)
  - Mandatory: disclaimer + hotline_tip in every response
  - Reference: spec.md FR-042 to FR-046

- [ ] [T046] [P0] [US1] Create final_status_router.py node (Node 18) (S)
  - File: `src/chains/nodes/final_status_router.py`
  - Function: final_status_router(state)
  - Input: status, error_message
  - Logic: route to END based on status
  - Reference: state-schema.yaml Node 18

- [ ] [T118] [P1] [US1] Implement JSON parsing retry policy (max 2) (M)
  - File: `src/services/llm_service.py`
  - Logic: retry parse failures up to 2 times before returning error
  - Tests: `tests/unit/test_services/test_llm_service.py`
  - Reference: spec.md FR-049

- [ ] [T119] [P1] [US1] Standardize user-friendly error responses (M)
  - File: `src/chains/nodes/final_status_router.py`
  - Output: status="error" with friendly message (no stack traces)
  - Tests: `tests/integration/test_error_handling.py`
  - Reference: spec.md FR-050

### 3.5 LangGraph State & Graph Builder

- [ ] [T047] [P0] [US1] Create TriageState TypedDict in graph module (M)
  - File: `src/chains/graph/triage_graph.py`
  - Define: TypedDict with all state fields
  - Add: Annotated fields with reducers (add_messages for conversation history)
  - Reference: state-schema.yaml Section "State Definition"

- [ ] [T048] [P0] [US1] Create build_graph() function with StateGraph (L)
  - File: `src/chains/graph/triage_graph.py`
  - Add: all 18 nodes
  - Add: linear edges (START → InputValidator → ... → FinalStatusRouter → END)
  - Add: conditional edges for clarification routing
  - Compile: with Redis checkpointer
  - Reference: state-schema.yaml Section "State Transitions"

### 3.6 LangServe Integration

- [ ] [T049] [P0] [US1] Create triage_chain.py main chain definition (M)
  - File: `src/chains/triage_chain.py`
  - Export: chain = build_graph(redis_conn_string).compile()
  - Configure: input schema, output schema
  - Reference: plan.md Section "Project Structure"

- [ ] [T050] [P0] [US1] Create server.py LangServe entry point (M)
  - File: `src/server.py`
  - Endpoint: POST /assistant/invoke
  - CORS: allow frontend origin
  - Health check: GET /health
  - Reference: openapi.yaml

### 3.7 Unit Tests (US1)

- [ ] [T051] [P1] [US1] Test input_validator with valid/invalid inputs (M)
  - File: `tests/unit/test_nodes/test_input_validator.py`
  - Cases: valid text, oversized text (>2000 chars), invalid lat/lng, missing session_id
  - Assert: proper validation errors

- [ ] [T052] [P1] [US1] Test clinical_extractor with various symptom descriptions (L)
  - File: `tests/unit/test_nodes/test_clinical_extractor.py`
  - Cases: mild symptoms, emergency symptoms, insufficient information
  - Mock: LLM service responses
  - Assert: structured symptom_schema output

- [ ] [T053] [P0] [US1] Test red_flag_detector with rule triggers (L)
  - File: `tests/unit/test_nodes/test_red_flag_detector.py`
  - Cases: breathing difficulty (EMERGENCY), chest pain (EMERGENCY), mild rash (ROUTINE)
  - Assert: correct triage_level, rule IDs captured

- [ ] [T054] [P1] [US1] Test triage_merger conflict resolution (M)
  - File: `tests/unit/test_nodes/test_triage_merger.py`
  - Cases: rule=EMERGENCY, llm=ROUTINE → EMERGENCY wins
  - Cases: rule=ROUTINE, llm=EMERGENCY → EMERGENCY wins (conservative)
  - Assert: rule always wins when in conflict

- [ ] [T055] [P1] [US1] Test reasoning_verifier safety filters (L)
  - File: `tests/unit/test_nodes/test_reasoning_verifier.py`
  - Cases: diagnosis language ("你得了XX病"), prescription ("服用XX药"), delay care ("不用看医生")
  - Assert: content blocked or rewritten

### 3.8 Integration Tests (US1)

- [ ] [T056] [P0] [US1] Test full workflow: text input → triage assessment (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: "手臂出现红疹，有点痒，持续2天"
  - Mock: external services (NCBI, Amap, Weather)
  - Assert: status=final, triage_level=ROUTINE, departments non-empty, causes qualified, disclaimer present

- [ ] [T057] [P0] [US1] Test emergency workflow with red flag trigger (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: "胸口闷，呼吸困难"
  - Assert: triage_level=EMERGENCY, departments=["急诊"], immediate response (no evidence delay)

- [ ] [T058] [P1] [US1] Test clarification workflow (need_more_info status) (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: "肚子不舒服" (insufficient)
  - Assert: status=need_more_info, clarify_questions max 3, turn_count=1

- [ ] [T059] [P1] [US1] Test session persistence across turns (M)
  - File: `tests/integration/test_session_management.py`
  - Turn 1: insufficient info → clarify
  - Turn 2: provide details → final triage
  - Assert: turn_count increments, session state preserved

---

## Phase 4: User Story 2 - Image Quality Check & Visual Extraction (P2)

**Goal**: Add image upload capability with quality gate and visual feature extraction

**Deliverables**: Working image processing pipeline

**Acceptance**: User uploads clear rash photo → system extracts visual features and integrates with symptom schema

### 4.1 LangGraph Nodes (Image Processing)

- [ ] [T060] [P1] [US2] Create image_quality_gate.py node (Node 3) (L)
  - File: `src/chains/nodes/image_quality_gate.py`
  - Function: image_quality_gate(state)
  - Input: image_base64
  - Logic: check clarity, lighting, focus using Qwen-VL
  - Output: image_is_clear (bool), issues (list if unclear)
  - Conditional: route to clarify_ask if unclear
  - Reference: spec.md FR-010 to FR-014

- [ ] [T061] [P1] [US2] Create vision_extract.py node (Node 4) (L)
  - File: `src/chains/nodes/vision_extract.py`
  - Function: vision_extract(state)
  - Input: image_base64
  - Use: Qwen-VL model with temperature=0.1
  - Output: visual_findings {type, summary, features, confidence}
  - No diagnosis terms in extraction
  - Reference: spec.md FR-011

### 4.2 Integration with Existing Nodes

- [ ] [T062] [P1] [US2] Update clinical_extractor to integrate visual_findings (M)
  - File: `src/chains/nodes/clinical_extractor.py`
  - Modify: incorporate visual_findings into symptom_schema
  - Logic: merge text + visual into unified schema
  - Reference: spec.md FR-013

### 4.3 Unit Tests (US2)

- [ ] [T063] [P1] [US2] Test image_quality_gate with clear/blurry images (M)
  - File: `tests/unit/test_nodes/test_image_quality_gate.py`
  - Cases: clear rash photo, blurry dark photo, no image provided
  - Mock: Qwen-VL responses
  - Assert: correct routing decision

- [ ] [T064] [P1] [US2] Test vision_extract feature extraction (M)
  - File: `tests/unit/test_nodes/test_vision_extract.py`
  - Cases: rash image, wound image, non-medical image
  - Mock: Qwen-VL responses
  - Assert: visual_findings structure correct, confidence in range

### 4.4 Integration Tests (US2)

- [ ] [T065] [P1] [US2] Test full workflow: image + text → enhanced triage (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: clear rash photo + "手臂红疹，有点痒"
  - Assert: visual_findings integrated, triage more accurate

- [ ] [T066] [P1] [US2] Test image quality gate retake flow (M)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: blurry photo → request retake with specific guidance
  - Assert: status=need_more_info, issues list specific, suggestion actionable

- [ ] [T067] [P2] [US2] Test wound image with tetanus risk reminder (M)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: wound photo + "被铁片划伤，出血"
  - Assert: urgent care recommendation, tetanus consultation reminder (non-prescriptive)

---

## Phase 5: User Story 3 - Hospital Navigation with Route Planning (P3)

**Goal**: Add GPS-based hospital search and route planning

**Deliverables**: Working navigation system with Amap integration

**Acceptance**: User provides GPS → system returns exactly 3 hospitals (3A prioritized) + route plan + weather alert

### 5.1 LangGraph Nodes (Navigation)

- [ ] [T068] [P1] [US3] Create navigator.py node (Node 15) (L)
  - File: `src/chains/nodes/navigator.py`
  - Function: navigator(state)
  - Input: lat, lng, triage_level
  - Use: AmapService.search_hospitals(), get_route()
  - Output: hospitals (exactly 3), route_plan
  - Ranking: 3A priority, then distance
  - Error handling: return empty hospitals on failure
  - Reference: spec.md FR-033 to FR-036

- [ ] [T069] [P2] [US3] Create weather_fetcher.py node (Node 16) (M)
  - File: `src/chains/nodes/weather_fetcher.py`
  - Function: weather_fetcher(state)
  - Input: lat, lng, route_plan
  - Use: WeatherService.get_weather()
  - Output: weather_alert {summary, tips}
  - Error handling: return None on failure (not critical)
  - Reference: spec.md FR-037

- [ ] [T070] [P1] [US3] Update response_composer to include navigation section (M)
  - File: `src/chains/nodes/response_composer.py`
  - Add: navigation section if hospitals available
  - Add: general guidance if no GPS or Amap failure
  - Reference: spec.md FR-039

### 5.2 Unit Tests (US3)

- [ ] [T071] [P1] [US3] Test navigator hospital ranking (M)
  - File: `tests/unit/test_nodes/test_navigator.py`
  - Cases: 3A hospitals available, no 3A hospitals, EMERGENCY priority
  - Mock: AmapService responses
  - Assert: exactly 3 hospitals, 3A prioritized, ranking rationale included

- [ ] [T072] [P2] [US3] Test weather_fetcher integration (M)
  - File: `tests/unit/test_nodes/test_weather_fetcher.py`
  - Cases: rainy weather, clear weather, service failure
  - Mock: WeatherService responses
  - Assert: tips relevant (umbrella for rain), graceful degradation

### 5.3 Integration Tests (US3)

- [ ] [T073] [P1] [US3] Test full workflow: GPS provided → navigation output (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: triage + GPS (39.9042, 116.4074)
  - Assert: 3 hospitals, route plan to Rank 1, weather alert included

- [ ] [T074] [P1] [US3] Test GPS denied → general guidance only (M)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: triage without GPS
  - Assert: navigation shows "建议就近选择综合医院（三甲优先）", no specific hospitals

- [ ] [T075] [P1] [US3] Test Amap service failure graceful degradation (M)
  - File: `tests/integration/test_external_services.py`
  - Scenario: Amap timeout/error
  - Assert: status=final, navigation degraded to general guidance, no system crash

---

## Phase 6: Evidence Retrieval (Optional Enhancement)

**Goal**: Add NCBI/PubMed evidence retrieval for non-emergency cases

**Deliverables**: Working evidence retrieval with ranking

**Acceptance**: ROUTINE triage → system retrieves 5-8 relevant PubMed articles with summaries

### 6.1 LangGraph Nodes (Evidence)

- [ ] [T076] [P1] [Foundation] Create evidence_router.py node (Node 11) (M)
  - File: `src/chains/nodes/evidence_router.py`
  - Function: evidence_router(state)
  - Input: triage_level, case_domain, extraction_confidence
  - Logic: skip evidence if EMERGENCY or extraction_confidence < 0.6; otherwise decide based on domain
  - Output: evidence_needed (bool)
  - Conditional: route to Navigator if EMERGENCY or not needed
  - Reference: spec.md FR-028, FR-029

- [ ] [T077] [P1] [Foundation] Create ncbi_query_builder.py node (Node 12) (M)
  - File: `src/chains/nodes/ncbi_query_builder.py`
  - Function: ncbi_query_builder(state)
  - Input: symptom_schema, case_domain
  - Output: ncbi_query (search string)
  - Filters: last 10 years, guideline/review preference
  - Reference: spec.md FR-030

- [ ] [T078] [P1] [Foundation] Create ncbi_retriever_tool.py node (Node 13) (L)
  - File: `src/chains/nodes/ncbi_retriever_tool.py`
  - Function: ncbi_retriever_tool(state)
  - Input: ncbi_query
  - Use: NCBIService.search_pubmed(), fetch_article_details()
  - Output: candidate_evidence (list), evidence_selected (5-8 ranked)
  - Ranking: relevance score, recency, article type
  - Error handling: return empty list on failure
  - Reference: spec.md FR-031, FR-032

- [ ] [T079] [P2] [Foundation] Create domain_classifier.py node (Node 14) (M)
  - File: `src/chains/nodes/domain_classifier.py`
  - Function: domain_classifier(state)
  - Input: symptom_schema
  - Output: case_domain (dermatology/trauma/respiratory/gastro/neuro/urology/other)
  - Use: LLM with temperature=0.1 for consistent classification
  - Reference: spec.md FR-023

- [ ] [T080] [P1] [Foundation] Update response_composer to include evidence section (M)
  - File: `src/chains/nodes/response_composer.py`
  - Add: evidence section if available (5-8 articles with titles + brief notes)
  - Language: "仅供科普参考，不作为诊疗依据" (for education only)
  - Reference: spec.md FR-032

### 6.2 Unit Tests (Evidence)

- [ ] [T081] [P1] [Foundation] Test evidence_router emergency bypass (M)
  - File: `tests/unit/test_nodes/test_evidence_router.py`
  - Cases: EMERGENCY triage → skip evidence; ROUTINE + confidence < 0.6 → skip; ROUTINE + confidence >= 0.6 → retrieve
  - Assert: correct routing decision

- [ ] [T082] [P1] [Foundation] Test ncbi_query_builder query generation (M)
  - File: `tests/unit/test_nodes/test_ncbi_query_builder.py`
  - Cases: various symptom schemas
  - Assert: query includes relevant terms, date filter, article type filter

- [ ] [T083] [P1] [Foundation] Test ncbi_retriever_tool ranking (L)
  - File: `tests/unit/test_nodes/test_ncbi_retriever_tool.py`
  - Cases: 20 PubMed results → rank to top 5-8
  - Mock: NCBIService responses
  - Assert: ranking by relevance, recency, guideline priority

### 6.3 Integration Tests (Evidence)

- [ ] [T084] [P1] [Foundation] Test full workflow: ROUTINE → evidence retrieval (L)
  - File: `tests/integration/test_full_workflow.py`
  - Scenario: ROUTINE triage with case_domain=dermatology
  - Mock: NCBI service
  - Assert: evidence_selected 5-8 items, included in final response

- [ ] [T085] [P1] [Foundation] Test NCBI service failure graceful degradation (M)
  - File: `tests/integration/test_external_services.py`
  - Scenario: NCBI timeout/error
  - Assert: status=final, evidence omitted, medical advice still provided

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal**: Finalize production readiness with testing, documentation, monitoring

**Deliverables**: Production-ready deployment with full test coverage

### 7.1 Contract Testing

- [ ] [T086] [P0] [Foundation] Create test_api_contract.py for OpenAPI compliance (L)
  - File: `tests/contract/test_api_contract.py`
  - Validate: request/response schemas match openapi.yaml
  - Test: all error codes (400, 500, 503)
  - Reference: openapi.yaml

- [ ] [T087] [P1] [Foundation] Create test_state_transitions.py for LangGraph (M)
  - File: `tests/contract/test_state_transitions.py`
  - Validate: all 18 nodes execute in correct order
  - Test: all conditional routing paths (image quality, clarification, emergency bypass)
  - Reference: state-schema.yaml

### 7.2 External Service Testing

- [ ] [T088] [P1] [Foundation] Test Redis service lifecycle (M)
  - File: `tests/integration/test_session_management.py`
  - Cases: save, load, expire (TTL), delete
  - Assert: data persists, TTL auto-expires

- [ ] [T089] [P1] [Foundation] Test all external services with mock failures (L)
  - File: `tests/integration/test_external_services.py`
  - Services: Redis, Amap, Weather, NCBI, Qwen API
  - Cases: timeout, error response, empty response
  - Assert: graceful degradation, no system crashes

### 7.3 Performance Testing

- [ ] [T090] [P1] [Foundation] Create performance tests for SLA compliance (L)
  - File: `tests/integration/test_performance.py`
  - Test: EMERGENCY ≤5 seconds p95, ROUTINE ≤15 seconds p95
  - Load: 100 concurrent users
  - Assert: response time percentiles meet SLA
  - Reference: spec.md FR-051, FR-052, FR-054

### 7.4 Documentation

- [ ] [T091] [P1] [Foundation] Create ARCHITECTURE.md (M)
  - File: `docs/ARCHITECTURE.md`
  - Content: system overview, 18-node workflow, data flow diagram
  - Diagrams: Mermaid or ASCII diagrams for state transitions

- [ ] [T092] [P1] [Foundation] Create WORKFLOW.md (M)
  - File: `docs/WORKFLOW.md`
  - Content: detailed node-by-node explanation
  - Include: conditional routing logic, error handling

- [ ] [T093] [P0] [Foundation] Create SAFETY.md (L)
  - File: `docs/SAFETY.md`
  - Content: safety measures, compliance checklist, constitution alignment
  - Include: red flag rule review process, prohibited content detection

- [ ] [T094] [P1] [Foundation] Create DEPLOYMENT.md (M)
  - File: `docs/DEPLOYMENT.md`
  - Content: LangServe CLI deployment, Docker configuration, environment variables
  - Include: production deployment checklist, rollback procedure

- [ ] [T124] [P1] [Foundation] Create metrics plan for success criteria measurement (S)
  - File: `docs/METRICS_PLAN.md`
  - Method: opt-in feedback + support-log sampling; store aggregate counts only (no user tracking)
  - Reference: spec.md SC-002, SC-003, SC-004, SC-015, SC-016, SC-017, OUT-019

### 7.5 Observability

- [ ] [T095] [P1] [Foundation] Create prometheus.yml scrape configuration (S)
  - File: `prometheus.yml`
  - Scrape: /metrics endpoint every 15 seconds
  - Reference: FR-060

- [ ] [T096] [P2] [Foundation] Create Grafana dashboard JSON (M)
  - File: `grafana/dashboards/tri-metrics.json`
  - Panels: response time, error rate, request rate, external service health
  - Reference: FR-060

- [ ] [T097] [P2] [Foundation] Verify distributed tracing with correlation IDs (M)
  - File: `src/utils/telemetry.py`
  - Test: trace propagation across API → Redis → external services
  - Assert: all log entries include correlation_id
  - Reference: FR-061, FR-062

### 7.6 Security Hardening

- [ ] [T098] [P0] [Foundation] Verify TLS 1.3 only configuration (S)
  - File: `src/server.py`
  - Configure: uvicorn with ssl_keyfile, ssl_certfile
  - Enforce: TLS 1.3 only (disable TLS 1.2, 1.1, 1.0)
  - Reference: spec.md CT-011

- [ ] [T099] [P0] [Foundation] Enable HSTS (HTTP Strict Transport Security) (S)
  - File: `src/server.py`
  - Header: Strict-Transport-Security: max-age=31536000; includeSubDomains
  - Reference: spec.md CT-012

- [ ] [T116] [P0] [Foundation] Enforce HTTP to HTTPS redirect (S)
  - File: `src/server.py`
  - Configure: redirect all HTTP traffic to HTTPS
  - Tests: `tests/integration/test_security.py`
  - Reference: spec.md CT-013

- [ ] [T117] [P1] [Foundation] Configure automatic TLS certificate renewal (S)
  - Files: `docs/DEPLOYMENT.md`, `docs/DEPLOYMENT_CHECKLIST.md`
  - Include: renewal mechanism and validation steps
  - Reference: spec.md CT-014

- [ ] [T100] [P1] [Foundation] Verify no sensitive data logging (M)
  - File: `tests/integration/test_logging.py`
  - Audit: all log statements for raw text, images, GPS coordinates
  - Assert: only structured symptom data logged
  - Reference: spec.md FR-063

### 7.7 Compliance Verification

- [ ] [T101] [P0] [Foundation] Create compliance checklist (M)
  - File: `docs/COMPLIANCE.md`
  - Check: all FRs implemented, CTs enforced, SCs measurable
  - Sign-off: medical advisor for all medical content (triage prompts/templates, red-flag rules, evidence summaries, response copy)

- [ ] [T122] [P0] [Foundation] Define medical content review scope and checklist (M)
  - File: `docs/MEDICAL_REVIEW.md`
  - Scope: triage prompts/templates, red-flag rules, evidence summaries, response copy, disclaimer/hotline text, self-care guidance
  - Reference: spec.md CT-022

- [ ] [T123] [P0] [Foundation] Record medical professional sign-off for initial content package (M)
  - File: `docs/MEDICAL_REVIEW_SIGNOFF.md`
  - Include: reviewer name, credentials, date, version reviewed
  - Reference: spec.md CT-022

- [ ] [T102] [P0] [Foundation] Verify red flag rule versioning (M)
  - File: `src/config/red_flag_rules.yaml`
  - Check: all rules have version field
  - Check: rule history tracked (git log)
  - Reference: spec.md FR-065, FR-066

- [ ] [T103] [P1] [Foundation] Verify audit log 30-day retention (S)
  - File: `src/utils/logging_config.py`
  - Configure: log rotation with 30-day retention
  - Reference: spec.md FR-067

- [ ] [T114] [P1] [Foundation] Create API version update checklist requiring manual review + test sign-off (S)
  - File: `docs/API_VERSIONING.md`
  - Reference: spec.md FR-041

- [ ] [T115] [P1] [Foundation] Add CI guard to require checklist update when api_versions.yaml changes (M)
  - File: `.github/workflows/` (or equivalent CI)
  - Reference: spec.md FR-041

### 7.8 Final Integration Testing

- [ ] [T104] [P0] [Foundation] Test all 4 user stories end-to-end (XL)
  - File: `tests/integration/test_user_stories.py`
  - US1: text-only triage (ROUTINE, EMERGENCY, clarification)
  - US2: image quality gate + visual extraction
  - US3: GPS navigation (3 hospitals + route + weather)
  - US4: multi-turn clarification (2 rounds max)
  - Assert: all acceptance criteria met

- [ ] [T105] [P0] [Foundation] Test all 13 edge cases (XL)
  - File: `tests/integration/test_edge_cases.py`
  - Edge cases 1-13 from spec.md
  - Assert: graceful handling, no crashes, safe outputs

- [ ] [T106] [P0] [Foundation] Test graceful degradation (all external services fail) (L)
  - File: `tests/integration/test_external_services.py`
  - Scenario: NCBI + Amap + Weather + Redis all fail
  - Assert: status=final, medical advice provided, general guidance for navigation

- [ ] [T107] [P1] [Foundation] Load test with 100 concurrent users (L)
  - File: `tests/load/test_concurrent_users.py`
  - Tool: locust or similar
  - Assert: no performance degradation, all SLAs met
  - Reference: spec.md FR-054

### 7.9 Production Readiness

- [ ] [T108] [P0] [Foundation] Create production deployment checklist (M)
  - File: `docs/DEPLOYMENT_CHECKLIST.md`
  - Items: SSL certificate, HSTS, environment variables, Redis configuration, monitoring setup, log aggregation

- [ ] [T109] [P1] [Foundation] Create rollback procedure documentation (S)
  - File: `docs/ROLLBACK.md`
  - Steps: git revert, docker-compose down, deploy previous version, verify health
  - Reference: spec.md FR-068

- [ ] [T110] [P2] [Foundation] Create runbook for common incidents (M)
  - File: `docs/RUNBOOK.md`
  - Scenarios: high error rate, slow response times, external service down, Redis connection failure

- [ ] [T120] [P2] [Foundation] Define availability SLO monitoring and alerting (M)
  - Files: `docs/DEPLOYMENT_CHECKLIST.md`, `grafana/dashboards/tri-metrics.json`
  - Metrics: uptime targets and alert thresholds
  - Reference: spec.md FR-053

- [ ] [T121] [P2] [Foundation] Document horizontal scaling plan (M)
  - File: `docs/ARCHITECTURE.md`
  - Content: scale-out strategy and limits
  - Reference: spec.md FR-055

### 7.10 Code Quality & Final Review

- [ ] [T111] [P1] [Foundation] Run full test suite and achieve 80%+ coverage (M)
  - Command: `pytest --cov=src --cov-report=html`
  - Assert: coverage >= 80%, all tests pass
  - Fix: any failing tests

- [ ] [T112] [P1] [Foundation] Run Black, Ruff, mypy on entire codebase (M)
  - Commands: `black src/ tests/`, `ruff check src/ tests/`, `mypy src/`
  - Fix: all linting issues, type errors

---

## Summary

**Total Tasks**: 124

**By Priority**:
- P0 (blocking): 44 tasks
- P1 (high): 63 tasks
- P2 (medium): 17 tasks
- P3 (low): 0 tasks

**By User Story**:
- Foundation (Phases 1, 2, 6, 7): 76 tasks
- US1 - Symptom Triage with Text (Phase 3): 26 tasks
- US2 - Image Quality Check (Phase 4): 9 tasks
- US3 - Hospital Navigation (Phase 5): 13 tasks
- US4 - Multi-Turn Clarification: covered within US1 tasks (T042, T059, T104)

**Recommended Implementation Order**:
1. Phase 1 (Setup) → All P0 tasks
2. Phase 2 (Foundation) → All P0 tasks
3. Phase 3 (US1) → All P0/P1 tasks (Core MVP)
4. Phase 6 (Evidence, optional) → All P0/P1 tasks (Foundation enhancement)
5. Phase 4 (US2) → All P0/P1 tasks
6. Phase 5 (US3) → All P0/P1 tasks
7. Phase 7 (Polish) → All P0/P1 tasks

**MVP Definition**: Phases 1-3 complete (US1 working) → System provides core medical triage value

**Production Ready**: All 7 phases complete → Full feature set per spec.md
