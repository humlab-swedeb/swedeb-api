# Swedeb API - AI Coding Instructions

This file should stay small and always-on. Put detailed backend guidance in `.github/instructions/*.instructions.md` so it loads only when relevant.

## Documentation scope

- Trust current runtime and deployment docs in `docs/`.
- Start with `docs/DESIGN.md`, `docs/OPERATIONS.md`, and `docs/DEVELOPMENT.md`.
- For proposal work, use `docs/PROPOSAL_WRITING_GUIDE.md` and `docs/templates/PROPOSAL_TEMPLATE.md`.
- Treat `docs/change_requests/` as design and migration context, not source of truth for current behavior, unless the task is explicitly proposal-related.
- Ignore `docs/archive/` for implementation decisions.

## Repository structure

Swedeb API is a FastAPI backend with a direct service-injection architecture.

- `api_swedeb/api/v1/endpoints/`: API routes
- `api_swedeb/api/services/`: service layer
- `api_swedeb/api/dependencies.py`: singleton dependency wiring
- `api_swedeb/mappers/`: DataFrame-to-schema mappers
- `api_swedeb/schemas/`: API response and request models
- `api_swedeb/core/`: active corpus, CWB, config, and load logic
- `api_swedeb/legacy/`: archived fallback runtime; debug-only unless the task explicitly targets it
- `tests/api_swedeb/` and `tests/integration/`: active runtime tests
- `tests/legacy/`: legacy-only coverage

## Always-on architecture rules

### Router, service, mapper boundaries

- Keep routers thin: inject a service, call a service method, apply a mapper, return a schema.
- Keep business logic out of routers and mappers.
- Keep mappers pure and schema-focused.
- Do not add pass-through util wrappers around service calls.

### Active vs legacy code

- Prefer active runtime code in `api_swedeb/api/` and `api_swedeb/core/`.
- Use `api_swedeb/legacy/` only for explicit legacy-runtime work.
- Do not add new production behavior to compatibility shims.

### Configuration and data access

- Initialize config with `get_config_store().configure_context(source='config/config.yml')` before resolving settings.
- Use `ConfigValue("...").resolve()` for configuration reads.
- When adding config keys, update both `config/config.yml` and `tests/config.yml`.
- Prefer Feather/Arrow-backed storage patterns already used in the repo.

## Workflow expectations

- Use the repository virtual environment and existing Make/uv commands.
- Common commands:
  - `uv run uvicorn main:app --reload`
  - `uv run pytest tests/`
  - `make tidy`
  - `make coverage`
  - `make profile-kwic-pyinstrument`
- Run targeted tests for the changed area before finishing.
- Run broader tests when a change crosses router, service, config, or corpus boundaries.
- Validate config-driven changes with the test config as well as production config files.

## Code conventions

- Follow the existing FastAPI + service + mapper pattern.
- Keep changes minimal and local to the correct layer.
- Use explicit types and response models.
- Raise `HTTPException` for user-facing API errors.
- Use `loguru` for logging where the codebase already does.
- Prefer absolute imports within the package.
- Use Black/isort style via `make tidy`.

## Safe change defaults

- Add new API behavior in services and schemas before touching routers.
- Reuse existing dependency factories and mappers before introducing new abstractions.
- Prefer extending active modules over creating parallel code paths.
- If a task touches CWB, config, speech loading, or request contracts, check the relevant docs first and test the affected path directly.
- When a change only applies to rollback or forensic debugging, keep it in `api_swedeb/legacy/` and do not mix it into active runtime code.

## Validation before finishing

- Run at least one targeted test for the changed area.
- Run broader tests when you cross API, config, or corpus boundaries.
- Keep unrelated user changes untouched.
- Call out config updates, migration effects, or residual risks in the handoff.

## Task-specific instructions

Use the targeted files under `.github/instructions/` instead of expanding this file again:

- `python.instructions.md`: backend architecture, config, CWB, testing, and Python change patterns
- `github-workflow.instructions.md`: issue creation, staging discipline, and commit message rules
- `operations.instructions.md`: operations-doc scope, environments, runtime config, CI/CD, observability, and recovery documentation
