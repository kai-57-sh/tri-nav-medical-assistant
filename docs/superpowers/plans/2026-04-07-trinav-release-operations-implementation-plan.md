# TriNav Release Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn existing shadow compare, canary gate, replay, and runtime admin pieces into an auditable cutover-and-rollback workflow for v3 production releases.

**Architecture:** Keep the current runtime admin and canary gate primitives, but add a release-ops layer that can load metrics, evaluate cutover safety, expose runtime gate config through the admin API, and run one repeatable cutover command that operators can execute before each rollout stage.

**Tech Stack:** Python 3.11+, FastAPI admin endpoints, existing `CanaryGate`, pytest, shell release scripts, Markdown runbooks

---

### Task 1: Add a Machine-Readable Canary Gate Report Library and CLI

**Files:**
- Create: `src/release/ops/gate_report.py`
- Create: `scripts/release/check_canary_gate.py`
- Create: `tests/unit/test_release/test_gate_report.py`

- [ ] **Step 1: Write the failing test**

```python
from src.release.ops.gate_report import build_gate_report


def test_build_gate_report_returns_exit_code_and_reason() -> None:
    report = build_gate_report(
        metrics={"red_flag_miss_rate": 0.02, "p95_ms": 4200},
        max_red_flag_miss_rate=0.01,
        max_p95_ms=6000,
    )

    assert report["allow"] is False
    assert report["reason"] == "red_flag_miss_rate_exceeded"
    assert report["exit_code"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_release/test_gate_report.py -v`
Expected: FAIL because `src.release.ops.gate_report` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/release/ops/gate_report.py
from __future__ import annotations

from typing import Any

from src.release.canary.gate import CanaryGate


def build_gate_report(
    *,
    metrics: dict[str, Any],
    max_red_flag_miss_rate: float,
    max_p95_ms: int,
) -> dict[str, object]:
    decision = CanaryGate(
        max_red_flag_miss_rate=max_red_flag_miss_rate,
        max_p95_ms=max_p95_ms,
    ).evaluate(metrics)
    return {
        "allow": decision.allow,
        "reason": decision.reason,
        "metrics": metrics,
        "exit_code": 0 if decision.allow else 1,
    }
```

```python
# scripts/release/check_canary_gate.py
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.release.ops.gate_report import build_gate_report


def main() -> int:
    metrics_path = Path(sys.argv[1])
    max_red_flag_miss_rate = float(sys.argv[2])
    max_p95_ms = int(sys.argv[3])
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    report = build_gate_report(
        metrics=metrics,
        max_red_flag_miss_rate=max_red_flag_miss_rate,
        max_p95_ms=max_p95_ms,
    )
    print(json.dumps(report, ensure_ascii=False))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_release/test_gate_report.py -v`
Expected: PASS

Run: `python - <<'PY'\nimport json, pathlib\npath = pathlib.Path('/tmp/canary_ok.json')\npath.write_text(json.dumps({'red_flag_miss_rate': 0.002, 'p95_ms': 4100}), encoding='utf-8')\nPY\npython scripts/release/check_canary_gate.py /tmp/canary_ok.json 0.01 6000`
Expected: prints JSON report with `"exit_code": 0`.

- [ ] **Step 5: Commit**

```bash
git add src/release/ops/gate_report.py scripts/release/check_canary_gate.py tests/unit/test_release/test_gate_report.py
git commit -m "feat(release): add canary gate reporting cli"
```

### Task 2: Expose Release Gate Configuration from Runtime Admin

**Files:**
- Modify: `src/interfaces/api/runtime_admin_v3.py`
- Modify: `tests/unit/test_server_v3_runtime_admin.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_doctor_v3_returns_canary_gate_configuration(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.interfaces.api.runtime_admin_v3.get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "v3_runtime_enabled": True,
                "v3_shadow_compare_enabled": False,
                "v4_canary_enabled": True,
                "v4_gate_max_red_flag_miss_rate": 0.01,
                "v4_gate_max_p95_ms": 6000,
            },
        )(),
    )

    response = client.get("/assistant/v3/runtime/doctor")
    body = response.json()

    assert body["release"]["v4_canary_enabled"] is True
    assert body["release"]["max_red_flag_miss_rate"] == 0.01
    assert body["release"]["max_p95_ms"] == 6000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_v3_runtime_admin.py::test_runtime_doctor_v3_returns_canary_gate_configuration -v`
Expected: FAIL because the `release` block is missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/interfaces/api/runtime_admin_v3.py
return {
    "status": "ok" if settings.v3_runtime_enabled else "disabled",
    "runtime": {
        "v3_runtime_enabled": settings.v3_runtime_enabled,
        "v3_shadow_compare_enabled": settings.v3_shadow_compare_enabled,
    },
    "release": {
        "v4_canary_enabled": settings.v4_canary_enabled,
        "max_red_flag_miss_rate": settings.v4_gate_max_red_flag_miss_rate,
        "max_p95_ms": settings.v4_gate_max_p95_ms,
    },
    "dependencies": {
        "redis": {"healthy": redis_healthy},
    },
    "observability": await _resolve_maybe_awaitable(get_runtime_store_summary()),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_v3_runtime_admin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/interfaces/api/runtime_admin_v3.py tests/unit/test_server_v3_runtime_admin.py
git commit -m "feat(release): expose canary gate config in runtime doctor"
```

