# PR Description Template (TriNav V4 Claude-Parity)

## 1. 背景

- 关联目标:
- 关联 issue/任务:
- 发布窗口:

## 2. 本次变更

- 变更类型: `feat` / `fix` / `refactor` / `docs` / `chore`
- 涉及模块:
- 核心改动:
1. 
2. 
3. 

## 3. 架构影响

- 是否影响 RuntimeKernel: `yes/no`
- 是否影响 capability 链路: `yes/no`
- 是否影响 tool/policy/state/release gate: `yes/no`
- 向后兼容性:

## 4. 医疗安全影响

- 是否影响红旗识别逻辑: `yes/no`
- 是否影响 medical safety engine/output guard: `yes/no`
- 风险评估:

## 5. 验证与结果

### 5.1 静态检查

- `ruff check src tests`
- `mypy src`

结果:
- [ ] 通过

### 5.2 测试

执行命令:

```bash
pytest -q <填入本次实际测试集>
```

结果:
- [ ] 通过
- 用例数:

### 5.3 人工验收

- [ ] `/assistant/v3/invoke`
- [ ] `/assistant/v3/stream`
- [ ] `/assistant/v3/runtime/doctor`
- [ ] `/assistant/v3/runtime/replay/{session_id}`

## 6. 发布与回滚

- Feature flags:
- 灰度策略: `1% -> 5% -> 20% -> 50% -> 100%`
- Gate 阈值:
1. `red_flag_miss_rate <= 0.01`
2. `p95_ms <= 6000`

回滚条件:
1. 医疗安全告警异常上升
2. gate 连续两窗口失败
3. 核心接口 SLO 越界且无法恢复

## 7. Reviewer 关注点

1. 
2. 
3. 

## 8. 附录

- 关键提交:
- 相关文档:
