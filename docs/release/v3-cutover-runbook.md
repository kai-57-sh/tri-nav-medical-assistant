# TriNav v3 Cutover Runbook

> Scope: operate the public v3 runtime baseline with replayable diagnostics, canary-gate checks, and a documented rollback path.

## Stage 0: Preconditions

Confirm the deploy target is configured with the current v3 baseline and gate settings:

```ini
V3_RUNTIME_ENABLED=true
V3_TASK_COORDINATOR_ENABLED=true
V3_LEGACY_FALLBACK_ENABLED=true
V3_SHADOW_COMPARE_ENABLED=false
V3_BUILTIN_PLUGINS_ENABLED=true
V3_PLUGIN_TRACE_ENABLED=true
V3_PLUGIN_MEDICAL_FOOTER_ENABLED=true
V4_CANARY_ENABLED=true
V4_GATE_MAX_RED_FLAG_MISS_RATE=0.01
V4_GATE_MAX_P95_MS=6000
```

Operator checks before continuing:

- Confirm `/assistant/invoke` is already routed through the v3 compat path.
- Confirm the release owner can call `/assistant/v3/runtime/doctor` and `/assistant/v3/runtime/sessions/{session_id}/replay`.
- Confirm the rollback owner knows how to disable canary promotion and keep `V3_LEGACY_FALLBACK_ENABLED=true`.

## Stage 1: Pre-cutover Checks

Run the automated cutover check command from the repo root:

```bash
bash scripts/release/run_cutover_checks.sh http://127.0.0.1:8000 tests/fixtures/release/canary_ok.json
```

Expected outputs:

- The targeted pytest suite passes.
- `python scripts/release/check_canary_gate.py ...` prints JSON with `"allow": true` and `"exit_code": 0`.
- `/tmp/trinav_runtime_doctor.json` is written and includes `runtime`, `release`, `dependencies`, and `observability`.

Before proceeding, inspect the runtime doctor payload:

```bash
cat /tmp/trinav_runtime_doctor.json
```

Validate at minimum:

- `release.v4_canary_enabled` is `true`.
- `release.max_red_flag_miss_rate` is `0.01`.
- `release.max_p95_ms` is `6000`.
- The runtime block still reports the intended v3 flags.

## Stage 2: Traffic Ramp

Increase rollout in explicit stages:

- `1% -> 5% -> 20% -> 50% -> 100%`

At each stage:

- Re-check the current canary metrics with `python scripts/release/check_canary_gate.py`.
- Inspect `/assistant/v3/runtime/doctor` for release configuration drift.
- Sample replay data from a fresh session to confirm runtime events and snapshots are still readable.
- Stop promotion immediately if any rollback trigger is hit.

## Stage 3: Rollback Triggers

Rollback immediately when any of the following is observed:

- `red_flag_miss_rate > 0.01`
- `p95_ms > 6000`
- Medical safety alerts rise materially during the observation window.
- Core invoke or stream error rate exceeds the release SLO.
- Runtime replay or doctor endpoints stop returning current session state.

## Stage 4: Rollback Procedure

1. Stop traffic promotion and keep the rollout at the last known safe percentage.
2. Disable canary-based promotion for the active window:

```ini
V4_CANARY_ENABLED=false
```

3. Keep the stable v3 baseline enabled:

```ini
V3_RUNTIME_ENABLED=true
V3_TASK_COORDINATOR_ENABLED=true
V3_LEGACY_FALLBACK_ENABLED=true
```

4. Re-run the runtime doctor endpoint and confirm the rollback configuration is live.
5. Capture the failing canary metrics JSON and the latest `/tmp/trinav_runtime_doctor.json` for incident review.