### Task 3: Automate the Pre-Cutover Check Command

**Files:**
- Create: `scripts/release/run_cutover_checks.sh`
- Create: `tests/fixtures/release/canary_ok.json`
- Create: `tests/fixtures/release/canary_block.json`

- [ ] **Step 1: Write the failing verification command**

Run: `test -f scripts/release/run_cutover_checks.sh`
Expected: FAIL because the cutover script does not exist.

- [ ] **Step 2: Write minimal implementation**

```bash
# scripts/release/run_cutover_checks.sh
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
METRICS_FILE="${2:-tests/fixtures/release/canary_ok.json}"

pytest -q tests/unit/test_server_v2.py tests/unit/test_server_v2_stream.py tests/unit/test_server_v3.py tests/unit/test_server_v3_stream.py tests/unit/test_server_v3_runtime_admin.py tests/unit/test_v3 tests/integration/test_shadow_compare.py tests/integration/test_shadow_compare_v3.py tests/evals/test_golden_cases.py
python scripts/release/check_canary_gate.py "$METRICS_FILE" 0.01 6000
curl -fsS "$BASE_URL/assistant/v3/runtime/doctor" >/tmp/trinav_runtime_doctor.json
```

```json
// tests/fixtures/release/canary_ok.json
{
  "red_flag_miss_rate": 0.002,
  "p95_ms": 4100
}
```

```json
// tests/fixtures/release/canary_block.json
{
  "red_flag_miss_rate": 0.04,
  "p95_ms": 4100
}
```

- [ ] **Step 3: Run verification commands**

Run: `bash -n scripts/release/run_cutover_checks.sh`
Expected: PASS with no shell syntax errors.

Run: `python scripts/release/check_canary_gate.py tests/fixtures/release/canary_block.json 0.01 6000`
Expected: exit code `1` and JSON payload with `"reason": "red_flag_miss_rate_exceeded"`.

- [ ] **Step 4: Exercise the happy path**

Run: `bash scripts/release/run_cutover_checks.sh http://127.0.0.1:8000 tests/fixtures/release/canary_ok.json`
Expected: all pytest suites pass, canary gate exits `0`, runtime doctor JSON is written to `/tmp/trinav_runtime_doctor.json`.

- [ ] **Step 5: Commit**

```bash
git add scripts/release/run_cutover_checks.sh tests/fixtures/release/canary_ok.json tests/fixtures/release/canary_block.json
git commit -m "feat(release): automate pre-cutover checks"
```

### Task 4: Write the Operator Runbook and Align the Existing Checklist

**Files:**
- Create: `docs/release/v3-cutover-runbook.md`
- Modify: `docs/release/v4-cutover-checklist.md`

- [ ] **Step 1: Write the failing verification command**

Run: `test -f docs/release/v3-cutover-runbook.md`
Expected: FAIL because the runbook does not exist.

- [ ] **Step 2: Write minimal implementation**

```markdown
# docs/release/v3-cutover-runbook.md
# TriNav v3 Cutover Runbook

## Stage 0: Preconditions
- Confirm `V3_RUNTIME_ENABLED=true`
- Confirm `V3_TASK_COORDINATOR_ENABLED=true`
- Confirm `V3_LEGACY_FALLBACK_ENABLED=true`
- Confirm `V4_CANARY_ENABLED=true`

## Stage 1: Pre-cutover checks
~~~bash
bash scripts/release/run_cutover_checks.sh http://127.0.0.1:8000 tests/fixtures/release/canary_ok.json
~~~

## Stage 2: Traffic ramp
- 1%
- 5%
- 20%
- 50%
- 100%

## Stage 3: Rollback triggers
- `red_flag_miss_rate > 0.01`
- `p95_ms > 6000`
- medical safety alerts increase materially
```

```markdown
# docs/release/v4-cutover-checklist.md
- [ ] 已执行 `bash scripts/release/run_cutover_checks.sh http://127.0.0.1:8000 tests/fixtures/release/canary_ok.json`
- [ ] `docs/release/v3-cutover-runbook.md` 已由值班工程师过目
```

- [ ] **Step 3: Verify the docs**

Run: `rg -n "run_cutover_checks.sh|V3_LEGACY_FALLBACK_ENABLED|100%" docs/release/v3-cutover-runbook.md docs/release/v4-cutover-checklist.md`
Expected: matching lines are found in both files.

- [ ] **Step 4: Sanity-read the rendered Markdown**

Run: `sed -n '1,220p' docs/release/v3-cutover-runbook.md`
Expected: runbook contains preconditions, pre-cutover command, traffic ramp, and rollback section.

- [ ] **Step 5: Commit**

```bash
git add docs/release/v3-cutover-runbook.md docs/release/v4-cutover-checklist.md
git commit -m "docs(release): add v3 cutover runbook"
```
