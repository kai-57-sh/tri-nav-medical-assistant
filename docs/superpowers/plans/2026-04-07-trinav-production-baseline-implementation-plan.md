# TriNav Production Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum deployment, health, CI, and configuration assets required to run TriNav safely in a small real production environment.

**Architecture:** Keep the existing FastAPI service shape, but expose operational endpoints (`/health/ready`, `/metrics`), add first-class container assets, add CI that runs backend tests plus frontend build, and normalize the environment template and docs so operators are configuring the same flags the code actually reads.

**Tech Stack:** FastAPI, Prometheus client, Docker, docker-compose, GitHub Actions, pytest, npm/Vite

---

### Task 1: Add Readiness and Metrics Endpoints

**Files:**
- Modify: `src/server.py`
- Modify: `src/utils/metrics.py`
- Modify: `tests/unit/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import AsyncMock, Mock, patch


def test_health_ready_reports_dependency_state(client):
    with patch("src.services.redis_service.get_redis_service", new_callable=AsyncMock) as mock_get_redis:
        mock_redis = Mock()
        mock_redis.is_healthy = True
        mock_get_redis.return_value = mock_redis

        with patch("src.services.llm_service.get_llm_service") as mock_get_llm:
            mock_llm = Mock()
            mock_llm.is_healthy = True
            mock_get_llm.return_value = mock_llm

            response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["dependencies"]["redis"]["healthy"] is True
    assert data["dependencies"]["llm"]["healthy"] is True


def test_metrics_endpoint_exposes_prometheus_text(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "trinav_requests_total" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server.py::test_health_ready_reports_dependency_state tests/unit/test_server.py::test_metrics_endpoint_exposes_prometheus_text -v`
Expected: FAIL because `/health/ready` and `/metrics` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# src/server.py
from fastapi import FastAPI, Response
from .utils.metrics import get_content_type, get_metrics


@app.get("/health/ready")
async def readiness_check() -> dict[str, object]:
    from .services.llm_service import get_llm_service
    from .services.redis_service import get_redis_service

    redis = await get_redis_service()
    llm = get_llm_service()
    redis_healthy = bool(redis and redis.is_healthy)
    llm_healthy = bool(llm and llm.is_healthy)
    ready = redis_healthy and llm_healthy

    return {
        "status": "ready" if ready else "degraded",
        "dependencies": {
            "redis": {"healthy": redis_healthy},
            "llm": {"healthy": llm_healthy},
        },
    }


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    return Response(content=get_metrics(), media_type=get_content_type())
```

```python
# src/utils/metrics.py
def get_metrics_text() -> str:
    return get_metrics().decode("utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/server.py src/utils/metrics.py tests/unit/test_server.py
git commit -m "feat(ops): add readiness and metrics endpoints"
```

### Task 2: Add Container Assets for App + Redis

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Write the failing verification command**

Run: `test -f Dockerfile && test -f docker-compose.yml && test -f .dockerignore`
Expected: FAIL because these files do not exist.

- [ ] **Step 2: Write minimal implementation**

```dockerfile
# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY src ./src
COPY docs ./docs
COPY specs ./specs
COPY README.md pyproject.toml .env.example run_server.py ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "src.server"]
```

```yaml
# docker-compose.yml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    build: .
    env_file:
      - .env
    depends_on:
      - redis
    ports:
      - "8000:8000"
```

```gitignore
# .dockerignore
.git
.venv
__pycache__
.pytest_cache
.mypy_cache
frontend/node_modules
frontend/dist
htmlcov
logs
.coverage
```

- [ ] **Step 3: Run verification commands**

Run: `docker compose config`
Expected: PASS with rendered Compose config.

Run: `docker build -t trinav:test .`
Expected: PASS with a tagged local image `trinav:test`.

- [ ] **Step 4: Smoke the containerized app**

Run: `docker compose up -d redis`
Expected: PASS and Redis container stays healthy.

Run: `docker run --rm --env-file .env -p 8000:8000 trinav:test`
Expected: App boots and serves `GET /health`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat(deploy): add container assets for production baseline"
```

### Task 3: Add CI and Smoke Scripts

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `scripts/ci/run_backend_checks.sh`
- Create: `scripts/smoke/check_v3_runtime.py`

- [ ] **Step 1: Write the failing verification command**

