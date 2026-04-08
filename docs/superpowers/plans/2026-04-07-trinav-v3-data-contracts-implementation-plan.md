# TriNav v3 Data Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace v3 capability-to-capability heuristic state reconstruction with explicit typed turn-state contracts.

**Architecture:** Introduce one canonical `MedicalTurnState` model carried on `ExecutionContext`, add `state_patch` to `CapabilityResult`, and update the v3 coordinator to merge patches after each capability run. Refactor v3 capabilities so consultation, triage, evidence, navigation, and response all read and write the canonical turn state instead of re-deriving data from raw text or metadata.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI runtime adapters, pytest, mypy

---

### Task 1: Introduce Canonical Turn-State Models

**Files:**
- Create: `src/core/runtime/medical_state.py`
- Modify: `src/core/runtime/execution_context.py`
- Modify: `src/core/runtime/types.py`
- Test: `tests/unit/test_v3/test_state_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.types import CapabilityResult


def test_execution_context_starts_with_empty_turn_state() -> None:
    context = ExecutionContext(
        request_id="req-state-1",
        session_id="sess-state-1",
        text="持续头痛两天",
    )

    assert context.turn_state.consultation.summary is None
    assert context.turn_state.triage.triage_level is None
    assert context.turn_state.evidence.evidence_selected == []
    assert context.turn_state.navigation.navigation_result is None


def test_capability_result_accepts_state_patch() -> None:
    result = CapabilityResult(
        name="consultation",
        success=True,
        payload={"status": "ok"},
        state_patch={"consultation": {"summary": "部位：头部；症状：头痛"}},
    )

    assert result.state_patch["consultation"]["summary"] == "部位：头部；症状：头痛"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_v3/test_state_contracts.py -v`
Expected: FAIL with `AttributeError` for missing `turn_state` and/or `ValidationError` for unexpected `state_patch`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/runtime/medical_state.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConsultationState(BaseModel):
    symptom_schema: dict[str, object] = Field(default_factory=dict)
    summary: str | None = None


class TriageState(BaseModel):
    triage_level: Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"] | None = None
    triage_reason: str | None = None
    recommended_departments: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    self_care_tips: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class EvidenceState(BaseModel):
    ncbi_query: str | None = None
    evidence_selected: list[dict[str, object]] = Field(default_factory=list)


class NavigationState(BaseModel):
    navigation_result: dict[str, object] | None = None
    weather_alert: dict[str, object] | None = None


class ResponseState(BaseModel):
    status: str | None = None
    response: str | None = None


class MedicalTurnState(BaseModel):
    consultation: ConsultationState = Field(default_factory=ConsultationState)
    triage: TriageState = Field(default_factory=TriageState)
    evidence: EvidenceState = Field(default_factory=EvidenceState)
    navigation: NavigationState = Field(default_factory=NavigationState)
    response: ResponseState = Field(default_factory=ResponseState)
```

```python
# src/core/runtime/execution_context.py
from pydantic import BaseModel, Field, StringConstraints
from src.core.runtime.medical_state import MedicalTurnState


class ExecutionContext(BaseModel):
    request_id: NonEmptyStr
    session_id: NonEmptyStr
    text: NonEmptyStr
    image_base64: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    metadata: dict[str, JSONValue] = Field(default_factory=dict)
    turn_state: MedicalTurnState = Field(default_factory=MedicalTurnState)
```

```python
# src/core/runtime/types.py
class CapabilityResult(BaseModel):
    name: str
    success: bool
    payload: dict[str, JSONValue]
    provenance: dict[str, JSONValue] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    state_patch: dict[str, JSONValue] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_v3/test_state_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/runtime/medical_state.py src/core/runtime/execution_context.py src/core/runtime/types.py tests/unit/test_v3/test_state_contracts.py
git commit -m "feat(v3): add canonical medical turn state models"
```

### Task 2: Merge State Patches in the v3 Coordinator

**Files:**
- Create: `src/core/runtime/state_patch.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Test: `tests/unit/test_v3/test_task_coordinator_v3.py`

- [ ] **Step 1: Write the failing test**

