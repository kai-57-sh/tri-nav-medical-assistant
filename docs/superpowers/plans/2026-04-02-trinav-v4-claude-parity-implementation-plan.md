# TriNav V4 Claude-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不丢失 TriNav 医疗咨询、问诊推荐、导诊导航特色能力的前提下，完成 Runtime 单核化与平台化重构，使工程成熟度对齐 claude-code。

**Architecture:** 采用“接口层协议适配 + 平台层统一运行时 + 医疗能力层可插拔 capability”的三层结构。v1/v2/v3 只保留协议差异，执行统一走 RuntimeKernel。通过双轨迁移（legacy adapter + v4 capability）保证线上安全。

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Redis, LangGraph, Pytest, Ruff, mypy

---

## 文件结构与职责冻结

### 新增目录（V4 平台层）

- `src/platform/runtime/kernel.py`: 统一运行时入口，管理 turn loop 与 task graph 执行。
- `src/platform/runtime/turn_loop.py`: 单轮请求生命周期（plan -> execute -> policy -> finalize）。
- `src/platform/runtime/task_graph.py`: task DAG 定义、并发执行、重试与取消语义。
- `src/platform/tooling/gateway.py`: 医疗外部工具统一调用入口（Amap/NCBI/Weather/Vision）。
- `src/platform/policy/permission_engine.py`: 工具调用前置权限判定。
- `src/platform/policy/medical_safety_engine.py`: 输出安全后置引擎（整合 medical_guard）。
- `src/platform/state/session_repository.py`: 会话主存取仓储。
- `src/platform/state/event_repository.py`: runtime 事件仓储（Redis 默认，内存仅测试）。
- `src/platform/state/replay_service.py`: replay/resume 核心服务。
- `src/platform/observability/tracer.py`: 运行时链路追踪。

### 既有文件改造

- `src/interfaces/api/assistant_v2.py`: 从“内联编排”改为调用 RuntimeKernel。
- `src/interfaces/api/assistant_v3.py`: 仅做 v3 协议适配与开关控制。
- `src/interfaces/api/runtime_admin_v3.py`: 改为调用 replay_service 与 state repositories。
- `src/core/coordinator/task_coordinator.py`: 逐步降级为 legacy 兼容层。
- `src/capabilities/*/capability.py`: 用真实医疗逻辑替换 stub。
- `src/config/settings.py`: 增加 v4 开关与发布门禁参数。

### 测试目录新增

- `tests/unit/test_platform/test_runtime_kernel.py`
- `tests/unit/test_platform/test_task_graph.py`
- `tests/unit/test_platform/test_permission_engine.py`
- `tests/unit/test_platform/test_replay_service.py`
- `tests/integration/test_v4_runtime_flow.py`
- `tests/integration/test_v4_shadow_gate.py`

---

### Task 1: RuntimeKernel 单核入口

**Files:**
- Create: `src/platform/runtime/kernel.py`
- Create: `src/platform/runtime/turn_loop.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Test: `tests/unit/test_platform/test_runtime_kernel.py`

- [ ] **Step 1: 写失败测试（v2 走 kernel）**

```python
# tests/unit/test_platform/test_runtime_kernel.py
async def test_assistant_v2_delegates_to_runtime_kernel(client, monkeypatch):
    called = {"value": False}

    class FakeKernel:
        async def invoke(self, payload):
            called["value"] = True
            return {"status": "final", "response": "ok", "session_id": payload.session_id, "trace_id": "t1"}

    monkeypatch.setattr("src.interfaces.api.assistant_v2.build_runtime_kernel", lambda: FakeKernel())

    resp = await client.post("/assistant/v2/invoke", json={"text": "头痛"})
    assert resp.status_code == 200
    assert called["value"] is True
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_platform/test_runtime_kernel.py::test_assistant_v2_delegates_to_runtime_kernel`
Expected: FAIL（`build_runtime_kernel` 或 `RuntimeKernel` 未定义）

- [ ] **Step 3: 写最小实现**

```python
# src/platform/runtime/kernel.py
class RuntimeKernel:
    async def invoke(self, payload):
        raise NotImplementedError
```

```python
# src/interfaces/api/assistant_v2.py
from src.platform.runtime.kernel import RuntimeKernel

def build_runtime_kernel() -> RuntimeKernel:
    return RuntimeKernel()
