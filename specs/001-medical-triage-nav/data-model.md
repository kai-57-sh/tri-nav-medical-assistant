# Data Model: TriNav Medical Triage System

**Feature**: Medical Triage and Hospital Navigation Assistant (TriNav)
**Date**: 2025-01-09
**Technologies**: Pydantic v2, Redis (JSON serialization), LangGraph TypedDict

---

## Overview

This document defines the 7 core entities for the TriNav system. All entities use:
- **Pydantic v2** for runtime validation and JSON schema generation
- **Redis JSON serialization** for session storage (60-minute TTL per CT-006)
- **LangGraph TypedDict** for workflow state management
- **Type hints** throughout for IDE support and mypy checking

---

## Entity 1: Session State (Redis)

**Purpose**: Maintain conversation context across multiple turns with 60-minute TTL.

**Storage**: Redis (ephemeral, per FR-007, CT-007, CT-008)

### Pydantic Model

```python
# src/models/session.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class SessionState(BaseModel):
    """Session state stored in Redis (60-minute TTL)."""

    # === Identity ===
    session_id: str = Field(..., description="UUID for conversation session")

    # === Conversation Tracking ===
    turn_count: int = Field(default=1, ge=1, le=2, description="Current clarification round (max 2 per CT-009)")
    last_updated_at: datetime = Field(default_factory=datetime.now, description="Last access time for TTL refresh")

    # === Clinical Data (Structured ONLY) ===
    symptom_schema: Optional[Dict[str, Any]] = Field(None, description="Extracted symptom information (body part, duration, severity, etc.)")
    clarify_questions: List[str] = Field(default_factory=list, description="Questions asked in previous turns")
    triage_level: Optional[str] = Field(None, pattern="^(EMERGENCY|URGENT|ROUTINE|SELF_CARE)$", description="Current triage assessment")
    case_domain: Optional[str] = Field(None, pattern="^(dermatology|trauma|respiratory|gastro|neuro|urology|other)$", description="Medical specialty")

    # === Cache References (to avoid re-fetching) ===
    evidence_cache_key: Optional[str] = Field(None, description="Reference to cached NCBI evidence")
    navigation_cache_key: Optional[str] = Field(None, description="Reference to cached hospital search results")

    # === Validation ===
    @validator('turn_count')
    def max_two_rounds(cls, v):
        """Enforce max 2 clarification rounds per CT-009."""
        if v > 2:
            raise ValueError("turn_count cannot exceed 2")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "turn_count": 1,
                "last_updated_at": "2025-01-09T10:30:00Z",
                "symptom_schema": {
                    "body_part": "手臂",
                    "symptoms": ["红疹", "痒"],
                    "duration": "2天",
                    "severity": "轻微"
                },
                "clarify_questions": [],
                "triage_level": "ROUTINE",
                "case_domain": "dermatology"
            }
        }

# What's NOT stored (privacy constraints):
# - raw_text: Violates CT-008 (no full text storage)
# - raw_image_base64: Violates CT-007 (no raw images in Redis)
# - precise_gps_long_term: Privacy concern (use cache_key instead)
```

### Redis Schema

```python
# Redis key pattern: session:{session_id}
# Value: JSON-serialized SessionState
# TTL: 3600 seconds (60 minutes per CT-006)

# Example:
# Key: session:550e8400-e29b-41d4-a716-446655440000
# Value: {"session_id": "...", "turn_count": 1, "symptom_schema": {...}}
# TTL: 3600
```

### Lifecycle

1. **Created**: When user submits first request (InputValidator node)
2. **Updated**: After each turn (SessionSave node)
3. **Expired**: Automatically after 60 minutes of inactivity (Redis TTL)
4. **Deleted**: Not needed - TTL handles cleanup

---

## Entity 2: Symptom Schema

**Purpose**: Structured representation of user's reported symptoms.

**Source**: Extracted by ClinicalExtractor node from text + visual findings.

### Pydantic Model

