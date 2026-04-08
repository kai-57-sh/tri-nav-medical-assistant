# TriNav v3 Cutover / Production Baseline Handoff

- 日期: 2026-04-08
- 仓库: `/AII-wuqi/AII_home/fq_775/project-dev/TriNav`
- 当前分支: `001-medical-triage-nav-V2.0`
- 当前 HEAD: `3e78ee47d4213b5661a69f314ae42f934eae49ee`
- 目标读者: 接手 TriNav v3 切主、生产可用化、上线准备的工程师

## 1. 交接摘要

TriNav 当前已经不再处于“纯分析/纯规划”阶段，v3 切主与生产可用化已经完成了大部分实装和验证。当前状态可以概括为：

1. `POST /assistant/invoke` 已通过 compat adapter 默认落到 v3 runtime。
2. `POST /assistant/v3/invoke` 与 `POST /assistant/v3/stream` 已有明确的 v3 runtime gate 语义。
3. legacy LangGraph 不再承担默认公开入口，只保留 fallback / shadow compare / 回归基线角色。
4. 生产基线资产已经基本齐全：readiness、metrics、Docker 资产、CI、smoke、release gate、cutover runbook 都已落地。
5. 测试基线很强，当前全量 `pytest -q` 为 `651 passed`。

当前最重要的未收口点，不再是“默认流量有没有切到 v3”，而是：

1. 将 `/assistant/v3/stream` 的执行语义进一步从 `assistant_v2` 的 SSE 包装逻辑中解耦，和 invoke 路径完全对齐。
2. 在有 Docker daemon 和真实 staging 配置的环境里，把容器化 smoke / cutover checks 真正跑完。
3. 决定是否要保持 `src/config/settings.py` 的 v3 默认值为安全关闭，还是与 `.env.example` 的“默认 baseline”表述进一步对齐。

## 2. 本轮设计与计划文档

接手前建议先读这 5 份文档：

1. `docs/superpowers/specs/2026-04-07-trinav-v3-cutover-production-design.md`
2. `docs/superpowers/plans/2026-04-07-trinav-v3-data-contracts-implementation-plan.md`
3. `docs/superpowers/plans/2026-04-07-trinav-v3-cutover-implementation-plan.md`
4. `docs/superpowers/plans/2026-04-07-trinav-production-baseline-implementation-plan.md`
5. `docs/superpowers/plans/2026-04-07-trinav-release-operations-implementation-plan.md`

如果只看一份，先看 design 文档；如果要直接继续实现，优先看 v3 cutover plan 和 production baseline plan。

## 3. 当前架构状态

### 3.1 公开入口

当前公开入口分为三类：

1. `POST /assistant/invoke`
   - 入口文件: `src/interfaces/api/assistant_compat.py`
   - 作用: 保持旧 public envelope，内部默认委托到 v3 runtime
   - 运输层语义: 即使 runtime 返回结构化失败，compat 路由通常仍返回 HTTP 200，并把失败包装在 `output.status=error`

2. `POST /assistant/v3/invoke`
   - 入口文件: `src/interfaces/api/assistant_v3.py`
   - 作用: 显式 v3 JSON 协议入口
   - 运输层语义: 成功返回 200；结构化失败返回 503

3. `POST /assistant/v3/stream`
   - 入口文件: `src/interfaces/api/assistant_v3.py`
   - 作用: 显式 v3 SSE 协议入口
   - 运输层语义: HTTP 200 + SSE final event 承载成功或失败

### 3.2 runtime 层

runtime 关键文件：

1. `src/interfaces/api/runtime_v3.py`
2. `src/interfaces/api/assistant_v2.py`
3. `src/platform/runtime/kernel.py`

当前行为：

1. invoke 路径已经集中到 `runtime_v3.py`
2. 显式 v3 runtime gate 现在真实生效，不再只是 doctor 文案
3. legacy fallback 仍由 `runtime_v3.py` 控制
4. stream 路径虽然已经受 `V3_RUNTIME_ENABLED` gate 控制，但成功路径仍复用 `assistant_v2` 的 SSE 包装逻辑

