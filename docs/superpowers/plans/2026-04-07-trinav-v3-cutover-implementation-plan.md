# TriNav v3 Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make v3 capability runtime the default execution path for both `/assistant/v3/*` and `/assistant/*` while preserving legacy graph fallback and shadow compare.

**Architecture:** Extract the current v3 task-coordinator path into a dedicated shared runtime module, point `/assistant/v3/*` at that module directly, and replace the current LangServe-backed `/assistant/invoke` surface with a compatibility adapter that keeps the old request/response envelope but delegates to v3. Legacy graph remains available only for fallback and compare paths.

**Tech Stack:** FastAPI, Pydantic v2, pytest, SSE streaming, existing legacy LangGraph chain

---

### Task 1: Extract a Shared v3 Runtime Module

**Files:**
- Create: `src/interfaces/api/runtime_v3.py`
- Modify: `src/interfaces/api/assistant_v3.py`
- Test: `tests/unit/test_server_v3.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi.responses import JSONResponse

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.assistant_v3 import invoke_assistant_v3


@pytest.mark.asyncio
async def test_assistant_v3_invoke_delegates_to_runtime_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_payload = None

    async def fake_invoke(payload: AssistantV2InvokePayload) -> JSONResponse:
        nonlocal observed_payload
        observed_payload = payload
        return JSONResponse(
            status_code=200,
            content={"status": "final", "session_id": payload.session_id, "response": "ok"},
        )

    monkeypatch.setattr("src.interfaces.api.assistant_v3.invoke_runtime_v3", fake_invoke)

    payload = AssistantV2InvokePayload(
        request_id="req-v3-cutover-1",
        session_id="sess-v3-cutover-1",
        trace_id="trace-v3-cutover-1",
        text="持续胸痛",
    )
    response = await invoke_assistant_v3(payload)

    assert observed_payload is payload
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_v3.py::test_assistant_v3_invoke_delegates_to_runtime_v3 -v`
Expected: FAIL because `invoke_runtime_v3` does not exist in `assistant_v3.py`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/interfaces/api/runtime_v3.py
from fastapi.responses import JSONResponse, StreamingResponse

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload, _invoke_v3_task_coordinator


async def invoke_runtime_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    request_id = (payload.request_id or "").strip() or "req-missing"
    session_id = (payload.session_id or "").strip() or "sess-missing"
    trace_id = (payload.trace_id or "").strip() or "trace-missing"
    return await _invoke_v3_task_coordinator(
        payload,
        request_id=request_id,
        session_id=session_id,
        trace_id=trace_id,
    )


async def stream_runtime_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    from src.interfaces.api.assistant_v2 import stream_assistant_v2
    return await stream_assistant_v2(payload.model_copy(update={"metadata": {**payload.metadata, "runtime_mode": "v3"}}))
```

```python
# src/interfaces/api/assistant_v3.py
from src.interfaces.api.runtime_v3 import invoke_runtime_v3, stream_runtime_v3


@router.post("/invoke")
async def invoke_assistant_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    return await invoke_runtime_v3(_with_v3_runtime_mode(payload))


@router.post("/stream")
async def stream_assistant_v3(payload: AssistantV2InvokePayload) -> StreamingResponse:
    return await stream_runtime_v3(_with_v3_runtime_mode(payload))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/interfaces/api/runtime_v3.py src/interfaces/api/assistant_v3.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py
git commit -m "refactor(v3): extract shared runtime entrypoints"
```

### Task 2: Add Explicit Legacy Fallback Controls to the v3 Runtime

**Files:**
- Modify: `src/config/settings.py`
- Modify: `src/interfaces/api/runtime_v3.py`
- Test: `tests/unit/test_server_v3.py`

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace

import pytest

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.runtime_v3 import invoke_runtime_v3


@pytest.mark.asyncio
async def test_runtime_v3_uses_legacy_fallback_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.interfaces.api.runtime_v3.get_settings",
        lambda: SimpleNamespace(v3_legacy_fallback_enabled=True),
    )

    async def failing_v3(payload):
        _ = payload
        raise RuntimeError("v3 broke")

    async def fake_legacy(payload):
        return {"status": "final", "session_id": payload.session_id, "response": "legacy ok"}

    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_primary_v3", failing_v3)
    monkeypatch.setattr("src.interfaces.api.runtime_v3._invoke_legacy_fallback", fake_legacy)

    payload = AssistantV2InvokePayload(session_id="sess-fallback-1", text="胸痛")
    response = await invoke_runtime_v3(payload)

    assert response.status_code == 200
    assert response.body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_v3.py::test_runtime_v3_uses_legacy_fallback_when_enabled -v`
Expected: FAIL because runtime_v3 has no fallback hooks or setting.

- [ ] **Step 3: Write minimal implementation**

```python
# src/config/settings.py
    v3_legacy_fallback_enabled: bool = Field(
        default=True,
        description="Allow v3 runtime to fall back to legacy graph on coordinator failure",
    )
```