```python
# src/models/symptom_schema.py
from pydantic import BaseModel, Field
from typing import Optional, List

class VisualFindings(BaseModel):
    """Image-based observations (optional, only if image provided)."""

    type: str = Field(..., pattern="^(rash|wound|unknown)$", description="Type of visual symptom")
    summary: str = Field(..., min_length=1, max_length=500, description="Plain-language visual description")
    features: List[str] = Field(default_factory=list, description="Observable characteristics (e.g., ['红斑', '丘疹'])")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")

class SymptomSchema(BaseModel):
    """Structured symptom information for clinical decision-making."""

    # === Core Symptoms ===
    body_part: str = Field(..., min_length=1, max_length=50, description="Affected area (e.g., '手臂', '胸口')")
    symptoms: List[str] = Field(..., min_items=1, max_items=10, description="Reported symptoms (e.g., ['红疹', '痒'])")

    # === Context ===
    duration: Optional[str] = Field(None, max_length=50, description="How long symptoms persisted (e.g., '2天', '1周')")
    severity: Optional[str] = Field(None, pattern="^(轻微|中度|严重)$", description="User-reported intensity")
    accompanying_symptoms: List[str] = Field(default_factory=list, description="Other symptoms (e.g., ['发热', '头痛'])")
    onset: Optional[str] = Field(None, pattern="^(突然|逐渐)$", description="How symptoms started")

    # === Visual Findings (Optional) ===
    visual_findings: Optional[VisualFindings] = Field(None, description="Image-based observations if image uploaded")

    class Config:
        json_schema_extra = {
            "example": {
                "body_part": "手臂",
                "symptoms": ["红疹", "痒"],
                "duration": "2天",
                "severity": "轻微",
                "accompanying_symptoms": [],
                "onset": "逐渐",
                "visual_findings": {
                    "type": "rash",
                    "summary": "手臂红斑伴丘疹",
                    "features": ["红斑", "丘疹", "肿胀"],
                    "confidence": 0.85
                }
            }
        }
```

### Validation Rules

- **body_part**: Required, max 50 characters (FR-001: 2000 char text limit enforced at input)
- **symptoms**: Required, 1-10 items (prevents excessive complexity)
- **duration**: Optional, max 50 characters
- **severity**: Enum (轻微/中度/严重) if provided
- **visual_findings**: Only present if image uploaded and quality check passed

---

## Entity 3: Triage Assessment

**Purpose**: Medical triage decision and recommendations.

**Source**: Generated by TriageClassifier node, merged with rule-based results in TriageMerger node.

### Pydantic Model

```python
# src/models/triage_assessment.py
from pydantic import BaseModel, Field, validator
from typing import List, Literal

class TriageAssessment(BaseModel):
    """Medical triage decision and recommendations."""

    # === Urgency Assessment ===
    triage_level: Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"] = Field(
        ...,
        description="Urgency classification (per FR-018)"
    )
    triage_reason: str = Field(..., min_length=1, max_length=500, description="Explanation of triage decision (per FR-043)")
    triage_source: Literal["rule_engine", "llm", "merged"] = Field(
        ...,
        description="Source of triage decision (for audit trail per FR-066)"
    )

    # === Recommendations ===
    recommended_departments: List[str] = Field(
        ...,
        min_items=1,
        max_items=5,
        description="Suggested medical departments (per FR-019)"
    )

    # === Possible Causes (Qualified) ===
    possible_causes: List[str] = Field(
        ...,
        min_items=0,
        max_items=3,
        description="Suspected causes with '疑似' or '可能' qualifiers (per FR-020)"
    )

    @validator('possible_causes')
    def must_use_qualified_language(cls, v):
        """Enforce '疑似' or '可能' qualifiers per FR-020, CT-001."""
        for cause in v:
            if not any(q in cause for q in ["疑似", "可能", "相关"]):
                raise ValueError(f"Cause must use qualified language: {cause}")
        return v

    # === Self-Care Guidance ===
    self_care_tips: List[str] = Field(
        ...,
        min_items=0,
        max_items=10,
        description="Non-prescriptive care guidance (per FR-021)"
    )

    @validator('self_care_tips')
    def no_prescriptive_language(cls, v):
        """Prohibit drug dosages or treatment protocols per FR-021, CT-002."""
        prohibited_patterns = ["mg", "每次", "剂量", "片", "服用", "用药"]
        for tip in v:
            if any(p in tip for p in prohibited_patterns):
                raise ValueError(f"Self-care tip cannot contain prescriptive language: {tip}")
        return v

    # === Red Flags (Warning Signs) ===
    red_flags: List[str] = Field(
        ...,
        min_items=0,
        max_items=10,
        description="Warning signs requiring immediate emergency care (per FR-022)"
    )

    # === Internal State ===
    red_flags_hit: List[str] = Field(
        default_factory=list,
        description="IDs of triggered red flag rules (for audit per FR-066)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "triage_level": "ROUTINE",
                "triage_reason": "症状轻微，无危险信号",
                "triage_source": "llm",
                "recommended_departments": ["皮肤科"],
                "possible_causes": [
                    "过敏相关皮疹（疑似）",
                    "接触性皮炎（疑似）"
                ],
                "self_care_tips": [
                    "避免抓挠患处",
                    "记录皮疹变化",
                    "避免接触可能过敏源"
                ],
                "red_flags": [
                    "如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"
                ],
                "red_flags_hit": []
            }
        }
```

