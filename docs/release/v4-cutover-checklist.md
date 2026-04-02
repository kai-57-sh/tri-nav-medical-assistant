# TriNav v4 Cutover Checklist

> 目标：在不破坏 v3 协议契约的前提下，完成 v4 runtime 灰度放量与全量回归验收。

## 1. 灰度前配置检查

- [ ] 部署平台配置项已生效：

```ini
v4_runtime_enabled=true
v4_canary_enabled=true
v4_gate_max_red_flag_miss_rate=0.01
```

- [ ] 环境变量与配置项映射已确认：

```ini
V4_RUNTIME_ENABLED=true
V4_CANARY_ENABLED=true
V4_GATE_MAX_RED_FLAG_MISS_RATE=0.01
V4_GATE_MAX_P95_MS=6000
```

- [ ] `/assistant/v3/invoke`、`/assistant/v3/stream`、`/assistant/v3/runtime/doctor` 路由健康检查通过。
- [ ] 已准备 v3 回滚开关（可在一个发布窗口内恢复到 v3 稳定路径）。

## 2. 全量回归

执行命令：

```bash
pytest -q tests/unit/test_server_v2.py tests/unit/test_server_v2_stream.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/unit/test_server_v3_runtime_admin.py tests/unit/test_v3 tests/integration/test_shadow_compare.py tests/integration/test_shadow_compare_v3.py tests/evals/test_golden_cases.py
```

验收标准：

- [ ] 所有测试通过。
- [ ] 无新增 flaky 测试。

## 3. 代码质量门禁

执行命令：

```bash
ruff check src tests
mypy src
```

验收标准：

- [ ] `ruff` 无错误。
- [ ] `mypy` 无错误。

## 4. 灰度放量建议

- [ ] 按比例放量：1% -> 5% -> 20% -> 50% -> 100%。
- [ ] 每阶段检查 `red_flag_miss_rate` 与 p95 指标。
- [ ] 任一阶段若 `red_flag_miss_rate > 0.01`，立即停止放量并回滚。

## 5. 发布后巡检

- [ ] 抽样检查 v3 SSE 事件序列仍为 `status -> final -> [DONE]`。
- [ ] 错误场景仍保持 stream HTTP 200 + final payload `status=error`。
- [ ] runtime replay 与诊断接口可读取最新会话事件。

## 6. 回滚触发条件

满足任一项立即回滚：

- [ ] 医疗安全相关告警显著上升。
- [ ] `red_flag_miss_rate` 连续两个观测窗口超过 `0.01`。
- [ ] 核心接口错误率或时延超过 SLO 且无法在窗口内恢复。
