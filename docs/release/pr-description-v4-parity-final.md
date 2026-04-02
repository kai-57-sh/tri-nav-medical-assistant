# PR: TriNav V4 Claude-Parity 重构收口

## 1. 背景与目标

本 PR 汇总 TriNav 面向 Claude-Code 架构水准对齐的重构收口结果。

目标:
1. 在保留 TriNav 医疗咨询、问诊推荐、循证检索、导诊导航能力前提下，完成平台内核化升级。
2. 形成统一 runtime + tool/policy/state/release gate 的可治理架构。
3. 清理工程质量阻塞项，建立可持续发布门禁。

## 2. 本次变更范围

### 2.1 运行时与协议层

1. RuntimeKernel 单入口执行与统一错误语义。
2. assistant v2/v3 协议层与执行层解耦（v3 作为协议适配层）。

### 2.2 工具/权限/安全治理

1. 增加 ToolGateway，统一工具调用前置策略检查。
2. 增加 PermissionEngine，输出可审计 decision。
3. 强化 medical safety/output guard，形成医疗安全三层闭环（前置权限 + 过程审计 + 后置安全）。

### 2.3 状态持久化与恢复

1. runtime event/snapshot Redis-first 仓储。
2. replay/resume 服务化并接入 runtime admin。

### 2.4 发布治理

1. v4 canary gate 门禁（red-flag miss rate、p95 latency）。
2. 切流 checklist 与回滚条件固化。

### 2.5 工程质量收口

1. mypy 类型债务清零。
2. ruff 通过。
3. 关键回归通过。

## 3. 架构影响评估

- RuntimeKernel: `yes`
- capability 执行链路: `yes`
- tool/policy/state/release gate: `yes`
- 对外兼容性: 保留 `/assistant/invoke` 与 v2/v3 协议契约

## 4. 医疗安全影响

1. 红旗风险和高风险输出治理链路增强。
2. 对敏感工具调用增加 consent 与策略审计。
3. 异常路径保持保守降级（避免误导医疗建议）。

## 5. 关键提交（节选）

1. `5f35e81` fix(types): drive mypy debt to zero across models and llm service
2. `2c66e44` fix(types): harden service/repository typing and graph node bindings
3. `e933a58` fix(types): tighten runtime and api typing contracts
4. `d167168` feat(release): add v4 canary gate with shadow-based blocking thresholds
5. `c58b3b1` docs(v4): publish final parity report and cutover evidence
6. `5a99ba4` docs(release): add PR body and release announcement templates

## 6. 验证结果

### 6.1 静态检查

1. `mypy src` -> `Success: no issues found in 116 source files`
2. `uvx ruff check src tests` -> `All checks passed`

### 6.2 回归测试

执行命令:

```bash
QWEN_API_KEY=test-key pytest -q tests/unit/test_services/test_llm_service.py tests/unit/test_nodes/test_session_loader.py tests/unit/test_nodes/test_red_flag_detector.py tests/unit/test_services/test_redis_service.py tests/unit/test_models/test_symptom_schema.py tests/unit/test_models/test_triage_assessment.py tests/unit/test_models/test_red_flag_rule.py tests/unit/test_models/test_navigation_result.py tests/unit/test_config/test_settings_v2.py tests/unit/test_v3/test_capabilities_v3.py tests/unit/test_v3/test_real_capabilities.py tests/unit/test_v3/test_redis_event_store.py tests/unit/test_platform/test_runtime_kernel.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/unit/test_server_v3_runtime_admin.py tests/integration/test_shadow_compare.py tests/integration/test_shadow_compare_v3.py
```

结果:
- `228 passed`

## 7. 灰度与回滚计划

灰度建议:
1. `1% -> 5% -> 20% -> 50% -> 100%`

门禁阈值:
1. `red_flag_miss_rate <= 0.01`
2. `p95_ms <= 6000`

回滚条件:
1. 医疗安全告警异常上升。
2. gate 连续两个观测窗口失败。
3. 核心接口错误率/时延超过 SLO 且无法在窗口内恢复。

## 8. Reviewer 关注点

1. RuntimeKernel 与 v2/v3 协议边界是否保持清晰。
2. ToolGateway/PermissionEngine 是否覆盖敏感工具路径并有完整审计证据。
3. replay/resume 在 Redis 波动场景的降级行为是否符合预期。

## 9. 关联文档

1. `docs/superpowers/2026-04-03-trinav-claude-parity-final-report.md`
2. `docs/release/v4-cutover-checklist.md`
3. `docs/superpowers/specs/2026-04-02-trinav-v3-claude-parity-design.md`
4. `docs/superpowers/plans/2026-04-02-trinav-v4-claude-parity-implementation-plan.md`