### 3.3 legacy 角色

legacy LangGraph 当前定位已经收敛为：

1. `runtime_v3` 的 fallback
2. shadow compare 基线
3. 回归与一致性对照

不建议再把新业务能力加回 legacy graph。

## 4. 已完成工作

### 4.1 Workstream A: v3 数据契约

状态: 已完成

关键结果：

1. 引入 canonical `MedicalTurnState`
2. `CapabilityResult` 增加并消费 `state_patch`
3. consultation / triage / evidence / navigation 已发出 canonical state patch
4. response capability 与 compat fallback 已优先消费 `turn_state`

关键文件：

1. `src/core/runtime/medical_state.py`
2. `src/core/runtime/state_patch.py`
3. `src/core/runtime/types.py`
4. `src/capabilities/consultation/capability.py`
5. `src/capabilities/triage/capability.py`
6. `src/capabilities/evidence/capability.py`
7. `src/capabilities/navigation/capability.py`
8. `src/capabilities/response/capability.py`

### 4.2 Workstream B: v3 切主

状态: 基本完成，但仍有一个技术债收口点

已完成：

1. 抽出共享入口 `src/interfaces/api/runtime_v3.py`
2. `assistant_v3.py` 不再直接绑死到 `assistant_v2`
3. `assistant_compat.py` 已成为 `/assistant/invoke` 的默认 compat 入口
4. `/assistant/invoke` 与 `/assistant/v3/invoke` 已共享 v3 默认执行路径
5. `V3_RUNTIME_ENABLED` 现在会真实 gate 显式 v3 路由和 public compat 行为

本轮新增的关键收口：

1. `3e78ee4 feat(v3): enforce runtime gate on public routes`
   - `V3_RUNTIME_ENABLED=false` 时：
     - `/assistant/v3/invoke` 直接返回结构化 503
     - `/assistant/invoke` 仍返回 HTTP 200，但 `output.status=error`
     - `/assistant/v3/stream` 返回稳定的 SSE final error

剩余未完成：

1. `/assistant/v3/stream` 的成功路径仍借用了 `assistant_v2` 的 SSE 包装逻辑
2. 从“功能上已切主”到“实现上完全不借壳”的最后一步还没做

### 4.3 Workstream C: 生产可用基线

状态: 大体完成

已完成：

1. readiness / metrics 端点
2. Dockerfile / docker-compose / .dockerignore
3. GitHub Actions CI
4. backend check 脚本
5. v3 smoke 脚本
6. `.env.example`、README、API 文档、开发者文档对齐

关键文件：

1. `src/server.py`
2. `src/utils/metrics.py`
3. `Dockerfile`
4. `docker-compose.yml`
5. `.github/workflows/ci.yml`
6. `scripts/ci/run_backend_checks.sh`
7. `scripts/smoke/check_v3_runtime.py`
8. `.env.example`
9. `README.md`
10. `docs/API_REFERENCE.md`
11. `docs/DEVELOPER_GUIDE.md`

本轮新增的关键收口：

1. `9124623 feat(smoke): tighten v3 runtime verification`
2. `4747299 test(smoke): cover structured 503 invoke responses`
3. `8cf3259 fix(smoke): harden v3 runtime readiness check`

现在 smoke 脚本会：

1. 要求 `/assistant/v3/runtime/doctor.status == "ok"`
2. 要求 `runtime.v3_runtime_enabled == true`
3. 真正发起 `POST /assistant/v3/invoke`
4. 接受结构化 200 / 503，而不是把 503 误判成 transport failure

剩余未完成：

1. 本机没有可用 Docker daemon，因此无法在当前环境里完成 `docker build` 与容器级 smoke 的最终验证
2. 这部分必须在有 daemon 的 staging / CI / 其他开发机上补完

### 4.4 Workstream D: 发布治理闭环

状态: 已完成到“可执行脚本 + runbook”层

已完成：

