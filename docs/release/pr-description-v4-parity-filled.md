# PR Description (Filled Example) - TriNav V4 Claude-Parity

## 1. 背景

- 目标: 完成 TriNav 对齐 claude-code 平台成熟度的关键重构收口
- 关联文档:
1. `docs/superpowers/2026-04-03-trinav-claude-parity-final-report.md`
2. `docs/release/v4-cutover-checklist.md`

## 2. 本次变更

- 变更类型: `feat/fix/docs/chore`（平台级重构）
- 涉及模块:
1. runtime kernel
2. tooling/policy
3. state replay/resume
4. canary gate
5. 类型治理与质量门禁

核心改动:
1. 单核运行时与 API 协议适配完成
2. tool permission + medical safety 治理链路贯通
3. Redis-first 状态仓储与 replay/resume 生产化
4. 发布门禁、回滚策略与切流清单完善
5. 全量 mypy 债务清零

## 3. 架构影响

- RuntimeKernel: `yes`
- capability 链路: `yes`
- tool/policy/state/release gate: `yes`
- 向后兼容: 保留 `/assistant/invoke` 与 v2/v3 契约，v3 作为协议适配层

## 4. 医疗安全影响

- 红旗识别逻辑: 强化
- medical safety engine/output guard: 强化
- 风险评估: 低到中（由 canary gate + 回滚策略托底）

## 5. 验证与结果

### 5.1 静态检查

- `uvx ruff check src tests` -> PASS
- `mypy src` -> PASS (`Success: no issues found in 116 source files`)

### 5.2 测试

执行命令:

```bash
QWEN_API_KEY=test-key pytest -q tests/unit/test_services/test_llm_service.py tests/unit/test_nodes/test_session_loader.py tests/unit/test_nodes/test_red_flag_detector.py tests/unit/test_services/test_redis_service.py tests/unit/test_models/test_symptom_schema.py tests/unit/test_models/test_triage_assessment.py tests/unit/test_models/test_red_flag_rule.py tests/unit/test_models/test_navigation_result.py tests/unit/test_config/test_settings_v2.py tests/unit/test_v3/test_capabilities_v3.py tests/unit/test_v3/test_real_capabilities.py tests/unit/test_v3/test_redis_event_store.py tests/unit/test_platform/test_runtime_kernel.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/unit/test_server_v3_runtime_admin.py tests/integration/test_shadow_compare.py tests/integration/test_shadow_compare_v3.py
```

结果:
- PASS
- 228 passed

## 6. 发布与回滚

- Feature flags:
1. `V4_RUNTIME_ENABLED=true`
2. `V4_CANARY_ENABLED=true`
3. `V4_GATE_MAX_RED_FLAG_MISS_RATE=0.01`
4. `V4_GATE_MAX_P95_MS=6000`

- 灰度策略: `1% -> 5% -> 20% -> 50% -> 100%`
- 回滚条件:
1. 医疗安全告警异常上升
2. gate 连续两窗口失败
3. 核心接口 SLO 越界且无法恢复

## 7. Reviewer 关注点

1. RuntimeKernel 与 assistant_v2/v3 的协议边界是否清晰
2. ToolGateway/PermissionEngine 对敏感工具调用是否可审计
3. replay/resume 在 Redis 异常时的降级与一致性

## 8. 附录

关键提交（节选）:
1. `5f35e81` fix(types): drive mypy debt to zero across models and llm service
2. `2c66e44` fix(types): harden service/repository typing and graph node bindings
3. `e933a58` fix(types): tighten runtime and api typing contracts
4. `c58b3b1` docs(v4): publish final parity report and cutover evidence
