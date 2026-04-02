# TriNav vs Claude-Code 差距审计与完全重构蓝图

- 日期: 2026-04-02
- 目标仓库: `/AII-wuqi/AII_home/fq_775/project-dev/TriNav`
- 对标基线: `/AII-wuqi/AII_home/fq_775/project-dev/claude-code-source`
- 结论定位: 在保留医疗咨询/问诊推荐能力的前提下，将 TriNav 从“医疗流程系统”升级为“医疗垂直 Agent 平台”

## 1. 当前基线（基于代码事实）

### 1.1 Claude-Code 的平台成熟特征

1. 统一查询内核与会话状态循环
- `QueryEngine` 配置面覆盖 tools/commands/mcp/agents/permissions/budget/json schema/streaming 等核心维度，且一会话多轮复用状态。
- 证据: `claude-code-source/src/QueryEngine.ts:130-237`

2. 工具体系是“平台一级对象”
- 具备大量内建工具，并通过 feature flag 动态装配；工具本身包含任务、计划模式、工作树、MCP、LSP、技能等平台能力。
- 证据: `claude-code-source/src/tools.ts:3-220`

3. 任务生命周期建模完整
- 显式 TaskType/TaskStatus/terminal state/输出文件/超时与 kill 协议。
- 证据: `claude-code-source/src/Task.ts:6-125`

4. 权限决策链成熟
- 支持 allow/deny/ask、自动分类器、协同代理权限处理、交互回调、拒绝审计。
- 证据: `claude-code-source/src/hooks/useCanUseTool.tsx:27-182`

5. 事件/传输可靠性工程化
- HybridTransport 拥有 batching、重试、退避、背压、close drain、失败诊断。
- 证据: `claude-code-source/src/cli/transports/HybridTransport.ts:12-220`

6. SDK 事件契约标准化
- Hook 事件集合完整，覆盖任务、权限、会话、文件、工作树等。
- 证据: `claude-code-source/src/entrypoints/sdk/coreTypes.ts:25-62`

### 1.2 TriNav 当前状态（含本轮已完成能力）

1. v3 入口已具备，但仍复用 v2 外壳
- v3 API 当前通过 metadata 注入 runtime_mode 后委托 v2 路由。
- 证据: `src/interfaces/api/assistant_v3.py:1-32`

2. v3 任务编排链路已建立
- `assistant_v2` 已可在开关控制下走 v3 task coordinator 路径，并带 runtime events、trace、medical guard。
- 证据: `src/interfaces/api/assistant_v2.py:138-360`

3. runtime 插件机制已落地（初级）
- before/after hook、注册校验、故障隔离已具备。
- 证据: `src/core/plugins/registry.py:13-104`

4. 会话 replay/resume/doctor/plugins 管理接口已落地
- 证据: `src/interfaces/api/runtime_admin_v3.py:38-113`

5. 仍存在关键短板
- v3 consultation/triage/response 等能力仍是 stub（固定或模板化输出）。
- 证据:
  - `src/capabilities/consultation/capability.py:13-57`
  - `src/capabilities/triage/capability.py:13-61`
  - `src/capabilities/response/capability.py:13-62`
- task coordinator 仍为“串行 + required/optional”最小实现。
- 证据: `src/core/coordinator/task_coordinator.py:23-53`
- snapshot/event 默认内存存储，重启后不可恢复。
- 证据:
  - `src/core/state/event_store.py:9-52`
  - `src/core/state/session_snapshot_store.py:9-31`

## 2. 差距矩阵（对齐到 Claude-Code 水准）