### Validation Rules

- **triage_level**: Must be one of 4 levels (EMERGENCY/URGENT/ROUTINE/SELF_CARE)
- **possible_causes**: Max 3 items, MUST contain "疑似"/"可能"/"相关" (FR-020, CT-001)
- **self_care_tips**: No drug dosages, no treatment protocols (FR-021, CT-002)
- **recommended_departments**: At least 1, max 5 departments (FR-019)
- **red_flags**: Warning signs for when to seek emergency care (FR-022)

---

## Entity 4: Evidence (Literature)

**Purpose**: Reference to medical literature for科普解释 (public education, NOT diagnosis).

**Source**: Retrieved from NCBI/PubMed by EvidenceRetriever node, ranked by EvidenceRanker node.

### Pydantic Model

```python
# src/models/evidence.py
from pydantic import BaseModel, Field
from typing import Optional

class Evidence(BaseModel):
    """Medical literature reference for public education (NOT treatment guidance)."""

    # === Identification ===
    pmid: str = Field(..., description="PubMed ID")

    # === Metadata ===
    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    year: str = Field(..., pattern=r"^\d{4}$", description="Publication year (last 10 years per FR-030)")
    source: str = Field(..., max_length=200, description="Journal name")
    type: str = Field(
        ...,
        pattern="^(Guideline|SystematicReview|Review|RCT|CaseReport|Other)$",
        description="Article type (per FR-030: preference for reviews/guidelines)"
    )

    # === Relevance ===
    note: Optional[str] = Field(None, max_length=500, description="Brief relevance explanation")

    class Config:
        json_schema_extra = {
            "example": {
                "pmid": "12345678",
                "title": "Acute urticaria: Evaluation and management",
                "year": "2023",
                "source": "Journal of Allergy and Clinical Immunology",
                "type": "Review",
                "note": "最新急性荨麻疹诊疗指南"
            }
        }
```

### Constraints

- **Usage**: For public education ONLY, NOT as individual treatment guidance (per entity description in spec)
- **Max items**: 8 per response (FR-031)
- **Time filter**: Last 10 years preference (FR-030)
- **Type preference**: Guidelines > Systematic Reviews > Reviews > RCT > Case Reports (FR-030)

---

## Entity 5: Navigation Result

**Purpose**: Hospital recommendations and route guidance.

**Source**: Generated by Navigator node using Amap API.

### Pydantic Model

