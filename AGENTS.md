# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Python backend (LangGraph/LangServe). Key subdirs: `src/chains/` (workflow + nodes), `src/models/`, `src/services/`, `src/utils/`, `src/config/`.
- `frontend/`: Vite + React client.
- `tests/`: pytest unit/integration/contract tests.
- `docs/`, `specs/`: architecture, API references, and design notes.
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`: backend dependencies and tooling config.

## Build, Test, and Development Commands
Backend (repo root):
- `python3.11 -m venv .venv && source .venv/bin/activate` to create the env.
- `pip install -r requirements.txt -r requirements-dev.txt` to install deps.
- `langchain serve src.chains.triage_chain:chain --port 8000` to run the API.
- `pytest` to run all tests.
- `black src tests`, `ruff check src tests`, `mypy src` for format/lint/type checks.

Frontend (from `frontend/`):
- `npm install` to install deps.
- `npm run dev` to start the UI (expects `http://localhost:8000`).
- `npm run build` to build production assets.
- `npm run lint` for ESLint checks.

## Coding Style & Naming Conventions
- Python: Black formatting (line length 100) and Ruff linting; keep types explicit (`mypy` strict).
- LangGraph nodes are `async def` functions, typically wrapped with `@safe_node`.
- Naming: `snake_case` for Python, `PascalCase` for React components, `camelCase` for JS/TS values.

## Testing Guidelines
- Framework: `pytest` with markers (`unit`, `integration`, `contract`, `slow`).
- Naming: files `test_*.py`, functions `test_*` (see `pyproject.toml`).
- Run targeted suites, e.g. `pytest tests/unit -v` or `pytest -m integration`.

## Commit & Pull Request Guidelines
- Recent commits use versioned summaries like `v1.5 ...` alongside plain descriptive messages. Use a short, imperative summary; include a `vX.Y` prefix when batching release-style changes.
- PRs should include a brief description, relevant test results, and UI screenshots when frontend behavior changes.

## Configuration & Secrets
- Copy `.env.example` to `.env` and set API keys locally. Do not commit secrets.
