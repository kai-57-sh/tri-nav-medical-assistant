#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

require_python_module() {
  local module="$1"

  if ! python -m "$module" --version >/dev/null 2>&1; then
    echo "Missing Python module for 'python -m $module'. Install requirements.txt plus the local QA tools in the active environment." >&2
    exit 127
  fi
}

cd "$ROOT_DIR"

require_python_module pytest
require_python_module mypy
require_python_module ruff

python -m pytest -q
python -m mypy src
python -m ruff check src tests
