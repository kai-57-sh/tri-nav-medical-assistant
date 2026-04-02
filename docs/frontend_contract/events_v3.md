# Assistant V3 Stream Event Contract

`POST /assistant/v3/stream` returns `text/event-stream` using SSE frames.

## Frame Order

1. `event: status` with startup payload
2. `event: final` with invoke-like payload
3. `data: [DONE]`

## Status Event

Example:

```text
event: status
data: {"status":"start","request_id":"req-...","session_id":"sess-...","trace_id":"trace-..."}
```

## Final Event

Example:

```text
event: final
data: {"status":"final","session_id":"sess-...","trace_id":"trace-...","response":"...","runtime_events":[],"provenance":{},"trace":{}}
```

Error final payload uses:

- `status: "error"`
- `error_message: "<message>"`

## Done Marker

```text
data: [DONE]
```