| 维度 | Claude-Code 现状 | TriNav 现状 | 差距等级 | 重构要求 |
|---|---|---|---|---|
| Runtime 内核 | 统一 QueryEngine 处理多轮、工具循环、预算、权限 | v2/v3 双路并存，v3 仍是受控旁路 | 高 | 建立单一 RuntimeKernel，v1/v2/v3 仅为协议层 |
| 任务模型 | Task 类型、状态、终态、输出、kill 完整 | TaskCoordinator 仅顺序执行与失败中断 | 高 | 引入 Task DAG/并发策略/可取消与重试语义 |
| 工具平台 | 工具池 + 动态装配 + plan/worktree/MCP/LSP | 工具有 registry，但缺统一 tool lifecycle | 高 | 建立 ToolGateway + ToolPolicy + ToolAudit |
| 权限治理 | allow/deny/ask + 自动分类 + 交互/协同回调 | 医疗安全主要在输出后置 guard | 高 | 构建“前置权限 + 中途审计 + 后置安全”三层 |
| 会话恢复 | Session 生命周期与恢复较完整 | replay/resume 接口已加，但底层默认内存态 | 高 | 全量切换 Redis/持久化快照 + 事件回放 |
| 事件契约 | SDK 事件集合标准化 | runtime_events 有，但语义粒度不足 | 中高 | 扩展事件 taxonomy，接入 trace/span/cost |
| 传输可靠性 | batching/退避/背压/drain | API 侧稳定，流式传输治理较轻 | 中 | 增加 SSE 重连、幂等 final、拥塞保护 |
| 插件生态 | 插件安装/CLI 命令/平台集成 | 仅内建插件，缺插件包协议 | 中高 | 定义 Plugin Manifest 与版本兼容策略 |
| 多 Agent 协作 | local/remote/in-process teammate 体系 | 无多 agent 运行时 | 中 | 医疗场景采用“单主控 + 专业子代理”可选模型 |
| 可观测性 | analytics + diagnostics + usage 体系 | 基础 runtime events 与 metrics | 中高 | 增强 SLO 仪表盘、失败归因、病例回放 |
| 发布治理 | feature flags + 分层能力开关 | 已有 v2/v3 开关与 shadow compare | 中 | 强化 canary gate + 自动回滚 |
| 医疗安全合规 | 平台策略治理成熟 | medical_guard 已落地但规则较浅 | 中高 | 引入分级医疗风险规则与审核证据链 |

## 3. TriNav 完全重构目标架构（V4）

```text
interfaces/
  api/
    assistant_v1_compat.py
    assistant_v2.py
    assistant_v3.py
    runtime_admin_v3.py
  stream/
    sse_contract.py

platform/
  runtime/
    kernel.py
    turn_loop.py
    task_graph.py
    context.py
  tooling/
    gateway.py
    registry.py
    audit.py
  policy/
    permission_engine.py
    medical_safety_engine.py
    policy_trace.py
  state/
    session_repository.py
    event_repository.py
    snapshot_repository.py
    replay_service.py
  observability/
    tracer.py
    metrics.py
    diagnostics.py

medical/
  capabilities/
    consultation/
    triage/
    clarification/
    evidence/
    navigation/
    response/
  workflows/
    legacy_triage_adapter.py

release/
  shadow/
  canary/
  rollback/
```

### 3.1 设计约束

1. 对外 API 契约稳定
- `/assistant/invoke` 兼容保留，新增能力走 v2/v3。

2. 医疗安全优先于生成质量
- 任一环节触发高风险规则，必须进入“保守响应 + 就医建议”。

3. 双轨迁移
- legacy 图保持可运行，V4 内核按 capability 分批替换。

4. 观测先行
- 新链路必须具备 trace_id、task_id、policy_decision_id、evidence_id。

## 4. 医疗特色保真映射

| 现有能力 | 现状模块 | V4 模块 | 保真要求 |
|---|---|---|---|
| 医疗咨询 | legacy chain + response | `medical/capabilities/consultation` | 解释性与谨慎措辞不下降 |
| 问诊推荐/分诊 | triage_graph + rules + llm | `medical/capabilities/triage` | 红旗召回率不下降，误分诊可追踪 |
| 循证检索 | NCBI nodes | `medical/capabilities/evidence` | 引文可追溯，失败可降级 |
| 导航导诊 | amap/weather nodes | `medical/capabilities/navigation` | 医院推荐可解释，路线失败可回退 |
| 医疗安全 | medical_guard | `platform/policy/medical_safety_engine` | 输出误导率持续下降 |

## 5. 分阶段重构方案（可落地）

### Phase 0: 基线冻结（1 周）

