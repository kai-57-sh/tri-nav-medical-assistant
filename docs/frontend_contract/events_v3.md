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
data: {"status":"final","session_id":"sess-...","trace_id":"trace-...","response":"...","safety":{"risk_level":"low|high","matched_rules":[...]},"runtime_events":[],"provenance":{},"trace":{}}
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
- `safety: {"risk_level": "low|high", "matched_rules": [...]}` (contract parity with invoke)
- HTTP status remains 200 for the stream transport (v2 parity), even when the final payload status is `error`.

## V4 Cutover Compatibility

For v4 rollout/canary configuration, deployment runtime settings must include:

- `v4_runtime_enabled=true`
- `v4_canary_enabled=true`
- `v4_gate_max_red_flag_miss_rate=0.01`

When v4 runtime is enabled but traffic still enters `POST /assistant/v3/stream`, the SSE protocol contract stays unchanged:

- frame order remains `status -> final -> [DONE]`
- `final` payload still contains `status/session_id/trace_id/response/safety/runtime_events/provenance/trace`
- gate or runtime failures are expressed by final payload `status: "error"` + `error_message`, while stream transport remains HTTP 200

## Done Marker

```text
data: [DONE]
```
