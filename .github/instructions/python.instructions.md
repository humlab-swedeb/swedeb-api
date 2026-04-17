---
description: "Use for Python, FastAPI, service, mapper, config, cache, and test work in swedeb-api."
name: "Python Backend"
---
# Python Backend

## Trust first

- Start with `docs/DESIGN.md`, `docs/OPERATIONS.md`, and `docs/DEVELOPMENT.md`.
- Treat `docs/change_requests/` as proposal and migration context, not authoritative runtime behavior, unless the user is working on proposal work.
- Ignore `docs/archive/` for implementation decisions.

## Architecture rules

- Keep routes thin: routers inject services, call one service method, then apply a mapper.
- Keep business logic in services or core modules, not in routers, schemas, or mappers.
- Keep mappers pure: DataFrame or domain result in, API schema out.
- Keep shared query parameter handling in `api_swedeb/api/utils/common_params.py`; do not add pass-through util wrappers.
- Use `api_swedeb/legacy/` only for explicit legacy-runtime tasks.
- Do not add new production logic to compatibility shims such as `api_swedeb/core/speech_text.py`.

## Where changes belong

- Endpoints: `api_swedeb/api/v1/endpoints/tool_router.py` and `metadata_router.py`
- Dependencies and singleton wiring: `api_swedeb/api/dependencies.py`
- Services: `api_swedeb/api/services/`
- Mappers: `api_swedeb/mappers/`
- API schemas: `api_swedeb/schemas/`
- Core CWB and corpus logic: `api_swedeb/core/`
- Active shared loaders: `api_swedeb/core/load.py`
- Legacy fallback runtime: `api_swedeb/legacy/`

## Configuration rules

- Initialize config with `get_config_store().configure_context(source='config/config.yml')`.
- Resolve settings with `ConfigValue("...").resolve()`.
- In tests, patch `api_swedeb.core.configuration.inject.get_config_store` instead of relying on the module-level alias.
- When adding config keys, update both `config/config.yml` and `tests/config.yml`.

## Service and API patterns

- Prefer direct `Depends(get_*_service)` injection.
- Reuse existing singleton dependency functions before adding new ones.
- If a new endpoint needs a new service, also add a dependency factory in `api_swedeb/api/dependencies.py`.
- Keep response models explicit and typed.
- Raise `HTTPException` for user-facing API errors.

## CWB and performance rules

- Route CWB query construction through the existing compiler and helpers; do not hand-roll parallel query logic in routers.
- Respect the existing KWIC multiprocessing model and its isolated `ccc.Corpus` worker behavior.
- Prefer Feather/Arrow for local columnar artifacts and large DataFrame persistence.
- Be cautious with memory growth around KWIC and speech indexes; avoid retaining large intermediate DataFrames longer than necessary.

## Testing and validation

- Use `uv run pytest tests/` for broad validation.
- Prefer targeted tests for the changed area first, then broader tests if you cross service or API boundaries.
- Add or update tests under `tests/api_swedeb/` for active runtime behavior.
- Keep legacy-only coverage under `tests/legacy/`.
- When changing config-dependent code, ensure test fixtures configure the store before objects that resolve config are created.

## Common changes

- New endpoint: schema → service method → dependency (if needed) → router → tests.
- Config change: config files → `ConfigValue` usage → tests.
- Performance change: profile first, then change query or load path, then re-test.
- Proposal/doc change: follow `docs/PROPOSAL_WRITING_GUIDE.md` and `docs/templates/PROPOSAL_TEMPLATE.md`.

## Commands

- `uv run uvicorn main:app --reload`
- `uv run pytest tests/`
- `make tidy`
- `make coverage`
- `make profile-kwic-pyinstrument`
