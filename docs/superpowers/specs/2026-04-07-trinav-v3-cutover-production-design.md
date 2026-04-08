# TriNav v3 切主与生产可用化设计

- 日期: 2026-04-07
- 仓库: `/AII-wuqi/AII_home/fq_775/project-dev/TriNav`
- 设计范围: 下一轮开发
- 目标读者: 对当前仓库上下文不熟悉、但要负责实施切换与上线准备的工程师

## 1. 背景

TriNav 当前已经具备较强的业务能力与测试基线，但执行面存在三层并存：

1. 默认主链路仍是 LangGraph 18 节点医疗工作流，入口为 `POST /assistant/invoke`。
2. v2 runtime 已提供统一 kernel、runtime event、snapshot、plugin、安全治理、shadow compare。
3. v3 capability/task-coordinator 路径已形成雏形，但尚未成为唯一主执行路径。

这导致两个实际问题：

1. 架构层面存在“双轨长期共存”风险，新平台能力没有真正吃到默认流量。
2. “production ready” 在业务上基本成立，但在部署、CI、配置一致性、发布门禁自动化上仍未完全达标。

## 2. 本轮目标

### 2.1 主目标

在不损失现有医疗分诊、循证检索、导航导诊、安全合规能力的前提下，完成以下两件事：

1. 让 v3 capability runtime 成为 TriNav 的默认主执行路径。
2. 将系统提升到“小规模真实生产可用”的工程水准。

### 2.2 成功标准

本轮结束时应满足以下条件：

1. `/assistant/v3/invoke` 与 `/assistant/invoke` 指向同一条 v3 主执行路径。
2. 旧 LangGraph 不再承担默认用户入口，只保留为 fallback、shadow compare、回归基线。
3. consultation、triage、evidence、navigation、response 五个 capability 之间通过显式结构化契约传递中间结果，而不是大量依赖 heuristic 重建状态。
4. 仓库具备可重复的 staging/production 启动方式、基础 CI、静态检查入口、健康检查与 smoke test。
5. 发布前具备 golden + shadow + canary gate 的可执行门禁，而不是只停留在文档层。

## 3. 非目标

本轮不处理以下事项：

1. 不做医疗多 agent 专家协作层。
2. 不做跨地域多活、高级流量调度或自动扩缩容。
3. 不重写全部旧 LangGraph 节点，只在必要处复用其成熟逻辑。
4. 不追求一次性消灭所有历史文档；只清理会影响实施和上线判断的关键漂移。

## 4. 现状判断

### 4.1 已具备能力

当前仓库已具备以下高价值基础：

1. 业务能力完整：文本问诊、图片症状提取、红旗检测、分诊、NCBI 循证、医院导航、天气提醒。
2. 平台基础存在：runtime kernel、plugin registry、permission engine、tool gateway、event/snapshot repository、replay service、runtime admin、shadow compare、canary gate。
3. 测试强度高：本次仓库审计中 `pytest -q` 通过 `593 passed`，前端 `npm run build` 通过。

### 4.2 当前主要问题

1. v3 仍是“过渡路径”，不是默认主路径。
2. capability 之间的中间状态传递还不够统一，response/navigation 等模块仍有 heuristic 补状态的做法。
3. 文档、环境变量、实现存在漂移，容易误导上线与运维。
4. 部署与 CI 基线未在仓库内闭环，缺少 Dockerfile、compose、GitHub Actions。
5. 发布治理组件存在，但还没有被固化为真实操作流程和自动化门禁。

## 5. 设计决策

### 5.1 切换策略

采用“strangler cutover”而不是大爆炸替换。

具体原则：

1. v3 capability runtime 先补齐显式契约与结果聚合能力。
2. 在协议层保持外部 API 契约稳定，内部将默认流量切到 v3。
3. 旧 LangGraph 保留为 fallback 与 shadow compare 基线，避免一次性删除成熟逻辑。
4. 切换通过 feature flag、shadow compare、golden cases、canary gate 渐进验证。

### 5.2 主执行路径

切换完成后，推荐执行拓扑如下：

1. `POST /assistant/v3/invoke` -> v3 coordinator -> capability pipeline -> response payload
2. `POST /assistant/invoke` -> 默认代理到相同 v3 coordinator
3. 旧 LangGraph `invoke_chain()` 仅用于：
   - shadow compare
   - fallback
   - 回归与一致性对照

### 5.3 数据契约原则

v3 不再依赖“把上游结果塞进 metadata，再由下游猜测还原”。

应引入统一的中间结果结构，至少覆盖：

1. consultation 输出：`symptom_schema`、`consultation_summary`
2. triage 输出：`triage_level`、`triage_reason`、`recommended_departments`、`possible_causes`、`red_flags`
3. evidence 输出：`ncbi_query`、`evidence_selected`
4. navigation 输出：`navigation_result`、`weather_alert`
5. response 输入：消费上述结构化结果，避免再用启发式推断 triage level

### 5.4 对外稳定性原则

外部请求和响应契约优先稳定：

1. 不打破现有 `/assistant/invoke`、`/assistant/v3/invoke`、`/assistant/v3/stream` 基本响应格式。
2. 对前端与客户端保持兼容，字段缺失要通过兼容层处理，而不是直接删字段。
3. 可以逐步废弃历史字段，但必须先在文档、适配层、测试中给出过渡。

## 6. 目标架构

### 6.1 运行时分层

目标分层如下：