```

- [ ] **Step 4: 补全 v2 invoke 调用路径**

```python
kernel = build_runtime_kernel()
result = await kernel.invoke(payload)
return JSONResponse(status_code=200 if result.get("status") != "error" else 503, content=result)
```

- [ ] **Step 5: 运行单测验证通过**

Run: `pytest -q tests/unit/test_platform/test_runtime_kernel.py`
Expected: PASS

- [ ] **Step 6: 运行回归最小集合**

Run: `pytest -q tests/unit/test_server_v2.py tests/unit/test_server_v2_stream.py`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/platform/runtime/kernel.py src/platform/runtime/turn_loop.py src/interfaces/api/assistant_v2.py tests/unit/test_platform/test_runtime_kernel.py
git commit -m "feat(v4-runtime): introduce RuntimeKernel and route assistant_v2 invoke through kernel"
```

### Task 2: v3 协议适配瘦身

**Files:**
- Modify: `src/interfaces/api/assistant_v3.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Test: `tests/unit/test_server_v3.py`

- [ ] **Step 1: 写失败测试（v3 只做协议适配）**

```python
def test_assistant_v3_sets_runtime_mode_and_calls_v2(client, monkeypatch):
    captured = {}

    async def fake_invoke(payload):
        captured["metadata"] = payload.metadata
        return JSONResponse(status_code=200, content={"status": "final", "response": "ok", "session_id": "s1", "trace_id": "t1"})

    monkeypatch.setattr("src.interfaces.api.assistant_v3.invoke_assistant_v2", fake_invoke)
    resp = client.post("/assistant/v3/invoke", json={"text": "腹痛"})
    assert resp.status_code == 200
    assert captured["metadata"]["runtime_mode"] == "v3"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_server_v3.py::test_assistant_v3_sets_runtime_mode_and_calls_v2`
Expected: FAIL（行为不一致）

- [ ] **Step 3: 调整实现**

```python
# 保留 _with_v3_runtime_mode
# 禁止在 assistant_v3 中出现任何 capability/task 编排逻辑
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest -q tests/unit/test_server_v3.py`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/api/assistant_v3.py src/interfaces/api/assistant_v2.py tests/unit/test_server_v3.py
git commit -m "refactor(v3-api): keep v3 as protocol adapter over unified runtime kernel"
```

### Task 3: v3 capability 去 stub 化（医疗核心）

**Files:**
- Modify: `src/capabilities/consultation/capability.py`
- Modify: `src/capabilities/triage/capability.py`
- Modify: `src/capabilities/evidence/capability.py`
- Modify: `src/capabilities/navigation/capability.py`
- Modify: `src/capabilities/response/capability.py`
- Test: `tests/unit/test_v3/test_real_capabilities.py`

- [ ] **Step 1: 写失败测试（triage 不再固定 ROUTINE）**

```python
async def test_triage_capability_not_constant_routine():
    cap = TriageCapability()
    emergency_ctx = ExecutionContext(request_id="r1", session_id="s1", text="胸痛 大汗 呼吸困难", metadata={})
    result = await cap.run(emergency_ctx, {"enabled": True})
    assert result.payload["triage_level"] in {"EMERGENCY", "URGENT"}
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_v3/test_real_capabilities.py::test_triage_capability_not_constant_routine`
Expected: FAIL（当前固定 ROUTINE）

- [ ] **Step 3: 接入真实能力源**

```python
# consultation: 复用 clinical_extractor 输出摘要
# triage: 复用 red_flag_detector + triage_classifier + triage_merger
# evidence: 复用 ncbi_query_builder + ncbi_retriever_tool
# navigation: 复用 navigator + weather_fetcher
# response: 复用 reasoning_verifier + response_composer
```

- [ ] **Step 4: 加入 fallback 降级策略**

```python
return CapabilityResult(
    name=self.name,
    success=False,
    payload={"status": "degraded", "response": "服务繁忙，请尽快线下就医"},
    errors=[reason],
)
```

- [ ] **Step 5: 运行能力单测**

Run: `pytest -q tests/unit/test_v3/test_real_capabilities.py`
Expected: PASS

- [ ] **Step 6: 运行集成回归**

Run: `pytest -q tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/evals/test_golden_cases.py`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/capabilities/ src/chains/nodes/ tests/unit/test_v3/test_real_capabilities.py
git commit -m "feat(v4-medical): replace v3 stub capabilities with real medical capability pipeline"
```

### Task 4: ToolGateway + PermissionEngine

**Files:**
- Create: `src/platform/tooling/gateway.py`
- Create: `src/platform/policy/permission_engine.py`
- Modify: `src/core/plugins/registry.py`
- Test: `tests/unit/test_platform/test_permission_engine.py`

- [ ] **Step 1: 写失败测试（高风险工具调用被拒绝）**

```python
def test_permission_engine_denies_sensitive_tool_without_context():
    engine = PermissionEngine()
    decision = engine.decide(tool_name="vision_tool", payload={"image_base64": "..."}, context={"consent": False})
    assert decision.allow is False
    assert decision.reason == "missing_patient_consent"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_platform/test_permission_engine.py::test_permission_engine_denies_sensitive_tool_without_context`
Expected: FAIL（引擎未实现）

- [ ] **Step 3: 实现权限判定与审计结构**

```python
@dataclass
class PolicyDecision:
    allow: bool
    reason: str
    decision_id: str