```python
# src/models/navigation_result.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Literal

class RoutePlan(BaseModel):
    """Navigation route to top-ranked hospital."""

    to_hospital_rank: int = Field(..., ge=1, le=3, description="Target hospital rank (always 1)")
    mode: Literal["driving", "transit", "walking"] = Field(..., description="Transport method (per FR-036)")
    eta_min: int = Field(..., ge=1, description="Estimated travel time in minutes (per FR-036)")
    summary: str = Field(..., min_length=1, max_length=200, description="Plain-language route description (per FR-036)")

class Hospital(BaseModel):
    """Individual hospital recommendation."""

    rank: int = Field(..., ge=1, le=3, description="Priority order (1 = top recommendation)")
    name: str = Field(..., max_length=100, description="Hospital name")
    is_3a: bool = Field(..., description="Grade 3A (三甲) status (per FR-034)")
    address: Optional[str] = Field(None, max_length=200, description="Hospital address")
    distance_m: Optional[int] = Field(None, ge=0, description="Distance in meters")
    location: Dict[str, float] = Field(..., description="GPS coordinates {lat, lng}")
    phone: Optional[str] = Field(None, max_length=50, description="Hospital phone number")
    reason: str = Field(..., min_length=1, max_length=200, description="Ranking rationale (per FR-044)")

class NavigationResult(BaseModel):
    """Complete navigation result with hospitals and route."""

    # === Search Parameters ===
    radius_km: int = Field(default=10, ge=1, le=50, description="Search radius in kilometers (per FR-033)")

    # === Hospital Recommendations ===
    hospitals: List[Hospital] = Field(..., min_items=3, max_items=3, description="Exactly 3 hospitals: Top1 + 2 alternatives (per FR-035)")

    @validator('hospitals')
    def exactly_three_hospitals(cls, v):
        """Enforce exactly 3 hospitals per FR-035."""
        if len(v) != 3:
            raise ValueError("Must have exactly 3 hospitals")
        return v

    @validator('hospitals')
    def ranked_correctly(cls, v):
        """Validate ranking sequence 1, 2, 3."""
        ranks = [h.rank for h in v]
        if sorted(ranks) != [1, 2, 3]:
            raise ValueError("Hospitals must be ranked 1, 2, 3")
        return v

    # === Route Planning ===
    route_plan: RoutePlan = Field(..., description="Route to top-ranked hospital (per FR-036)")

    class Config:
        json_schema_extra = {
            "example": {
                "radius_km": 10,
                "hospitals": [
                    {
                        "rank": 1,
                        "name": "北京协和医院",
                        "is_3a": True,
                        "address": "北京市东城区帅府园1号",
                        "distance_m": 1200,
                        "location": {"lat": 39.914, "lng": 116.417},
                        "phone": "010-69156699",
                        "reason": "三甲综合医院，距离较近，急诊/门诊齐全"
                    },
                    {
                        "rank": 2,
                        "name": "中日友好医院",
                        "is_3a": True,
                        "address": "北京市朝阳区樱花园东街",
                        "distance_m": 3500,
                        "location": {"lat": 39.979, "lng": 116.447},
                        "phone": "010-84205566",
                        "reason": "三甲综合医院，口碑较好"
                    },
                    {
                        "rank": 3,
                        "name": "朝阳医院",
                        "is_3a": False,
                        "address": "北京市朝阳区工人体育场南路",
                        "distance_m": 900,
                        "location": {"lat": 39.921, "lng": 116.457},
                        "phone": "010-85231000",
                        "reason": "距离更近，可作为备选"
                    }
                ],
                "route_plan": {
                    "to_hospital_rank": 1,
                    "mode": "driving",
                    "eta_min": 15,
                    "summary": "大约15分钟车程"
                }
            }
        }
```

### Validation Rules

- **Exactly 3 hospitals**: Top recommendation + 2 alternatives (FR-035)
- **Ranking priority**: Grade 3A hospitals prioritized (FR-034)
- **Route to Rank 1 only**: Navigation provided for top hospital (FR-036)
- **Radius**: 10km default, configurable (FR-033, AS-009)

---

## Entity 6: Weather Alert

**Purpose**: Weather-related travel tips.

**Source**: Fetched by WeatherFetcher node from weather API.

### Pydantic Model

```python
# src/models/weather_alert.py
from pydantic import BaseModel, Field
from typing import List

class WeatherAlert(BaseModel):
    """Weather-related travel tips."""

    summary: str = Field(..., min_length=1, max_length=200, description="Weather condition description")
    tips: List[str] = Field(
        ...,
        min_items=0,
        max_items=5,
        description="Relevant advice (e.g., ['带伞', '注意保暖'])"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "小雨，气温5°C",
                "tips": ["带伞出行", "注意保暖", "路面湿滑小心"]
            }
        }
```

### Constraints

- **Optional**: Weather failure does not block navigation (FR-038, FR-046)
- **Relevance**: Tips related to travel conditions (umbrella, clothing, road safety)

