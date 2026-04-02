# TriNav 对齐 Claude-Code 架构重构（一页汇报）

- 日期: 2026-04-03
- 项目: TriNav（医疗导诊小助手）
- 对标: Claude-Code（成熟 Agent 架构）

## 1. 目标

在保持医疗咨询、问诊推荐、循证检索、导诊导航特色能力不下降前提下，将 TriNav 升级为可治理、可观测、可灰度、可回滚的医疗垂直 Agent 平台。

## 2. 关键差距（重构前）

1. 运行时执行链路分叉，协议层与执行层耦合。
2. 工具调用缺少统一前置权限与可审计决策链。
3. 状态恢复能力不足，事件与快照生产化不足。
4. 发布门禁与自动回滚策略不完整。
5. 类型与静态质量债影响迭代速度。

## 3. 完全重构方案

1. 统一内核: 建立 RuntimeKernel 单入口，v2/v3 仅做协议适配。
2. 能力分层: capability 化承载 consultation/triage/evidence/navigation/response。
3. 工具治理: ToolGateway + PermissionEngine，敏感调用需策略放行。
4. 状态恢复: Redis-first event/snapshot + replay/resume。
5. 安全闭环: 前置权限 + 过程审计 + 后置 medical/output guard。
6. 发布治理: shadow compare + canary gate + 回滚清单。

## 4. 当前结果

1. `mypy src` 全绿（116 source files）。
2. `ruff check src tests` 全绿。
3. 关键回归测试全绿（228 passed）。
4. 形成完整重构文档、PR 模板、发布模板与切流证据。

## 5. 业务价值

1. 医疗风险控制能力提升（高风险输出可拦截、可追溯）。
2. 研发迭代确定性提升（类型门禁 + 统一架构）。
3. 发布风险可控（门禁阈值 + 自动回滚策略）。

## 6. 下一步建议（V5）

1. 医疗多 Agent 专家协作（triage/evidence/navigation）。
2. 评测平台化（golden + shadow + canary 持续评测）。
3. 运营可观测增强（失败归因与病例级追踪）。
