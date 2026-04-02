# [发布通知] TriNav v4 Claude-Parity 重构上线说明

- 日期: 2026-04-03
- 版本: v4 parity baseline
- 发布负责人: [待填]
- 影响范围: assistant v2/v3 runtime、tool/policy/state/release gate

## 1. 发布摘要

本次发布完成 TriNav 对齐 Claude-Code 架构水准的重构收口，重点实现:
1. 统一 RuntimeKernel 执行入口。
2. 工具/权限/医疗安全治理闭环。
3. Redis-first 状态持久化与 replay/resume。
4. canary gate 与切流回滚机制。
5. 类型与质量门禁清零。

## 2. 医疗能力与安全

- 医疗咨询与问诊推荐: 保留并在 capability 边界内增强可解释性。
- 导诊导航与循证检索: 统一纳入 tool/policy/runtime 治理轨道。
- 医疗安全策略: 前置同意检查 + 过程决策审计 + 后置输出安全拦截。

## 3. 质量门禁结果

1. `mypy src`: PASS（116 source files 全通过）
2. `uvx ruff check src tests`: PASS
3. 关键回归测试: PASS（`228 passed`）

## 4. 灰度计划

1. 灰度比例: `1% -> 5% -> 20% -> 50% -> 100%`
2. 门禁阈值:
- `red_flag_miss_rate <= 0.01`
- `p95_ms <= 6000`

## 5. 回滚策略

满足任一项立即回滚:
1. 医疗安全告警显著上升。
2. canary gate 连续两个观测窗口失败。
3. 核心接口错误率/时延超过 SLO 且无法在窗口内恢复。

## 6. 值班与监控

- 监控面板: [待填]
- 值班负责人: [待填]
- 升级路径: [待填]

## 7. 相关文档

1. `docs/superpowers/2026-04-03-trinav-claude-parity-final-report.md`
2. `docs/release/v4-cutover-checklist.md`