```python
# src/interfaces/api/runtime_v3.py
from fastapi.responses import JSONResponse
from src.chains.triage_chain import invoke_chain
from src.config.settings import get_settings


async def _invoke_primary_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    return await _invoke_v3_task_coordinator(
        payload,
        request_id=(payload.request_id or "").strip() or "req-missing",
        session_id=(payload.session_id or "").strip() or "sess-missing",
        trace_id=(payload.trace_id or "").strip() or "trace-missing",
    )


async def _invoke_legacy_fallback(payload: AssistantV2InvokePayload) -> dict[str, object]:
    return await invoke_chain(
        session_id=(payload.session_id or "").strip() or "sess-missing",
        text=payload.text,
        image_base64=payload.image_base64,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
    )


async def invoke_runtime_v3(payload: AssistantV2InvokePayload) -> JSONResponse:
    settings = get_settings()
    try:
        return await _invoke_primary_v3(payload)
    except Exception:
        if not settings.v3_legacy_fallback_enabled:
            raise
        fallback = await _invoke_legacy_fallback(payload)
        return JSONResponse(status_code=200, content=fallback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_v3.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py src/interfaces/api/runtime_v3.py tests/unit/test_server_v3.py
git commit -m "feat(v3): add explicit legacy fallback control"
```

### Task 3: Replace the Public `/assistant/*` Surface with a v3 Compatibility Adapter

**Files:**
- Create: `src/interfaces/api/assistant_compat.py`
- Modify: `src/server.py`
- Modify: `tests/unit/test_server.py`
- Modify: `tests/unit/test_server_v3_stream.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from src.server import app


def test_assistant_invoke_returns_langserve_compatible_envelope(monkeypatch) -> None:
    client = TestClient(app)

    async def fake_v3(payload):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200,
            content={
                "status": "final",
                "session_id": payload.session_id,
                "response": "compat ok",
            },
        )

    monkeypatch.setattr("src.interfaces.api.assistant_compat.invoke_runtime_v3", fake_v3)

    response = client.post(
        "/assistant/invoke",
        json={"input": {"session_id": "sess-compat-1", "text": "头痛"}},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["output"]["status"] == "final"
    assert body["output"]["response"] == "compat ok"
    assert body["metadata"]["runtime_mode"] == "v3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server.py::test_assistant_invoke_returns_langserve_compatible_envelope -v`
Expected: FAIL because `/assistant/invoke` is still owned by LangServe.

- [ ] **Step 3: Write minimal implementation**

```python
# src/interfaces/api/assistant_compat.py
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.interfaces.api.assistant_v2 import AssistantV2InvokePayload
from src.interfaces.api.runtime_v3 import invoke_runtime_v3, stream_runtime_v3

router = APIRouter(prefix="/assistant", tags=["assistant-compat"])


class AssistantCompatEnvelope(BaseModel):
    input: AssistantV2InvokePayload


@router.post("/invoke")
async def invoke_assistant_compat(payload: AssistantCompatEnvelope) -> JSONResponse:
    response = await invoke_runtime_v3(payload.input)
    body = json.loads(response.body.decode("utf-8"))
    return JSONResponse(status_code=response.status_code, content={"output": body, "metadata": {"runtime_mode": "v3"}})


@router.post("/stream")
async def stream_assistant_compat(payload: AssistantCompatEnvelope) -> StreamingResponse:
    return await stream_runtime_v3(payload.input)
```

```python
# src/server.py
from .interfaces.api.assistant_compat import router as assistant_compat_router

app.include_router(assistant_compat_router)
# Remove: add_routes(app, cast(Any, chain), path="/assistant", input_type=dict, output_type=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server.py tests/unit/test_server_v3_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/interfaces/api/assistant_compat.py src/server.py tests/unit/test_server.py tests/unit/test_server_v3_stream.py
git commit -m "feat(api): route public assistant endpoints through v3 compatibility adapter"
```

### Task 4: Lock the New Default Route with Regression Coverage

**Files:**
- Modify: `tests/unit/test_server_v2.py`
- Modify: `tests/unit/test_server_v3.py`
- Modify: `tests/integration/test_shadow_compare_v3.py`

- [ ] **Step 1: Write the failing test**

```python
def test_assistant_invoke_and_v3_invoke_return_same_status(monkeypatch, client) -> None:
    payload = {"session_id": "sess-regression-1", "text": "持续咳嗽两周"}

    legacy = client.post("/assistant/invoke", json={"input": payload}, headers={"Content-Type": "application/json"})
    v3 = client.post("/assistant/v3/invoke", json=payload, headers={"Content-Type": "application/json"})

    assert legacy.status_code == 200
    assert v3.status_code == 200
    assert legacy.json()["output"]["status"] == v3.json()["status"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_v2.py tests/unit/test_server_v3.py tests/integration/test_shadow_compare_v3.py -v`
Expected: FAIL until `/assistant/invoke` and `/assistant/v3/invoke` share the same default path.

- [ ] **Step 3: Write minimal implementation**

```python
# tests/unit/test_server_v2.py
def test_assistant_invoke_delegates_to_v3_default_runtime(...):
    ...
```

```python
# tests/unit/test_server_v3.py
def test_assistant_invoke_and_v3_invoke_return_same_status(...):
    ...
```

```python
# tests/integration/test_shadow_compare_v3.py
def test_shadow_compare_v3_uses_legacy_vs_default_v3_paths(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_v2.py tests/unit/test_server_v3.py tests/integration/test_shadow_compare_v3.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_server_v2.py tests/unit/test_server_v3.py tests/integration/test_shadow_compare_v3.py
git commit -m "test(v3): lock default route cutover behavior"
```
