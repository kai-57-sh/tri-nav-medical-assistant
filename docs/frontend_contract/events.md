# Assistant v2 Stream Events

Endpoint: `POST /assistant/v2/stream`

Response headers:
- `Content-Type: text/event-stream`

The stream emits exactly three frames in order:

1. `status` event with `start` marker.
```text
event: status
data: {"status":"start","request_id":"req-...","session_id":"sess-..."}
```

2. `final` event with the same payload shape returned by `POST /assistant/v2/invoke`.
```text
event: final
data: {"status":"final|need_more_info|error","session_id":"...","response":"...","runtime_events":[...],"provenance":{...},"trace":{...}}
```

3. Done marker.
```text
data: [DONE]
```

Notes:
- The stream HTTP status is `200` even when the `final` payload contains `"status": "error"`.
- The frontend should stop reading after receiving `data: [DONE]`.
