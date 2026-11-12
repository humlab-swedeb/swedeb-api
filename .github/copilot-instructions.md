# Swedeb API - AI Coding Instructions

Keep this file small and always-on. Put detailed guidance in `.github/instructions/*.instructions.md`.

## Sources of truth

- Start with `docs/DESIGN.md`, `docs/OPERATIONS.md`, and `docs/DEVELOPMENT.md` when relevant.
- Use current code, configuration, tests, workflows, and generated API definitions to verify behavior.
- `docs/proposals/` contains proposals and migration context, not current runtime truth. Ignore `docs/archive/` for implementation decisions.
- Use `docs/DIAGRAMS.md` for diagrams of the active runtime. Promote proposal diagrams there after implementation.

## Repository boundaries

- This repository is the Swedeb FastAPI backend. Routes, services, schemas, mappers, core logic, and active tests live under `api_swedeb/` and `tests/`.
- Prefer active code in `api_swedeb/api/` and `api_swedeb/core/`. Treat `api_swedeb/legacy/` as archived fallback code; change it only for explicit legacy work.
- Keep routers thin: inject a service, call it, map the result, and return a schema. Keep business logic in services or core modules and mappers pure.
- Do not add pass-through utility wrappers or new production logic to compatibility shims.
- Initialize configuration with `get_config_store().configure_context(source='config/config.yml')` before resolving settings. Read values with `ConfigValue("...").resolve()`. Update both production and test config when adding keys.

## Working approach

- Check the worktree and inspect only the relevant code and instructions. Preserve unrelated user changes.
- Fix the root cause with a narrow, repository-consistent change. Avoid speculative refactors and unrelated cleanup.
- Surface errors using existing conventions; do not hide failures with broad catches or silent fallbacks.
- Run the smallest relevant test or quality check, then broader checks when the change crosses boundaries.
- Do not claim success without fresh validation output. Report failures, skipped checks, and residual risks.
- Update documentation that directly describes changed behavior or workflow.

## Common commands

- `uv run uvicorn main:app --reload`
- `uv run pytest tests/`
- `make tidy`
- `make coverage`
- `make profile-kwic-pyinstrument`

## Task-specific instructions

- `coding-practices.instructions.md`: general change and verification practices
- `python.instructions.md`: FastAPI layers, configuration, CWB, data loading, and Python tests
- `testing.instructions.md`: test scope, fixtures, and validation guidance
- `design.instructions.md`, `diagrams.instructions.md`: design documentation and Mermaid diagrams
- `development.instructions.md`, `operations.instructions.md`: developer and runtime operations documentation
- `readme.instructions.md`: root README scope
- `proposal-writing-guide.instructions.md`, `proposal-document-structure.instructions.md`: proposals under `docs/proposals/`
- `phase-plan.instructions.md`, `task-plan.instructions.md`: planning and implementation handoff
- `writing-style.instructions.md`: technical prose and docstrings
- `github-workflow.instructions.md`: issues, commits, and branch workflow