```

- [ ] **Step 4: ToolGateway 在执行前调用 PermissionEngine**

```python
decision = self._permission_engine.decide(tool_name, payload, context)
if not decision.allow:
    raise ToolPermissionDenied(decision.reason)
```

- [ ] **Step 5: 运行单测**

Run: `pytest -q tests/unit/test_platform/test_permission_engine.py`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/platform/tooling/gateway.py src/platform/policy/permission_engine.py tests/unit/test_platform/test_permission_engine.py
git commit -m "feat(v4-policy): add ToolGateway and PermissionEngine with decision auditing"
```

### Task 5: 持久化状态仓储替换内存默认

**Files:**
- Create: `src/platform/state/event_repository.py`
- Create: `src/platform/state/snapshot_repository.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Modify: `src/interfaces/api/runtime_admin_v3.py`
- Test: `tests/unit/test_platform/test_state_repository.py`

- [ ] **Step 1: 写失败测试（重建实例后可读到历史事件）**

```python
async def test_event_repository_persists_across_instances(redis_service):
    repo1 = EventRepository(redis_service)
    await repo1.append("s1", {"event_type": "runtime_started"})

    repo2 = EventRepository(redis_service)
    events = await repo2.list("s1")
    assert events[0]["event_type"] == "runtime_started"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_platform/test_state_repository.py::test_event_repository_persists_across_instances`
Expected: FAIL

- [ ] **Step 3: 实现 Redis 默认、内存兜底策略**

```python
if redis_available:
    return RedisEventStore(...)
return InMemoryEventStore(...)
```

- [ ] **Step 4: 替换 assistant_v2 的 `_RUNTIME_EVENT_STORE/_RUNTIME_SNAPSHOT_STORE` 初始化**

```python
_event_repo = build_event_repository()
_snapshot_repo = build_snapshot_repository()
```

- [ ] **Step 5: 运行单测与接口测试**

Run: `pytest -q tests/unit/test_platform/test_state_repository.py tests/unit/test_server_v3_runtime_admin.py`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/platform/state/ src/interfaces/api/assistant_v2.py src/interfaces/api/runtime_admin_v3.py tests/unit/test_platform/test_state_repository.py tests/unit/test_server_v3_runtime_admin.py
git commit -m "feat(v4-state): persist runtime events and snapshots with redis-first repositories"
```

### Task 6: Replay/Resume 生产化

**Files:**
- Create: `src/platform/state/replay_service.py`
- Modify: `src/interfaces/api/runtime_admin_v3.py`
- Test: `tests/unit/test_platform/test_replay_service.py`

- [ ] **Step 1: 写失败测试（replay 返回可继续执行的恢复点）**

```python
async def test_replay_service_returns_resume_cursor():
    service = ReplayService(event_repo=FakeEventRepo(), snapshot_repo=FakeSnapshotRepo())
    replay = await service.replay("s1")
    assert "resume_cursor" in replay
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_platform/test_replay_service.py::test_replay_service_returns_resume_cursor`
Expected: FAIL

- [ ] **Step 3: 实现 replay/resume 语义**

```python
{"session_id": sid, "runtime_events": events, "snapshot": snapshot, "resume_cursor": cursor}
```

- [ ] **Step 4: 调整 runtime_admin_v3 走 service 层**

```python
state = await replay_service.replay(session_id)
return JSONResponse(status_code=200, content=state)
```

- [ ] **Step 5: 运行单测**

Run: `pytest -q tests/unit/test_platform/test_replay_service.py tests/unit/test_server_v3_runtime_admin.py`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/platform/state/replay_service.py src/interfaces/api/runtime_admin_v3.py tests/unit/test_platform/test_replay_service.py tests/unit/test_server_v3_runtime_admin.py
git commit -m "feat(v4-runtime-admin): productionize replay and resume via replay service"
```

### Task 7: 医疗安全引擎化（替代散点后置）

**Files:**
- Create: `src/platform/policy/medical_safety_engine.py`
- Modify: `src/policy/safety/medical_guard.py`
- Modify: `src/interfaces/api/assistant_v2.py`
- Test: `tests/unit/test_policy/test_medical_safety_engine.py`

- [ ] **Step 1: 写失败测试（高风险词命中必须降级输出）**

```python
def test_medical_safety_engine_rewrites_high_risk_output():
    engine = MedicalSafetyEngine()
    result = engine.enforce("不用就医，肯定没事")
    assert "建议尽快就医" in result.text
    assert result.risk_level == "HIGH"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/unit/test_policy/test_medical_safety_engine.py::test_medical_safety_engine_rewrites_high_risk_output`
Expected: FAIL

- [ ] **Step 3: 实现结构化安全结果**

```python
@dataclass
class SafetyResult:
    text: str
    risk_level: str
    matched_rules: list[str]
