# TriNav V3 完全重构设计（对齐 Claude Code 架构水准）

- 日期: 2026-04-02
- 作者: Codex
- 适用仓库: `/AII-wuqi/AII_home/fq_775/project-dev/TriNav`
- 状态: Draft for Review

## 1. 目标与边界

### 1.1 目标

在保持 TriNav 医疗业务优势的前提下，将工程底座从“单体业务工作流”升级为“可扩展 Agent 平台内核”，使其在以下维度向 `claude-code-source` 对齐:

1. 运行时内核与统一执行循环
2. capability/tool/policy 分层治理
3. 可恢复、可追溯、可灰度发布
4. 工程质量门禁与持续评测体系

### 1.2 明确保留的医疗特色功能

1. 医疗咨询与症状解释
2. 问诊推荐与分诊等级判断
3. 红旗风险优先拦截
4. 医院推荐与路线规划
5. 循证检索与可解释结论

### 1.3 非目标

1. 不将 TriNav 改造成通用代码代理产品
2. 不在一期引入多模型竞价、自动策略学习
3. 不进行无业务收益的大规模前端重写

## 2. 现状差距矩阵（Claude vs TriNav）

以下对比基于本地仓库实测:

1. 规模
- `claude-code-source/src`: 约 1902 文件，约 142603 行 TS/TSX
- `TriNav/src`: 约 76 Python 文件，约 6858 行

2. 平台化能力
- Claude: 已形成通用平台层（tools/commands/plugins/skills/coordinator/resume）
- TriNav: 仍以医疗流程为主，平台能力初具骨架但不完整

3. 运行时与治理
- Claude: 统一 QueryEngine + 多模式权限 + 插件化装载 + 会话恢复
- TriNav: 已有 v2 runtime/capability/tool/policy 骨架，但恢复、插件生态、发布治理缺口明显

4. 质量与验证
- Claude: 平台级模块化、统一工具接口和治理路径
- TriNav: 功能测试通过，但类型与静态质量债较大，需要专门治理

## 3. V3 目标架构

```text
interfaces/
  api/
    assistant_v1_compat.py
    assistant_v2.py
    assistant_v3.py
  stream/
    event_contract.py

core/
  runtime/
    query_engine.py
    execution_context.py
    event_bus.py
    budget_manager.py
    stop_reason.py
  capability/
    protocol.py
    planner.py
    registry.py
    executor.py
  state/
    session_store.py
    snapshot_store.py
    event_store.py
    replay.py

tools/
  registry/
    tool_spec.py
    tool_registry.py
  providers/
    amap_tool.py
    ncbi_tool.py
    weather_tool.py
    vision_tool.py

policy/
  permissions/
    rules.py
    engine.py
    decision_log.py
  safety/
    medical_guard.py
    output_guard.py

capabilities/
  consultation/
  triage/
  clarification/
  evidence/
  navigation/
  response/

observability/
  tracing/
  metrics/
  audit/

release/
  shadow_compare/
  canary/
  rollback/
```

## 4. 关键设计原则

1. 内核先行: 先统一 runtime contracts，再拆业务能力
2. 能力解耦: 每个 capability 单一职责、可替换、可独立测试
3. 策略优先: 医疗高风险场景由规则与安全策略优先裁决
4. 观测闭环: 每次决策具备 trace_id、provenance、审计事件
5. 双轨迁移: v1 稳态运行，v2/v3 影子对比后灰度切流

## 5. 领域能力映射（保留并增强）

1. `consultation_capability`
- 负责用户症状语义理解、上下文关联、回答边界约束

2. `triage_capability`
- 输出 `EMERGENCY/URGENT/ROUTINE` 等级与理由

3. `clarification_capability`
- 在不确定场景生成高信息增益追问

4. `evidence_capability`
- 触发 NCBI 检索并生成可追溯证据摘要

5. `navigation_capability`
- 根据 GPS、专科、医院等级与距离生成候选医院和路线建议

6. `response_capability`
- 输出最终医疗建议，附风险提示与免责声明

7. `medical_guard`（强制后置）
- 审核输出中的诊断化表达、延误就医风险、处方化建议

## 6. 契约设计

### 6.1 ExecutionContext

必须包含:

1. `request_id`
2. `session_id`
3. `trace_id`
4. `input`（text/image/location）
5. `metadata`（channel/client/version）
6. `policy_context`