1. API 层
   - `assistant_v3` 作为默认执行入口
   - `assistant_v2` 退化为兼容与过渡层，最终可合并或下沉

2. Runtime 层
   - `RuntimeKernel` 负责统一 invoke surface
   - `RuntimeCoordinator` 负责 plugin before/after execute
   - `TaskCoordinator` 负责 capability 串行与 required/optional 语义

3. Capability 层
   - `ConsultationCapability`
   - `TriageCapability`
   - `EvidenceCapability`
   - `NavigationCapability`
   - `ResponseCapability`

4. Platform 层
   - `PermissionEngine`
   - `ToolGateway`
   - `RuntimeEventRepository`
   - `RuntimeSnapshotRepository`
   - `ReplayService`
   - `CanaryGate`

5. Legacy 层
   - LangGraph workflow
   - 仅用于 fallback、shadow compare、回归对照

### 6.2 关键责任边界

1. capability 负责医疗业务逻辑与结果产出。
2. runtime 负责编排、审计、故障隔离、插件和事件。
3. platform 负责权限、状态、回放、治理。
4. legacy graph 不再新增业务能力，只接受缺陷修复和对照保障。

## 7. 下一轮实施拆分

下一轮不应写成一个大而全的实现计划，而应拆成四个可独立验收的子计划。

### Workstream A: v3 数据契约与能力聚合

目标：
让 v3 capability pipeline 通过显式结构传递中间结果，去掉 response/navigation 对 metadata 和 heuristic 的过度依赖。

产出：

1. 新的 capability result schema
2. 统一 context/result 聚合逻辑
3. v3 capability tests 升级

### Workstream B: v3 切主

目标：
把 v3 变成默认执行路径，并让 `/assistant/invoke` 与 `/assistant/v3/invoke` 行为一致。

产出：

1. 默认调用路由切换
2. legacy graph fallback/shadow compare 明确化
3. 兼容性回归测试

### Workstream C: 生产可用基线

目标：
补齐容器化、CI、环境一致性、健康检查、静态检查、staging smoke test。

产出：

1. `Dockerfile`
2. `docker-compose.yml` 或等价本地部署清单
3. `.github/workflows/ci.yml`
4. 配置文档、env 模板、部署说明收敛

### Workstream D: 发布治理闭环

目标：
把 golden、shadow、canary、replay、runtime admin 连接成真正的上线与回滚流程。

产出：

1. 可执行 cutover runbook
2. 自动化 gate 命令或脚本
3. 失败回滚流程
4. 关键运维观察面板与告警需求

## 8. 里程碑顺序

建议顺序如下：

1. 先完成 Workstream A
2. 再完成 Workstream B
3. 然后完成 Workstream C
4. 最后完成 Workstream D

原因：

1. A 是 B 的前置依赖；不先收敛 capability 契约，切主只会把旧问题转移到新入口。
2. B 完成后，C 和 D 才有明确的主执行路径可以加固。
3. C 与 D 可以部分并行，但最终都必须围绕已切主的 v3 路径展开。

## 9. 验收门槛

### 9.1 功能门槛

1. v3 主路径可覆盖 consultation、triage、evidence、navigation、response 全链路。
2. shadow compare 可对比 v1 legacy graph 与 v3 主路径。
3. fallback 可在 v3 关键失败时降级到 legacy graph 或安全错误输出。

### 9.2 工程门槛

1. `pytest -q` 通过
2. 前端 `npm run build` 通过
3. 静态检查通过：至少 `ruff check src tests` 和 `mypy src`
4. 本地/CI/staging 有统一启动方式

### 9.3 发布门槛

1. golden eval 通过
2. shadow compare 无重大 triage 偏差
3. canary gate 满足 `red_flag_miss_rate` 与 `p95_ms` 阈值
4. 存在可执行回滚路径

## 10. 风险与缓解

### 风险 1: v3 capability 与 legacy graph 行为不一致

缓解：

1. 保留 shadow compare
2. 增加 golden case 对照
3. 以 EMERGENCY/URGENT 的保守一致性优先

### 风险 2: capability 契约改动过大导致前端或 API 响应漂移

缓解：

1. API 层保持稳定契约
2. 通过兼容层做字段适配
3. 以 contract test 锁住响应格式

### 风险 3: 生产准备工作扩散成大规模平台化改造

缓解：

1. 本轮只做到单 region、小规模真实生产可用
2. 不引入多活和自动扩缩容
3. 只建设上线必须的 CI、容器化、健康检查、回滚

## 11. 本轮完成定义

当以下条件同时满足时，本轮视为完成：

1. v3 为默认主执行路径
2. legacy graph 不再是默认入口
3. 关键 capability 之间的中间结果为显式结构传递
4. CI、容器化、配置、部署说明、静态检查闭环
5. golden + shadow + canary + replay 构成可执行上线流程

## 12. 实施后的预期状态

完成本轮后，TriNav 的定位将从：

- “具备成熟业务链路、但平台主路径尚未收口的医疗 Agent 系统”

提升为：

- “以 v3 runtime 为唯一主路径、具备上线治理与回滚能力的小规模生产可用医疗 Agent 系统”

## 13. 后续计划输出方式

基于本设计，下一步应产出四份实现计划：

1. `trinav-v3-data-contracts`
2. `trinav-v3-cutover`
3. `trinav-production-baseline`
4. `trinav-release-operations`

每份计划都应包含：

1. 精确文件列表
2. TDD 任务拆分
3. 测试命令
4. 验收标准
5. 分阶段提交建议