1. machine-readable canary gate report
2. `check_canary_gate.py` CLI
3. `run_cutover_checks.sh`
4. `/assistant/v3/runtime/doctor` release block
5. cutover runbook
6. checklist 文档与真实 flags 对齐

关键文件：

1. `src/release/ops/gate_report.py`
2. `scripts/release/check_canary_gate.py`
3. `scripts/release/run_cutover_checks.sh`
4. `src/interfaces/api/runtime_admin_v3.py`
5. `docs/release/v3-cutover-runbook.md`
6. `docs/release/v4-cutover-checklist.md`

剩余未完成：

1. 还没有在真实 staging / canary 环境里跑过完整 traffic ramp
2. 目前 gate 更多是“脚本能力已就位”，还不是“线上发布已经完成”

## 5. 最近重要提交

建议重点读下面这些提交：

1. `3e78ee4 feat(v3): enforce runtime gate on public routes`
   - 让 `V3_RUNTIME_ENABLED` 成为真实执行门禁

2. `8cf3259 fix(smoke): harden v3 runtime readiness check`
   - 修复 smoke 对结构化 503 / disabled doctor 的判断

3. `133bc68 feat(release): finalize v3 cutover operations`
   - 完成 release gate / runbook / cutover checks

4. `9af6a91 feat(ci): add baseline workflow and smoke checks`
   - 加入 CI 和 smoke 基线

5. `3a1bf14 docs: align public compat contract`
   - 公开 API / env / operator docs 对齐

## 6. 当前 freshly verified 状态

以下结果为本次交接前新鲜验证，不依赖历史记录：

1. `pytest -q`
   - 结果: `651 passed in 12.16s`

2. `python -m mypy src`
   - 结果: `Success: no issues found in 121 source files`

3. `uvx ruff check src tests`
   - 结果: `All checks passed!`

4. `cd frontend && npm run build`
   - 结果: 成功

5. `git status --short`
   - 结果: 工作树干净

## 7. 仍需明确提醒的风险 / 注意事项

### 7.1 `V3_RUNTIME_ENABLED` 现在是硬门禁

这件事和之前不同了：

1. 以前 `runtime doctor` 可以报告 disabled，但显式 v3 路由仍可能继续执行
2. 现在这已经被修掉

实际影响：

1. 如果部署环境没有设置 `V3_RUNTIME_ENABLED=true`
2. `/assistant/v3/invoke` 会直接返回 503
3. `/assistant/invoke` 会返回 HTTP 200，但 `output.status=error`
4. `/assistant/v3/stream` 会返回 final error SSE

所以 staging / production 环境必须显式配置：

```ini
V3_RUNTIME_ENABLED=true
V3_TASK_COORDINATOR_ENABLED=true
V3_LEGACY_FALLBACK_ENABLED=true
V3_BUILTIN_PLUGINS_ENABLED=true
```

### 7.2 settings 默认值与 `.env.example` 的语义不同

当前现状：

1. `src/config/settings.py` 里多数 v3 flags 默认仍是 `False`
2. `.env.example` 和 runbook 里的推荐 baseline 是 `true`

这不是 bug，但它意味着：

1. 本地如果不加载 `.env`
2. 或测试不显式 patch settings
3. 显式 v3 路由就会被 gate 掉

本轮已经把相关测试前提写明确了，但团队后续需要决定：

1. 保持“代码安全默认关闭”
2. 或将代码默认值与 baseline 文档对齐

### 7.3 容器验证仍缺真实运行证据

当前代码和 compose 资产都在仓库里，但当前环境没有 Docker daemon，因此：

1. `docker compose config` 可以检查静态配置
2. 但 `docker build` / `docker compose up` / 容器级 smoke 还没在本机完成

这部分必须在下一位同事接手时优先补齐。

## 8. 推荐的接手顺序

如果同事明天开始继续，建议按下面顺序推进：