```

- [ ] **Step 4: assistant_v2/v3 final 输出统一走 MedicalSafetyEngine**

```python
safety = medical_safety_engine.enforce(body["response"])
body["response"] = safety.text
body["safety"] = {"risk_level": safety.risk_level, "matched_rules": safety.matched_rules}
```

- [ ] **Step 5: 运行单测与回归**

Run: `pytest -q tests/unit/test_policy/test_medical_safety_engine.py tests/unit/test_server_v2.py tests/unit/test_server_v3.py`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/platform/policy/medical_safety_engine.py src/policy/safety/medical_guard.py src/interfaces/api/assistant_v2.py tests/unit/test_policy/test_medical_safety_engine.py
git commit -m "feat(v4-safety): add structured medical safety engine and enforce on final output"
```

### Task 8: Shadow/Canary 门禁自动化

**Files:**
- Modify: `tests/integration/test_shadow_compare_v3.py`
- Create: `tests/integration/test_v4_shadow_gate.py`
- Create: `src/release/canary/gate.py`
- Modify: `src/config/settings.py`

- [ ] **Step 1: 写失败测试（门禁阈值不达标禁止放量）**

```python
def test_canary_gate_blocks_when_red_flag_miss_exceeds_threshold():
    gate = CanaryGate(max_red_flag_miss_rate=0.01)
    decision = gate.evaluate({"red_flag_miss_rate": 0.03, "p95_ms": 4100})
    assert decision.allow is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest -q tests/integration/test_v4_shadow_gate.py::test_canary_gate_blocks_when_red_flag_miss_exceeds_threshold`
Expected: FAIL

- [ ] **Step 3: 实现 gate 逻辑与配置项**

```python
v4_canary_enabled: bool = False
v4_gate_max_red_flag_miss_rate: float = 0.01
v4_gate_max_p95_ms: int = 6000
```

- [ ] **Step 4: 运行测试**

Run: `pytest -q tests/integration/test_v4_shadow_gate.py tests/integration/test_shadow_compare_v3.py`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/release/canary/gate.py src/config/settings.py tests/integration/test_v4_shadow_gate.py tests/integration/test_shadow_compare_v3.py
git commit -m "feat(release): add v4 canary gate with shadow-based blocking thresholds"
```

### Task 9: 全量回归与灰度就绪清单

**Files:**
- Modify: `docs/DEVELOPER_GUIDE.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/frontend_contract/events_v3.md`
- Create: `docs/release/v4-cutover-checklist.md`

- [ ] **Step 1: 更新文档中的 v4 执行路径与配置示例**

```markdown
- v4_runtime_enabled=true
- v4_canary_enabled=true
- v4_gate_max_red_flag_miss_rate=0.01
```

- [ ] **Step 2: 执行全量回归**

Run:
`pytest -q tests/unit/test_server_v2.py tests/unit/test_server_v2_stream.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/unit/test_server_v3_runtime_admin.py tests/unit/test_v3 tests/integration/test_shadow_compare.py tests/integration/test_shadow_compare_v3.py tests/evals/test_golden_cases.py`

Expected: 全部 PASS

- [ ] **Step 3: 运行代码质量检查**

Run:
- `ruff check src tests`
- `mypy src`

Expected: 无阻断错误

- [ ] **Step 4: 提交**

```bash
git add docs/DEVELOPER_GUIDE.md docs/API_REFERENCE.md docs/frontend_contract/events_v3.md docs/release/v4-cutover-checklist.md
git commit -m "docs(v4): add runtime cutover checklist and update api/events contracts"
```

---

## 计划自检结果

1. Spec 覆盖检查
- Runtime 单核化: Task 1-2
- capability 去 stub 化: Task 3
- 工具/权限治理: Task 4, Task 7
- 持久化与恢复: Task 5-6
- 发布门禁: Task 8-9
- 医疗特色保真: Task 3 + Task 7

2. 占位符扫描
- 未使用 TBD/TODO/implement later 等占位描述。

3. 类型一致性
- `RuntimeKernel.invoke`、`PolicyDecision`、`SafetyResult`、`ReplayService` 在任务中命名一致。

