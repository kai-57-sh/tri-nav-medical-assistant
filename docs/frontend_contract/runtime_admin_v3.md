# Assistant V3 Runtime Admin Contract

`/assistant/v3/runtime` 提供运行态诊断、会话回放与恢复接口，服务于灰度发布与故障排查。

## Endpoints

### `GET /assistant/v3/runtime/doctor`

返回运行时开关与依赖健康状态。

响应示例：

```json
{
  "status": "ok",
  "runtime": {
    "v3_runtime_enabled": true,
    "v3_shadow_compare_enabled": false
  },
  "dependencies": {
    "redis": {
      "healthy": true
    }
  },
  "observability": {
    "sessions_with_events": 12,
    "total_runtime_events": 126,
    "sessions_with_snapshots": 8
  }
}
```

### `GET /assistant/v3/runtime/sessions/{session_id}/replay`

返回会话的最新快照与运行事件列表。

成功响应示例：

```json
{
  "session_id": "sess-123",
  "snapshot": {
    "status": "final",
    "response": "..."
  },
  "runtime_events": [
    {
      "event_type": "runtime_started"
    },
    {
      "event_type": "runtime_finished"
    }
  ],
  "can_resume": true
}
```

失败响应（会话不存在）：

```json
{
  "detail": "session_not_found"
}
```

### `GET /assistant/v3/runtime/plugins`

返回当前注册的 runtime plugin 名称列表。

响应示例：

```json
{
  "plugins": ["trace_metadata", "medical_footer"],
  "count": 2
}
```

### `POST /assistant/v3/runtime/sessions/{session_id}/resume`

在固定 `session_id` 下继续问诊。

请求示例：

```json
{
  "text": "补充信息：没有发热",
  "metadata": {
    "source": "web"
  }
}
```

成功响应为 `POST /assistant/v3/invoke` 同构 payload。

失败响应（会话不存在）：

```json
{
  "detail": "session_not_found"
}
```