```python
from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.state_patch import apply_state_patch
from src.core.runtime.types import CapabilityResult


def test_apply_state_patch_preserves_existing_values() -> None:
    context = ExecutionContext(
        request_id="req-patch-1",
        session_id="sess-patch-1",
        text="头痛并发热",
    )
    seeded = context.model_copy(
        update={
            "turn_state": context.turn_state.model_copy(
                update={
                    "consultation": context.turn_state.consultation.model_copy(
                        update={"summary": "部位：头部"}
                    )
                }
            )
        }
    )
    result = CapabilityResult(
        name="triage",
        success=True,
        payload={"status": "ok"},
        state_patch={"triage": {"triage_level": "URGENT", "triage_reason": "存在发热风险"}},
    )

    updated = apply_state_patch(seeded, result)

    assert updated.turn_state.consultation.summary == "部位：头部"
    assert updated.turn_state.triage.triage_level == "URGENT"
    assert updated.turn_state.triage.triage_reason == "存在发热风险"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_v3/test_task_coordinator_v3.py::test_apply_state_patch_preserves_existing_values -v`
Expected: FAIL with `ImportError` for missing `apply_state_patch`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/runtime/state_patch.py
from __future__ import annotations

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.medical_state import MedicalTurnState
from src.core.runtime.types import CapabilityResult


def apply_state_patch(context: ExecutionContext, result: CapabilityResult) -> ExecutionContext:
    patch = result.state_patch if isinstance(result.state_patch, dict) else {}
    if not patch:
        return context

    merged_state = context.turn_state.model_copy(
        update=_deep_merge(context.turn_state.model_dump(mode="python"), patch)
    )
    return context.model_copy(update={"turn_state": MedicalTurnState.model_validate(merged_state)})


def _deep_merge(base: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
```

```python
# src/interfaces/api/assistant_v2.py
from src.core.runtime.state_patch import apply_state_patch


async def _run_task_with_enriched_context(task_name: str, capability: Any) -> dict[str, Any]:
    nonlocal task_context
    task_payload = await _run_v3_capability_task(capability, task_context)
    task_result = CapabilityResult(
        name=task_name,
        success=task_payload["status"] == "ok",
        payload=task_payload.get("payload", {}),
        provenance=task_payload.get("provenance", {}),
        errors=task_payload.get("errors", []),
        state_patch=task_payload.get("state_patch", {}),
    )
    task_context = apply_state_patch(task_context, task_result)
    task_context = _enrich_v3_task_context(
        task_context,
        task_name=task_name,
        task_payload=task_payload,
    )
    return task_payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_v3/test_task_coordinator_v3.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/runtime/state_patch.py src/interfaces/api/assistant_v2.py tests/unit/test_v3/test_task_coordinator_v3.py
git commit -m "feat(v3): merge capability state patches in coordinator"
```

### Task 3: Emit Canonical State Patches from Consultation, Triage, Evidence, and Navigation

**Files:**
- Modify: `src/capabilities/consultation/capability.py`
- Modify: `src/capabilities/triage/capability.py`
- Modify: `src/capabilities/evidence/capability.py`
- Modify: `src/capabilities/navigation/capability.py`
- Test: `tests/unit/test_v3/test_real_capabilities.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from src.capabilities import ConsultationCapability, TriageCapability
from src.core.runtime.execution_context import ExecutionContext


@pytest.mark.asyncio
async def test_consultation_and_triage_emit_state_patch() -> None:
    context = ExecutionContext(
        request_id="req-cap-patch-1",
        session_id="sess-cap-patch-1",
        text="胸痛并呼吸困难",
    )

    consultation = ConsultationCapability()
    consultation_result = await consultation.run(context, await consultation.plan(context))
    assert "consultation" in consultation_result.state_patch
    assert "summary" in consultation_result.state_patch["consultation"]

    triage = TriageCapability()
    triage_result = await triage.run(context, await triage.plan(context))
    assert "triage" in triage_result.state_patch
    assert "triage_level" in triage_result.state_patch["triage"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_v3/test_real_capabilities.py::test_consultation_and_triage_emit_state_patch -v`
Expected: FAIL because `state_patch` is empty.

- [ ] **Step 3: Write minimal implementation**

```python
# src/capabilities/consultation/capability.py
return CapabilityResult(
    name=self.name,
    success=True,
    payload={
        "status": "ok",
        "summary": summary,
        "consultation_signal": "intake_complete",
    },
    provenance={"source": _SOURCE, "capability_version": self.version},
    state_patch={
        "consultation": {
            "summary": summary,
            "symptom_schema": symptom_schema,
        }
    },
)
```

```python
# src/capabilities/triage/capability.py
return CapabilityResult(
    name=self.name,
    success=True,
    payload={...},
    provenance={"source": _SOURCE, "capability_version": self.version},
    state_patch={
        "triage": {
            "triage_level": triage_level,
            "triage_reason": merged_state.get("triage_reason", ""),
            "recommended_departments": merged_state.get("recommended_departments", []),
            "possible_causes": merged_state.get("possible_causes", []),
            "self_care_tips": merged_state.get("self_care_tips", []),
            "red_flags": merged_state.get("red_flags", []),
        }
    },
)
```

```python
# src/capabilities/evidence/capability.py
state_patch={
    "evidence": {
        "ncbi_query": query,
        "evidence_selected": evidence_selected,
    }
}
```

```python
# src/capabilities/navigation/capability.py
state_patch={
    "navigation": {
        "navigation_result": navigation_result,
        "weather_alert": weather_alert,
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_v3/test_real_capabilities.py tests/unit/test_v3/test_capabilities_v3.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capabilities/consultation/capability.py src/capabilities/triage/capability.py src/capabilities/evidence/capability.py src/capabilities/navigation/capability.py tests/unit/test_v3/test_real_capabilities.py tests/unit/test_v3/test_capabilities_v3.py
git commit -m "feat(v3): emit structured state patches from medical capabilities"
```

### Task 4: Make Response Capability Consume Canonical Turn State

**Files:**
- Modify: `src/capabilities/response/capability.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Test: `tests/unit/test_server_v3.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from src.capabilities.response.capability import ResponseCapability
from src.core.runtime.execution_context import ExecutionContext


@pytest.mark.asyncio
async def test_response_capability_uses_turn_state_instead_of_text_heuristics() -> None:
    context = ExecutionContext(
        request_id="req-response-state-1",
        session_id="sess-response-state-1",
        text="轻微头痛",
    )
    context = context.model_copy(
        update={
            "turn_state": context.turn_state.model_copy(
                update={
                    "triage": context.turn_state.triage.model_copy(
                        update={
                            "triage_level": "EMERGENCY",
                            "triage_reason": "规则命中高风险症状",
                            "recommended_departments": ["急诊"],
                        }
                    )
                }
            )
        }
    )

    result = await ResponseCapability().run(context, {"enabled": True})

    assert result.payload["status"] == "final"
    assert "急诊" in result.payload["response"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_v3.py tests/unit/test_v3/test_real_capabilities.py::test_response_capability_uses_turn_state_instead_of_text_heuristics -v`
Expected: FAIL because response generation still derives triage from raw text.

- [ ] **Step 3: Write minimal implementation**

```python
# src/capabilities/response/capability.py
def _build_response_state(context: ExecutionContext) -> dict[str, Any]:
    triage_state = context.turn_state.triage
    evidence_state = context.turn_state.evidence
    navigation_state = context.turn_state.navigation

    triage_level = triage_state.triage_level or "ROUTINE"
    triage_reason = triage_state.triage_reason or "当前信息未见明确紧急信号，建议常规门诊就诊"

    return {
        "session_id": context.session_id,
        "need_clarify": False,
        "triage_level": triage_level,
        "triage_reason": triage_reason,
        "recommended_departments": triage_state.recommended_departments,
        "possible_causes": triage_state.possible_causes,
        "self_care_tips": triage_state.self_care_tips,
        "red_flags": triage_state.red_flags,
        "navigation_result": navigation_state.navigation_result,
        "weather_alert": navigation_state.weather_alert,
        "evidence_selected": evidence_state.evidence_selected,
    }
```

```python
# src/interfaces/api/assistant_v2.py
body["triage_level"] = task_context.turn_state.triage.triage_level
body["recommended_departments"] = task_context.turn_state.triage.recommended_departments
body["possible_causes"] = task_context.turn_state.triage.possible_causes
body["red_flags"] = task_context.turn_state.triage.red_flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_v3.py tests/unit/test_v3/test_real_capabilities.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capabilities/response/capability.py src/interfaces/api/assistant_v2.py tests/unit/test_server_v3.py tests/unit/test_v3/test_real_capabilities.py
git commit -m "refactor(v3): build responses from canonical turn state"
```