1. 冻结 golden cases 与 shadow compare 样本集
2. 明确当前 v2/v3 的 SLO 基线（P50/P95、错误率、红旗漏判）
3. 输出《兼容性清单》：字段、状态码、SSE 时序、异常语义

退出条件:
- baseline 报告可复现
- 黄金病例门禁可自动跑通

### Phase 1: RuntimeKernel 单核化（2 周）

1. 新建 `platform/runtime/kernel.py`，统一 invoke/stream 执行入口
2. API 层仅做协议解析与响应编排，不再承载编排细节
3. 将 `QueryEngine` 与 `TaskCoordinator` 合并为统一 turn loop

退出条件:
- v2/v3 共享同一 kernel（仅 protocol adapter 不同）
- 行为回归通过

### Phase 2: 医疗能力 capability 化（2-3 周）

1. 将 v3 stub capability 替换为真实实现
2. 每个 capability 明确 plan/run/fallback 及输入输出 schema
3. legacy graph 作为 capability adapter 存在，逐步退出

退出条件:
- consultation/triage/evidence/navigation/response 不再 stub
- capability 级单测覆盖率 >= 90%

### Phase 3: 工具与权限治理（2 周）

1. ToolGateway：统一调用 amap/ncbi/weather/vision
2. PermissionEngine：调用前规则审查（地域、频控、敏感字段）
3. PolicyTrace：每次拒绝/放行记录证据

退出条件:
- 工具调用均有 policy decision log
- 高风险请求可被前置拦截

### Phase 4: 持久化会话与恢复（1-2 周）

1. 事件仓储默认 Redis（内存仅测试环境）
2. snapshot 与 event log 双写
3. replay/resume 接口从“调试”升级为“生产可用”

退出条件:
- 重启后可 replay 最近 N 会话
- resume 成功率 >= 99%

### Phase 5: 可观测与运营化（1-2 周）

1. 引入 trace span：capability/tool/policy 三层
2. 增加 runtime 失败归因标签（planner/executor/tool/policy）
3. 增加医疗 KPI 看板：红旗召回、分诊一致性、导航成功率

退出条件:
- 每次失败可定位到模块/阶段
- 日常巡检有自动报告

### Phase 6: 灰度与发布治理（1-2 周）

1. 扩展 shadow compare 为版本门禁
2. canary 比例: 1% -> 5% -> 20% -> 50% -> 100%
3. 任一红线越界自动回滚

退出条件:
- canary 策略自动化
- 回滚演练通过

## 6. 关键验收指标（对齐“成熟 Agent 平台”）

### 6.1 平台工程指标

1. Runtime 可用性 >= 99.9%
2. 会话恢复成功率 >= 99%
3. SSE 终态完整率（含 [DONE]）>= 99.99%
4. 关键路径 P95（非图像）<= 6s

### 6.2 医疗业务指标

1. 红旗漏判率较当前下降 >= 30%
2. 不安全建议拦截率 >= 99%
3. 导诊成功率（有定位）>= 95%
4. 证据检索失败时的可解释降级覆盖率 = 100%

### 6.3 研发治理指标

1. 关键模块 mypy 严格模式通过
2. 变更必须绑定测试（单测 + 集成 + golden case）
3. 发布前必须通过 shadow compare gate

## 7. 组织与实施建议

1. 建议采用“三线并行”
- 内核线: runtime/tool/policy/state
- 医疗线: capability 迁移与指标优化
- 发布线: shadow/canary/observability

2. 每周节奏
- 周一基线审计
- 周二到周四实现 + 评测
- 周五灰度演练与回滚演练

3. 版本策略
- `v3.x` 继续承载迁移
- `v4.0` 作为单核 runtime 的里程碑版本

## 8. 对用户需求的直接回应

你要的“保持 TriNav 医疗特色 + 向 claude-code 水准对齐”可以落地，但前提是将目标定义为:

1. 对齐其“平台工程成熟度”，而不是复制其“通用代码代理产品形态”
2. 保留并强化医疗垂直能力（咨询、分诊、导诊、循证、安全）
3. 以双轨迁移和强门禁推进，避免一次性重写造成临床风险与线上不稳定

该蓝图与当前代码状态连续，不推倒重来，可直接进入分阶段执行。