### 6.2 CapabilityResult

统一字段:

1. `name`
2. `success`
3. `status`
4. `payload`
5. `errors`
6. `provenance`

### 6.3 RuntimeEvent

统一事件类型:

1. `runtime_started`
2. `capability_planned`
3. `capability_completed`
4. `tool_called`
5. `permission_decided`
6. `runtime_failed`
7. `runtime_finished`

## 7. 数据与状态治理

1. 会话状态
- 从“仅 Redis 业务态”升级为“Snapshot + Event Log”双轨

2. 恢复能力
- 支持 `session replay` 与 `resume`，异常中断后可继续

3. 隐私策略
- 不落原始敏感图片，采用特征摘要或短期加密缓存

4. 审计要求
- 每次决策必须可追溯至 capability 和 tool 级别

## 8. API 与前端契约

1. 保留
- `POST /assistant/invoke`（v1 兼容）

2. 增强
- `POST /assistant/v2/invoke`
- `POST /assistant/v2/stream`
- `POST /assistant/v2/shadow/compare`

3. V3 扩展
- `POST /assistant/v3/invoke`
- `POST /assistant/v3/stream`
- 新增 `debug/audit` 只读接口（灰度期启用）

4. SSE 保证
- 固定时序: `status(start)` -> `final` -> `[DONE]`
- 异常路径仍需产出结构化 `final(error)`，避免前端挂起

## 9. 分阶段实施路线

### Phase A: 内核基线固化（1-2 周）

1. 冻结 v1 行为基线与黄金病例集
2. 清理 P0 回归点（参数错配、拼写错误、死代码）
3. 统一 runtime contracts 与错误语义

### Phase B: capability 化迁移（2-4 周）

1. 现有 LangGraph 链封装为 `legacy_triage_capability`
2. 逐步拆分 consultation/triage/evidence/navigation/response
3. 保持对外 API 稳定，内部替换执行路径

### Phase C: 工具与策略治理（2-3 周）

1. 全量接入 tool registry
2. 上线分层 permission engine
3. 引入 `medical_guard` 强制终审

### Phase D: 状态恢复与观测（2-3 周）

1. 落地 snapshot/event 双存储
2. 加入 resume/replay
3. 完善 tracing/metrics/audit dashboard

### Phase E: 影子对比与灰度切流（2-3 周）

1. v1/v3 shadow compare（病例集 + 在线采样）
2. 阈值达标后按 5% -> 20% -> 50% -> 100% 灰度
3. 任一核心指标越界自动回滚

## 10. 验收标准（对齐 Claude 水准）

1. 可靠性
- 关键链路可用性 >= 99.9%

2. 性能
- EMERGENCY 首响应 P95 <= 2.5s
- ROUTINE/URGENT 响应 P95 <= 6s

3. 医疗安全
- 红旗漏判率持续下降
- 高风险输出误导率受控并可追溯

4. 工程质量
- `pytest` 主干全绿
- `ruff` 阻断问题清零
- `mypy` 阻断问题清零或按模块 gate 清零

5. 发布治理
- 任意版本上线前必须通过离线评测 + shadow compare 门禁

## 11. 风险与缓解

1. 双轨复杂度上升
- 缓解: feature flags + 版本化契约 + 自动回滚

2. 历史类型债影响迭代速度
- 缓解: 按模块设债务燃尽 SLO，避免全仓一次性清理

3. 外部 API 不稳定
- 缓解: timeout budget + retry + 降级 + 缓存

4. 医疗策略变更风险
- 缓解: 规则版本化 + 专家评审 + 灰度策略

## 12. 当前落地状态（截至 2026-04-02）

已具备 V3 前置基础:

1. v2 runtime/capability/tool/policy 骨架
2. v2 invoke/stream/shadow compare 接口
3. 事件契约文档与测试覆盖
4. 全量回归测试通过（421 passed）

仍待完成:

1. capability 深度拆分与独立部署策略
2. snapshot/event 持久化与 resume/replay
3. 发布门禁与评测平台化
4. 类型与静态质量债系统治理

## 13. 结论

TriNav 不需要复制 Claude Code 的产品形态，但必须对齐其“平台内核能力”。本方案采用“内核先行 + 业务保真 + 双轨迁移 + 观测驱动”的路径，在不牺牲医疗特色的前提下，将 TriNav 提升到成熟 Agent 架构水准。
