# Assistant v2 Stream Events

Endpoint: `POST /assistant/v2/stream`

Response headers:
- `Content-Type: text/event-stream`

The stream emits exactly three frames in order, each terminated by `\n\n`:

1. `status` event with `start` marker.
```text
event: status
data: {"status":"start","request_id":"req-...","session_id":"sess-..."}
```

2. `final` event.

- Normal path: same payload returned by `POST /assistant/v2/invoke`.
- Fallback path (stream-level exception or decode failure): invoke-like error payload with keys:
  `status`, `session_id`, `response`, `safety`, `runtime_events`, `provenance`, `trace`, `error_message`.

```text
event: final
data: {"status":"final|need_more_info|error","session_id":"...","response":"...","safety":{"risk_level":"low|high","matched_rules":[...]},"runtime_events":[...],"provenance":{...},"trace":{...},"error_message":"...?"}
```

3. Done marker.
```text
data: [DONE]
```

Notes:
- `status` is always first.
- `final` is always emitted exactly once.
- `data: [DONE]` is always emitted exactly once and always after `final`.
- Stream HTTP status is `200` even when `final` contains `"status": "error"`.
- Frontend should stop reading after receiving `data: [DONE]`.