1. 先读 `docs/superpowers/specs/2026-04-07-trinav-v3-cutover-production-design.md`
2. 再读 `docs/release/v3-cutover-runbook.md`
3. 看最近 5 个提交
4. 本地跑一遍：
   - `pytest -q`
   - `python -m mypy src`
   - `uvx ruff check src tests`
   - `cd frontend && npm run build`
5. 在有 Docker daemon 的环境里补：
   - `docker compose config`
   - `docker build -t trinav:test .`
   - `docker compose up -d redis`
   - 应用启动 + `python scripts/smoke/check_v3_runtime.py http://127.0.0.1:8000`
6. 然后继续下一个技术债收口：v3 stream 路径完全解耦

## 9. 下一步详细工作计划

### P0: 统一 `/assistant/v3/stream` 的主执行语义

目标：

1. 让 `stream_runtime_v3()` 不再仅仅 gate 后调用 `stream_assistant_v2()`
2. 让它与 `invoke_runtime_v3()` 共享同一套 primary / fallback / disabled 语义

建议做法：

1. 抽一个更小的 shared execution helper，返回结构化 invoke 结果
2. invoke 路径直接返回 `JSONResponse`
3. stream 路径把同一结果转成 `status -> final -> [DONE]`
4. 避免成功路径仍然隐式依赖 `assistant_v2.invoke_assistant_v2`

建议先补测试：

1. `V3_RUNTIME_ENABLED=false` 的 stream 已有测试，不要回归
2. 新增“primary structured error -> stream final error”
3. 新增“legacy fallback success -> stream final success”
4. 新增“fallback disabled -> stream final error”

### P0: 在真实 daemon 环境完成容器化 smoke

目标：

1. 为 production baseline 增加真正的容器运行证据

建议执行：

1. `docker build -t trinav:test .`
2. `docker compose up -d redis`
3. `docker run --rm --env-file .env -p 8000:8000 trinav:test`
4. `python scripts/smoke/check_v3_runtime.py http://127.0.0.1:8000`
5. `bash scripts/release/run_cutover_checks.sh http://127.0.0.1:8000 tests/fixtures/release/canary_ok.json`

验收标准：

1. 镜像构建成功
2. 容器启动成功
3. smoke 成功
4. cutover checks 成功

### P1: 明确 v3 flags 的默认策略

当前是“代码默认关闭 + `.env.example` 默认开启 baseline”。

需要做一个明确决策：

1. 继续保持现在的安全默认
2. 或把 `Settings` 默认值也改成与 `.env.example` 一致

如果改默认值，需要同步：

1. `src/config/settings.py`
2. `tests/unit/test_config/test_settings_v2.py`
3. 可能依赖默认 false 的测试
4. README / API docs / runbook 中的表述

### P1: staging 级别演练 release runbook

目标：

1. 把目前“文档 + fixture + 脚本”提升成“staging 真实演练”

建议执行：

1. 按 `docs/release/v3-cutover-runbook.md` 配置 flags
2. 真实调用 `/assistant/v3/runtime/doctor`
3. 真实采样 replay/resume
4. 用 staging 指标生成 canary metrics JSON
5. 跑一遍 traffic ramp 的 1% -> 5% -> 20% 演练

## 10. 建议优先阅读的代码文件

如果要快速进入上下文，优先读下面这些文件：

1. `src/interfaces/api/runtime_v3.py`
2. `src/interfaces/api/assistant_compat.py`
3. `src/interfaces/api/assistant_v3.py`
4. `src/interfaces/api/runtime_admin_v3.py`
5. `src/interfaces/api/assistant_v2.py`
6. `src/core/runtime/medical_state.py`
7. `src/core/runtime/state_patch.py`
8. `src/capabilities/response/capability.py`
9. `scripts/smoke/check_v3_runtime.py`
10. `scripts/release/run_cutover_checks.sh`

## 11. 一句话接手结论

TriNav 已经完成“v3 作为默认 invoke 主路径”的大部分收口，也具备了生产基线和发布治理骨架；下一位同事不需要再做战略设计，应该直接进入最后的 stream 语义统一、容器化实机验证和 staging cutover 演练。
