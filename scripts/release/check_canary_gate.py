"""CLI for evaluating TriNav canary gate metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.release.ops.gate_report import build_gate_report


def main() -> int:
    """Load metrics from disk, print the report, and exit with gate status."""

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
