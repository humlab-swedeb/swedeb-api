# Development Guide

## Purpose

This guide is the main developer-facing reference for contributing to the Swedeb API codebase. It focuses on local setup, repository-specific development practices, validation steps, and the workflow contributors are expected to follow while making day-to-day changes.

It is not the deployment or runtime operations runbook. Environment rollout, release flow, rollback, backup, and incident handling belong in [OPERATIONS.md](./OPERATIONS.md).

## Table of Contents

- [Development Guide](#development-guide)
  - [Purpose](#purpose)
  - [Table of Contents](#table-of-contents)
  - [Audience and Scope](#audience-and-scope)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Local Configuration](#local-configuration)
  - [Project Structure](#project-structure)
  - [Common Development Commands](#common-development-commands)
  - [Code Quality Checks](#code-quality-checks)
  - [Development Workflow](#development-workflow)
    - [Branch and PR flow](#branch-and-pr-flow)
    - [Commit conventions](#commit-conventions)
    - [Before opening a PR](#before-opening-a-pr)
  - [Database and Migration Workflow](#database-and-migration-workflow)
  - [Debugging and Troubleshooting](#debugging-and-troubleshooting)
    - [Background Task Execution (KWIC)](#background-task-execution-kwic)
  - [Local Debug Modes](#local-debug-modes)
      - [Step 1 — Start the backend.](#step-1--start-the-backend)
      - [Step 2 — Configure the frontend dev server to proxy API calls.](#step-2--configure-the-frontend-dev-server-to-proxy-api-calls)
      - [Step 3 — Start the frontend dev server.](#step-3--start-the-frontend-dev-server)
    - [Mode 2 — Backend serving a locally built frontend](#mode-2--backend-serving-a-locally-built-frontend)
      - [Step 1 — Build the frontend.](#step-1--build-the-frontend)
      - [Step 2 — Start the backend with static files.](#step-2--start-the-backend-with-static-files)
  - [Development Best Practices](#development-best-practices)
  - [Related Documents](#related-documents)

## Audience and Scope

This document is for contributors working in the repository.

It covers:

- local setup and bootstrap
- repository structure
- config files used during development and testing
- common commands for running, testing, formatting, and profiling
- repository-specific workflow expectations such as branch targets and commit conventions

It does not cover:

- production deployment procedures
- release or rollback operations
- runtime monitoring and incident handling
- endpoint-by-endpoint API documentation
- detailed CI/CD internals beyond what contributors need to know for day-to-day work

Treat `docs/archive/` as historical reference only, not as the source of truth for current development practice.

## Prerequisites

- Python 3.13
- `uv`
- access to local corpus and metadata assets if you want to run the app against non-test data
- Docker or Podman only if you are working on container-related development tasks

Helpful references:

- [.python-version](../.python-version)
- [pyproject.toml](../pyproject.toml)
- [README.md](../README.md)

## Local Setup

1. Clone the repository and enter it.
2. Install the project and development dependencies.
3. Confirm or override the config file you want to use for local runs.
4. Start the API locally.

Recommended setup:

```bash
git clone https://github.com/humlab-swedeb/swedeb-api.git
cd swedeb-api
uv sync --extra dev
uv run uvicorn main:app --reload
```

The local API docs are then available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

If you are only running tests, the repository already contains test data and `tests/config.yml`.

## Local Configuration

The application reads configuration from `SWEDEB_CONFIG_PATH`, defaulting to `config/config.yml` when the variable is not set.

Relevant config files:

- `config/config.yml`: default checked-in runtime config
- `config/debug.config.yml`: alternate checked-in config for development use
- `tests/config.yml`: test config

Useful patterns:

```bash
export SWEDEB_CONFIG_PATH=config/debug.config.yml
uv run uvicorn main:app --reload
```

Development rules for config work:

- initialize config through `get_config_store().configure_context(...)`
- use `ConfigValue("...").resolve()` for config reads
- when adding config keys, update both `config/config.yml` and `tests/config.yml`
- in tests, patch `api_swedeb.core.configuration.inject.get_config_store` rather than relying on the module-level alias
- `config/debug.config.yml` sets `development.celery_enabled: false` and `kwic.use_multiprocessing: false`; this keeps local development free of a Redis dependency and allows the VS Code debugger to attach directly to KWIC execution

Test configuration is also managed dynamically in [tests/conftest.py](../tests/conftest.py), which generates session-scoped test config and registry files for some test paths.

## Project Structure

The main repository areas contributors usually touch are:

```text
api_swedeb/
  api/v1/endpoints/   API routes
  api/services/       service layer
  api/dependencies.py singleton dependency wiring
  core/               config, CWB, corpus loading, KWIC, n-grams
  mappers/            domain/dataframe to schema transforms
  schemas/            request/response models
  legacy/             archived fallback runtime
  workflows/          offline or build-time workflows
tests/
  api_swedeb/         active runtime tests
  integration/        integration tests
  legacy/             legacy-only tests
docs/
  DEVELOPMENT.md      developer guide
  OPERATIONS.md       operations/runbook guide
  DESIGN.md           architecture and design context
```

Repository-specific architectural conventions:

- keep routers thin
- keep business logic in services or core modules
- keep mappers pure
- avoid pass-through util wrappers
- use `api_swedeb/legacy/` only for explicit legacy-runtime work

## Common Development Commands

```bash
uv run uvicorn main:app --reload
uv run pytest tests/
make run
make test
make coverage
make clean-dev
make profile-kwic-pyinstrument
```

To start a Celery worker for production-mode KWIC testing (requires a running Redis):

```bash
celery -A api_swedeb.celery_tasks worker --loglevel=info
# or via uv:
uv run celery -A api_swedeb.celery_tasks worker --loglevel=info
```

To start Redis locally:

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

Additional useful commands:

```bash
make sqlite-db
make sqlite-test-db
make build-test-speech-corpus
make build-speech-corpus
```

Use the build-related targets only when your work touches corpus build pipelines, speech corpus generation, or metadata inspection.

## Code Quality Checks

Primary checks:

```bash
make tidy
make ruff
make pylint
make notes
```

What they do:

- `make tidy`: runs Black and isort
- `make ruff`: runs Ruff with `--fix`
- `make pylint`: runs pylint over the main source folders
- `make notes`: finds `FIXME`, `XXX`, and `TODO` markers

The standard pre-PR baseline is:

1. run targeted tests for the changed area
2. run broader tests if the change crosses service, config, router, or corpus boundaries
3. run `make tidy`

Type-check configuration exists in [pyproject.toml](../pyproject.toml), but the repository does not currently define a single standard type-check command in the documented development workflow.

## Development Workflow

Use the normal contributor path unless the task explicitly targets release or operations work.

At a high level, development flows into `dev`, while promotion beyond `dev` proceeds through `test`, `staging`, and `main`. Contributors should usually think in terms of preparing a clean change for `dev`; environment promotion and deployment remain operational concerns documented in [OPERATIONS.md](./OPERATIONS.md).

### Branch and PR flow

- create feature or fix branches from `dev`
- open pull requests back to `dev`
- treat `test`, `staging`, and `main` as promotion branches rather than day-to-day feature branches

Quick branch reference:

- `dev`: default integration branch for development work
- `test`, `staging`, `main`: promotion and release branches

Detailed environment promotion belongs in [OPERATIONS.md](./OPERATIONS.md), not here.

### Commit conventions

Use Conventional Commits:

```text
<type>[optional scope]: <description>
```

Common examples:

- `feat: add new API endpoint`
- `fix: resolve metadata lookup issue`
- `docs: update development guide`
- `chore: update dev tooling`
- `feat!: change kwic response shape`

Use a `BREAKING CHANGE:` footer when needed.

### Before opening a PR

- run the relevant tests locally
- run `make tidy`
- keep schema, service, route, and test changes in sync
- update `docs/DEVELOPMENT.md` if setup, commands, config guidance, or workflow expectations changed
- update `docs/OPERATIONS.md` instead if the change affects runtime environments or deployment behavior

## Database and Migration Workflow

There is no formal application migration framework documented in this repository.

Instead, development typically works with:

- versioned metadata stored in SQLite
- versioned corpus assets
- configuration changes that point the application at the correct versions and paths

Developer implications:

- inspect metadata databases with `make sqlite-db` and `make sqlite-test-db`
- keep metadata and corpus versions aligned with config values
- treat changes to metadata expectations and corpus layout as data/config work, not ORM migration work
- when changing config keys or expected config structure, update both `config/config.yml` and `tests/config.yml`

If your change affects speech corpus build outputs, use the speech-corpus build targets in the `Makefile` and validate the affected tests.

## Background Task Execution (KWIC)

KWIC ticket queries use one of two execution paths, controlled by `development.celery_enabled` in the active config file.

| Mode | Config | Execution | Multiprocessing | Redis required |
|------|--------|-----------|-----------------|----------------|
| Development | `debug.config.yml` (`celery_enabled: false`) | FastAPI `BackgroundTasks` | No | No |
| Production | `config.yml` (`celery_enabled: true`) | Celery worker process | Yes (`num_processes: 8`) | Yes |

**Development mode** is the default for local work. No Redis or Celery worker is needed; KWIC queries run inline in the FastAPI process. The VS Code debugger works normally — set breakpoints in `kwic_ticket_service.py` and they will be hit.

**Production mode** requires Redis and at least one running Celery worker. The API process enqueues a task via `celery_app.send_task("api_swedeb.execute_kwic_ticket", ...)` and returns immediately. The worker picks up the task and runs the query with multiprocessing enabled. Task state is read back through `celery_app.AsyncResult(ticket_id)`.

Debugging in production mode: attach the debugger to the Celery worker process instead of the FastAPI process, or switch to development mode temporarily.

## Debugging and Troubleshooting

Useful first checks during development:

- confirm the API starts and `/docs` loads
- run the narrowest relevant pytest target first
- inspect [tests/conftest.py](../tests/conftest.py) when config-driven tests behave unexpectedly
- use `make clean-dev` to remove build and test artifacts before retrying a broken local environment

Repository-specific troubleshooting notes:

- if a fixture or object resolves `ConfigValue(...)` too early, ensure the config store is configured before construction
- if a change affects CWB or KWIC performance, profile it with `make profile-kwic-pyinstrument`
- if a change affects test data or metadata-driven behavior, compare `config/config.yml`, `tests/config.yml`, and the generated test config path in `tests/output/`
- use `/docs` and `/redoc` to confirm request/response contracts quickly during API work

### Local Debug Modes

Two non-Docker modes for running the backend with the VS Code debugger (F5 / **Run and Debug** panel), avoiding a separate `uvicorn` terminal command.

`.vscode/launch.json` defines two named configurations:

- **FastAPI: backend only** — API on `http://localhost:8000`, no static files served; pair with the frontend dev server
- **FastAPI: backend + static frontend** — API + locally built frontend assets mounted at `/public`

Both configs load `config/debug.config.yml` via `SWEDEB_CONFIG_PATH`. `--reload` is intentionally omitted — uvicorn's file-watcher forks a child process that the debugger does not follow, so breakpoints would never be hit. Restart the debug session manually after code changes.

------------------

### Mode 1 — Backend with a separate frontend dev server

Use when iterating on backend and frontend simultaneously and you want hot-reload on both sides.

#### Step 1 — Start the backend.
Select **FastAPI: backend only** and press F5. The API starts on `http://localhost:8000` with reload enabled.

#### Step 2 — Configure the frontend dev server to proxy API calls.
The Quasar dev server runs on port 8080. By default, `process.env.API` is `/v1` (same-origin), so API calls will not reach the backend. Add a proxy to the `devServer` block in `quasar.config.js`:

```js
devServer: {
  // ...existing options...
  proxy: {
    '/v1': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

This is a local convenience change. Do not commit the proxy config unless the project intentionally adopts it.

#### Step 3 — Start the frontend dev server.

```bash
cd ../swedeb_frontend
pnpm dev
```

The browser opens at `http://localhost:8080`. API requests are proxied to the backend.

------------------

### Mode 2 — Backend serving a locally built frontend

Use when you want to test the complete app as a single origin without Docker.

#### Step 1 — Build the frontend.

```bash
cd ../swedeb_frontend
pnpm build
```

This produces `dist/spa/` inside the `swedeb_frontend` directory.

#### Step 2 — Start the backend with static files.
Select **FastAPI: backend + static frontend** and press F5. The launch config sets `STATIC_DIR` to `<workspace>/../swedeb_frontend/dist/spa`. `main.py` passes it to `create_app(static_dir=...)`, which mounts the assets at `/public`.

Open `http://localhost:8000/public/index.html` in a browser. All API and frontend traffic is served from the same origin on port 8000.

## Development Best Practices

- Use Conventional Commits so release automation and changelog generation remain predictable.
- Treat `dev` as the normal integration target for development work.
- Validate changes locally before opening a PR, starting with targeted tests and then broader checks when needed.
- Keep code, tests, and developer documentation in sync when local workflow or setup expectations change.

## Related Documents

- [README.md](../README.md) for project overview and quick start
- [DESIGN.md](./DESIGN.md) for architecture and design context
- [OPERATIONS.md](./OPERATIONS.md) for deployment and runtime operations
- [AGENTS.md](../AGENTS.md) for repository-specific coding and testing expectations
- `docs/TESTING.md` is not present yet; use [AGENTS.md](../AGENTS.md), [tests/conftest.py](../tests/conftest.py), and the test tree for current test-specific guidance
