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

When `v3_task_coordinator_enabled=true` and request is routed via v3 runtime mode, final payload additionally includes:

- `triage_level` (for example `ROUTINE`)
- `recommended_departments` (string array)
- `possible_causes` (string array, qualified wording)
- `red_flags` (string array)
- `disclaimer` (medical safety disclaimer)

Error final payload uses:

- `status: "error"`
- `error_message: "<message>"`
- HTTP status remains 200 for the stream transport (v2 parity), even when the final payload status is `error`.

## Done Marker

```text
data: [DONE]
```