---

## Entity 7: Red Flag Rule

**Purpose**: Emergency symptom detection rule (versioned, auditable).

**Source**: Loaded from `config/red_flag_rules.yaml` (version-controlled file).

### Pydantic Model

```python
# src/models/red_flag_rule.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Literal

class RuleCondition(BaseModel):
    """Single rule condition for symptom matching."""

    field: str = Field(..., description="Symptom schema field to check (e.g., 'accompanying_symptoms')")
    op: Literal["contains_any", "equals", "contains_all"] = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Expected value(s)")

class RedFlagRule(BaseModel):
    """Emergency symptom detection rule (versioned for audit trail per FR-054)."""

    # === Identification ===
    id: str = Field(..., pattern=r"^RF_[A-Z_]+$", description="Unique rule identifier (e.g., 'RF_BREATHING_DIFFICULTY')")
    priority: Literal["high", "medium", "low"] = Field(..., description="Rule importance for sorting")
    version: str = Field(..., description="Rule version for traceability (per FR-054)")

    # === Rule Logic ===
    conditions: List[RuleCondition] = Field(..., min_items=1, description="Rule conditions (AND logic between conditions)")

    # === Output ===
    triage_level: Literal["EMERGENCY"] = Field(..., description="Triage level when rule triggers (always EMERGENCY)")
    user_message: str = Field(..., min_length=1, max_length=500, description="Explanation to user")
    department: List[str] = Field(..., min_items=1, description="Recommended departments (typically ['急诊'])")

    @validator('id')
    def must_start_with_rf(cls, v):
        """Ensure rule ID follows naming convention."""
        if not v.startswith("RF_"):
            raise ValueError("Rule ID must start with 'RF_'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "RF_BREATHING_DIFFICULTY",
                "priority": "high",
                "version": "1.0.0",
                "conditions": [
                    {
                        "field": "accompanying_symptoms",
                        "op": "contains_any",
                        "value": ["呼吸困难", "喘不过气", "窒息感"]
                    }
                ],
                "triage_level": "EMERGENCY",
                "user_message": "检测到呼吸困难症状，建议立即急诊/呼叫急救",
                "department": ["急诊"]
            }
        }
```

### Example Configuration (YAML)

```yaml
# config/red_flag_rules.yaml
- id: RF_BREATHING_DIFFICULTY
  priority: high
  version: 1.0.0
  conditions:
    - field: accompanying_symptoms
      op: contains_any
      value: ["呼吸困难", "喘不过气", "窒息感"]
  triage_level: EMERGENCY
  user_message: "检测到呼吸困难症状，建议立即急诊/呼叫急救"
  department: ["急诊"]

- id: RF_CHEST_PAIN
  priority: high
  version: 1.0.0
  conditions:
    - field: body_part
      op: equals
      value: "胸口"
    - field: symptoms
      op: contains_any
      value: ["痛", "闷", "压迫感"]
  triage_level: EMERGENCY
  user_message: "胸痛可能是心脏问题征兆，建议立即急诊"
  department: ["急诊"]

- id: RF_HIGH_FEVER
  priority: medium
  version: 1.0.0
  conditions:
    - field: accompanying_symptoms
      op: contains_any
      value: ["发热", "发烧"]
    - field: severity
      op: equals
      value: "严重"
  triage_level: EMERGENCY
  user_message: "高热且症状严重，建议尽快急诊排查"
  department: ["急诊", "发热门诊"]
```

### Version Control

- **File**: `config/red_flag_rules.yaml` (committed to Git)
- **Version field**: Incremented on each change (semantic versioning)
- **Audit trail**: All changes tracked via Git (per FR-054, FR-066)
- **Medical sign-off**: Required before deployment (per SC-008)

---

## Entity Relationships

