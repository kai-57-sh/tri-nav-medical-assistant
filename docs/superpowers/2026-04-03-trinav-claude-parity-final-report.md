# TriNav 对齐 Claude-Code 架构最终报告（重构版）

- 日期: 2026-04-03
- TriNav 仓库: `/AII-wuqi/AII_home/fq_775/project-dev/TriNav`
- 对标仓库: `/AII-wuqi/AII_home/fq_775/project-dev/claude-code-source`
- 定位: 在保留医疗咨询、问诊推荐、循证检索、导诊导航能力前提下，实现“医疗垂直 Agent 平台”工程水准对齐

## 1. 结论

TriNav 已从“以业务链路为中心”升级为“runtime/kernel + capability + tool/policy/state + release gate”平台化架构。当前可给出结论：

1. 核心平台能力已对齐到可生产工程水准。
2. 医疗特色能力保留且增强（安全治理前置/后置闭环、可回放、可灰度）。
3. 工程质量门禁达到可持续迭代状态（全量类型检查清零 + 关键回归通过）。

## 2. 与 Claude-Code 的差距对比（重构后）

| 维度 | Claude-Code | TriNav 当前状态 | 对齐结论 |
|---|---|---|---|
| 统一运行时内核 | QueryEngine + tool loop | RuntimeKernel 单入口，API 协议层与执行层分离 | 已对齐（医疗垂直范围） |
| 工具治理 | 工具平台化 + 权限回调 | ToolGateway + PermissionEngine + decision audit | 已对齐（医疗工具域） |
| 状态恢复 | 会话恢复与任务态 | event/snapshot repository + replay/resume | 已对齐 |
| 发布门禁 | feature flag + 体系化发布 | v4 canary gate + shadow compare + cutover checklist | 已对齐 |
| 安全策略 | 平台策略与权限体系 | medical safety engine + output guard + consent policy | 已对齐（医疗优先） |
| 工程质量 | TS 严格工程化 | `mypy src` 全绿、`ruff` 全绿、回归全绿 | 已对齐 |
| 多 Agent/团队协作 | 原生成熟体系 | 已有 runtime 基础，尚未构建医疗多 agent 编排层 | 部分差距（可选） |
| IDE/remote bridge 生态 | 完整 bridge/remote 能力 | 不作为医疗核心目标，暂未建设 | 目标外差距 |

## 3. 已落地架构与代码证据

### 3.1 统一运行时

- `RuntimeKernel` 单入口与统一错误语义: `src/platform/runtime/kernel.py`
- v2/v3 协议层适配到统一 runtime: `src/interfaces/api/assistant_v2.py`, `src/interfaces/api/assistant_v3.py`

### 3.2 工具与权限

- Policy-aware 工具网关: `src/platform/tooling/gateway.py`
- 统一权限判定与审计决策: `src/platform/policy/permission_engine.py`

### 3.3 状态与恢复

- Redis-first runtime 事件仓储: `src/platform/state/event_repository.py`
- Redis-first snapshot 仓储: `src/platform/state/snapshot_repository.py`
- replay/resume 服务化: `src/platform/state/replay_service.py`
- 管理面可诊断接口: `src/interfaces/api/runtime_admin_v3.py`

### 3.4 发布治理

- v4 canary gate: `src/release/canary/gate.py`
- 运行切流清单: `docs/release/v4-cutover-checklist.md`

## 4. 关键实施提交（按时间）

- `2eda965` `fix(v4-medical): harden capability timeouts and triage consistency`
- `587c7b3` `feat(v4-policy): add ToolGateway and PermissionEngine with decision auditing`
- `358c0db` `feat(v4-state): persist runtime events and snapshots with redis-first repositories`
- `097ad00` `feat(v4-runtime-admin): productionize replay and resume via replay service`
- `24cd7e5` `feat(v4-safety): add structured medical safety engine and enforce on final output`
- `d167168` `feat(release): add v4 canary gate with shadow-based blocking thresholds`
- `71800a6` `docs(v4): add runtime cutover checklist and update api/events contracts`
- `e933a58` `fix(types): tighten runtime and api typing contracts`
- `2c66e44` `fix(types): harden service/repository typing and graph node bindings`
- `5f35e81` `fix(types): drive mypy debt to zero across models and llm service`

## 5. 质量与回归结果（2026-04-03）

### 5.1 类型与静态检查

- `mypy src` -> `Success: no issues found in 116 source files`
- `ruff check src tests` -> `All checks passed`

### 5.2 回归测试（重点覆盖）

- 运行集：`llm_service`、models、session_loader、v3 runtime、shadow compare、runtime kernel 等
- 结果：`228 passed`

## 6. 保留医疗特色能力的重构策略（最终方案）

1. 咨询（Consultation）
- 以 capability 为边界，确保输出解释性、非诊断化、风险提示完整。

2. 问诊推荐/分诊（Triage）
- 红旗规则 + 分类器 + 合并策略；不确定时保守升级。

3. 循证（Evidence）
- NCBI 检索链路纳入统一 tool/policy/runtime 轨道，失败有可解释降级。

4. 导诊导航（Navigation）
- 医院推荐与路线能力保持，天气与地理能力通过统一工具网关受控调用。

5. 安全（Medical Safety）
- 前置权限（consent）+ 过程审计（decision log）+ 后置安全（medical guard/output guard）三层闭环。

## 7. 仍建议的下一阶段（V5，可选）

1. 医疗多 Agent 专家协作
- 例如 `triage-agent / evidence-agent / navigation-agent` 的受控并发与仲裁。

2. 评测平台化
- 将 golden + shadow + canary 指标沉淀成持续评测流水线（日报/周报）。

3. 运营可观测增强
- 增加失败归因维度与病例级可追踪 dashboard。

## 8. 最终判断

TriNav 现已具备“可落地、可治理、可发布”的成熟 Agent 工程底座。对齐目标不在于复制 Claude-Code 的通用产品形态，而是以医疗垂直场景达到同等级工程可靠性与治理能力；该目标已实质达成。
