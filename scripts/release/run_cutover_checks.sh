#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_URL="${1:-http://127.0.0.1:8000}"
METRICS_FILE="${2:-$ROOT_DIR/tests/fixtures/release/canary_ok.json}"

cd "$ROOT_DIR"

pytest -q \
  tests/unit/test_server_v2.py \
  tests/unit/test_server_v2_stream.py \
  tests/unit/test_server_v3.py \
  tests/unit/test_server_v3_stream.py \
  tests/unit/test_server_v3_runtime_admin.py \
  tests/unit/test_v3 \
  tests/integration/test_shadow_compare.py \
  tests/integration/test_shadow_compare_v3.py \
  tests/evals/test_golden_cases.py

python scripts/release/check_canary_gate.py "$METRICS_FILE" 0.01 6000
curl -fsS "$BASE_URL/assistant/v3/runtime/doctor" >/tmp/trinav_runtime_doctor.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/trinav_runtime_doctor.json").read_text(encoding="utf-8"))
runtime = payload.get("runtime")
release = payload.get("release")

if payload.get("status") != "ok":
    raise SystemExit("runtime doctor status is not ok")
if not isinstance(runtime, dict) or runtime.get("v3_runtime_enabled") is not True:
    raise SystemExit("runtime doctor reports v3 runtime disabled")
if not isinstance(release, dict) or release.get("v4_canary_enabled") is not True:
    raise SystemExit("runtime doctor reports v4 canary disabled")
PY