```
┌─────────────────┐
│  Session State  │
│  (Redis)         │
└────────┬────────┘
         │ 1
         │
         ▼
┌─────────────────┐       ┌──────────────────┐
│  Symptom Schema │ ──1──→│ Visual Findings  │
│                 │       │ (Optional)       │
└────────┬────────┘       └──────────────────┘
         │
         │ 1
         ▼
┌─────────────────┐       ┌──────────────────┐
│ Triage Assess.  │ ──N──→│ Red Flag Rules   │
│                 │       │ (N triggered)    │
└────────┬────────┘       └──────────────────┘
         │
         │ 1
         ▼
┌─────────────────┐       ┌──────────────────┐
│ Navigation Res. │ ──N──→│ Hospitals (3)    │
│                 │       │ + Route Plan     │
└─────────────────┘       └──────────────────┘

┌─────────────────┐       ┌──────────────────┐
│ Evidence        │ ──N──→│ Literature Items  │
│ (Optional)      │       │ (Max 8)          │
└─────────────────┘       └──────────────────┘

┌─────────────────┐
│ Weather Alert   │
│ (Optional)      │
└─────────────────┘
```

**Cardinality**:
- Session → Symptom Schema: 1:1 (current session state)
- Symptom Schema → Visual Findings: 1:0..1 (optional)
- Symptom Schema → Triage Assessment: 1:1
- Triage Assessment → Red Flag Rules: 1:N (N rules triggered)
- Triage Assessment → Navigation Result: 1:1 (if GPS provided)
- Navigation Result → Hospitals: 1:3 (fixed)
- Triage Assessment → Evidence: 1:0..8 (optional, max 8)

---

## LangGraph State Schema

**Purpose**: Complete workflow state for 18-node LangGraph.

**Note**: This is the FULL state schema used in LangGraph StateGraph. Entities above are SUBSETS used for Redis storage and API responses.

```python
# src/chains/graph/state.py
from typing_extensions import TypedDict, Annotated, Required, Literal
from typing import Optional, List, Dict, Any
from operator import add
from langgraph.graph.message import add_messages

class TriageState(TypedDict):
    """Complete state schema for 18-node LangGraph workflow."""

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

    # === Session State ===
    turn_count: int
    symptom_schema: Optional[Dict[str, Any]]
    clarify_questions: List[str]
    triage_level: Optional[Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]]
    case_domain: Optional[str]

    # === Workflow Flags ===
    image_is_clear: Optional[bool]
    need_clarify: bool
    evidence_needed: bool

    # === Evidence ===
    ncbi_query: Optional[str]
    candidate_evidence: Optional[List[Dict]]
    evidence_selected: Optional[List[Dict]]

    # === Navigation ===
    hospitals: Optional[List[Dict]]
    route_plan: Optional[Dict]

    # === Weather ===
    weather_alert: Optional[Dict]

    # === Output ===
    status: Literal["need_more_info", "final", "error"]
    error_message: Optional[str]
    final_response: Optional[str]
```

---

## JSON Schemas

For API contract validation, the following JSON schemas are generated from Pydantic models:

```json
{
  "SessionState": {
    "type": "object",
    "properties": {
      "session_id": {"type": "string", "format": "uuid"},
      "turn_count": {"type": "integer", "minimum": 1, "maximum": 2},
      "symptom_schema": {"type": "object"},
      "triage_level": {"type": "string", "enum": ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]}
    },
    "required": ["session_id", "turn_count"]
  },
  "SymptomSchema": {
    "type": "object",
    "properties": {
      "body_part": {"type": "string", "minLength": 1, "maxLength": 50},
      "symptoms": {"type": "array", "minItems": 1, "maxItems": 10},
      "severity": {"type": "string", "enum": ["轻微", "中度", "严重"]}
    },
    "required": ["body_part", "symptoms"]
  },
  "TriageAssessment": {
    "type": "object",
    "properties": {
      "triage_level": {"type": "string", "enum": ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]},
      "recommended_departments": {"type": "array", "minItems": 1, "maxItems": 5},
      "possible_causes": {"type": "array", "maxItems": 3},
      "self_care_tips": {"type": "array", "maxItems": 10}
    },
    "required": ["triage_level", "recommended_departments"]
  }
}
```

---

## Next Steps

1. ✅ Data models defined with Pydantic v2
2. → Generate OpenAPI contract (`contracts/openapi.yaml`)
3. → Generate LangGraph state schema (`contracts/state-schema.yaml`)
4. → Generate quickstart guide (`quickstart.md`)
5. → Update agent context