Run: `test -f .github/workflows/ci.yml && test -f scripts/ci/run_backend_checks.sh && test -f scripts/smoke/check_v3_runtime.py`
Expected: FAIL because the workflow and scripts do not exist.

- [ ] **Step 2: Write minimal implementation**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: bash scripts/ci/run_backend_checks.sh

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm run build
```

```bash
# scripts/ci/run_backend_checks.sh
#!/usr/bin/env bash
set -euo pipefail

pytest -q
ruff check src tests
mypy src
```

```python
# scripts/smoke/check_v3_runtime.py
from __future__ import annotations

import sys
import requests


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    doctor = requests.get(f"{base_url}/assistant/v3/runtime/doctor", timeout=5)
    invoke = requests.post(
        f"{base_url}/assistant/v3/invoke",
        json={"session_id": "smoke-v3", "text": "持续头痛两天"},
        timeout=15,
    )
    if doctor.status_code != 200 or invoke.status_code not in {200, 503}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run verification commands**

Run: `bash scripts/ci/run_backend_checks.sh`
Expected: PASS with test, lint, and type output.

Run: `python scripts/smoke/check_v3_runtime.py http://127.0.0.1:8000`
Expected: exit code `0` against a locally running server.

- [ ] **Step 4: Validate workflow syntax**

Run: `python - <<'PY'\nimport yaml, pathlib\nprint(yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())['name'])\nPY`
Expected: prints `CI`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/ci/run_backend_checks.sh scripts/smoke/check_v3_runtime.py
git commit -m "feat(ci): add backend and frontend baseline checks"
```

### Task 4: Normalize Environment Template and Operator Docs

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/DEVELOPER_GUIDE.md`
- Create: `tests/unit/test_config/test_env_template.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_env_example_contains_runtime_flags_and_no_legacy_weather_keys() -> None:
    text = Path(".env.example").read_text(encoding="utf-8")

    assert "V3_RUNTIME_ENABLED=" in text
    assert "V3_LEGACY_FALLBACK_ENABLED=" in text
    assert "V4_CANARY_ENABLED=" in text
    assert "WEATHER_API_URL" not in text
    assert "WEATHER_API_KEY" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config/test_env_template.py -v`
Expected: FAIL because the env template still contains old weather keys and misses new runtime flags.

- [ ] **Step 3: Write minimal implementation**

```ini
# .env.example
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=your_qwen_api_key_here
REDIS_URL=redis://localhost:6379
AMAP_API_KEY=your_amap_api_key_here
NCBI_BASE_URL=https://eutils.ncbi.nlm.nih.gov/entrez/eutils
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=trinav-dev
OTEL_EXPORTER_OTLP_ENDPOINT=
V2_RUNTIME_ENABLED=false
V2_SHADOW_COMPARE_ENABLED=false
V3_RUNTIME_ENABLED=true
V3_SHADOW_COMPARE_ENABLED=false
V3_TASK_COORDINATOR_ENABLED=true
V3_BUILTIN_PLUGINS_ENABLED=true
V3_LEGACY_FALLBACK_ENABLED=true
V4_CANARY_ENABLED=false
V4_GATE_MAX_RED_FLAG_MISS_RATE=0.01
V4_GATE_MAX_P95_MS=6000
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO
```

```markdown
# README.md
- 默认执行路径: `POST /assistant/invoke` -> v3 runtime compatibility adapter
- 旧 LangGraph: 仅用于 shadow compare / fallback
```

```markdown
# docs/API_REFERENCE.md
- `/assistant/invoke` 保持 LangServe 兼容 envelope，但内部默认委托到 v3 runtime
- `WEATHER_API_URL` / `WEATHER_API_KEY` 已废弃，天气数据统一使用 Open-Meteo
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config/test_env_template.py -v`
Expected: PASS

Run: `rg -n "WEATHER_API_URL|WEATHER_API_KEY" README.md docs/API_REFERENCE.md docs/DEVELOPER_GUIDE.md .env.example`
Expected: only historical migration notes remain, no active setup instructions.

- [ ] **Step 5: Commit**

```bash
git add .env.example README.md docs/API_REFERENCE.md docs/DEVELOPER_GUIDE.md tests/unit/test_config/test_env_template.py
git commit -m "docs(ops): align environment template and operator docs with v3 runtime"
```
