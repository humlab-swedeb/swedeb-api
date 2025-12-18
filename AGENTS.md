# AGENT INSTRUCTIONS - Swedeb API

## Scope & Ownership
- Build, test, and optimize the FastAPI backend that exposes Swedish parliamentary debate data backed by IMS Open Corpus Workbench (CWB) and Penelope corpora.
- Maintain compatibility with historical data (1867–present) from the SWERIK project and the existing directory layout.
- Keep Codex instructions authoritative; treat this file as mandatory context before every task.

## Configuration & Startup
- Always initialize the configuration context via `ConfigStore.configure_context(source='config/config.yml')` (use `tests/config.yml` inside tests) before reading any configuration value.
- Resolve configuration values with `ConfigValue("path.to.key").resolve()` using dot notation and respect custom YAML constructors `!jj` and `!join` plus the `PYRIKSPROT_` env override prefix.
- Keep environment variables (`DATA_DIR`, `METADATA_FILENAME`, `TAGGED_CORPUS_FOLDER`, `FOLDER`, `TAG`, `KWIC_CORPUS_NAME`, `KWIC_DIR`) defined and absolute when referencing corpus assets.
- Validate CWB registry/data directories exist prior to issuing queries and configure per-environment paths consistently.

## Data Loading & Storage (`api_swedeb/core/`)
- Use `api_swedeb/core/load.py` helpers to load speech indexes and DTMs; check the feather cache via `is_invalidated(source, target)` before falling back to CSV.gz.
- Honor `USED_COLUMNS` and `SKIP_COLUMNS` to minimize memory and keep load times acceptable.
- Keep document-term matrices based on `penelope.corpus.VectorizedCorpus` and manage token vocabularies through the provided token2id mappings.

## API Design (`api_swedeb/api/`)
- Register routes only in `tool_router.py` (`/v1/tools`) or `metadata_router.py` (`/v1/metadata`) and reuse shared dependency helpers (`get_shared_corpus`, `get_cwb_corpus`, `get_corpus_decoder`).
- Inject reusable query parameters via `CommonQueryParams` (KWIC filters, year ranges, etc.) and follow FastAPI Depends patterns for singleton resources.
- Keep KWIC, word trends, n-grams, and speech retrieval endpoints performant by enforcing cutoffs (default `cut_off=200000`) and cached corpora.

## CWB Integration (`api_swedeb/core/cwb/`)
- Build CQP expressions through `cwb/compiler.py` and execute via the `ccc` package; never bypass the compiler when constructing queries.
- Route all CWB access through validated registry/data directories and keep `/tmp/ccc-*` isolated per test to avoid shared-state pollution.

## Testing & Tooling
- Run `poetry run uvicorn main:app --reload` for local dev, `poetry run pytest tests/` for test suites, and `make tidy` (Black + isort) before every commit; `make black` and `make isort` remain available when partial formatting is needed.
- Generate coverage with `make coverage` when verifying broad changes and profile KWIC workloads via `make profile-kwic-pyinstrument` (output lives in `tests/output/`).
- Rely on fixtures from `tests/conftest.py`: use cached corpus fixtures for module scope and clone them for function scope to ensure isolation (`speech_index`, `person_codecs`, etc.).

## Git Workflow & Releases
- Follow the four-branch deployment flow: feature PRs → `dev`, promote sequentially `dev`→`test`→`staging`→`main`, and expect only `test`, `staging`, `main` to trigger CI/CD builds.
- Keep commits in Conventional Commit format (`feat:`, `fix:`, `docs:`, `chore:`) and declare `BREAKING CHANGE:` footers when necessary to drive semantic-release version bumps.
- Build Docker images solely through `.github/scripts/build-and-push-image.sh`; expect runtime frontend assets to be fetched by `download-frontend.sh` and push outputs to `ghcr.io/humlab-swedeb/swedeb-api` with environment-specific compose files (`compose.test.yml`, `compose.staging.yml`, `docker-compose.yml`).

## Documentation & Knowledge Base
- Consult deployment docs (`docs/DEPLOYMENT.md`, `docs/DEPLOY_DOCKER.md`, `docs/DEPLOY_PODMAN.md`), workflow guides, and troubleshooting references before changing release processes or infrastructure.
- Keep API contracts discoverable via `/docs` (Swagger) and `/redoc`; update schemas in `api_swedeb/schemas/` alongside endpoint changes.

## Common Implementation Tasks
- When adding endpoints: define schemas under `api_swedeb/schemas/`, extend utilities in `api_swedeb/api/utils/`, mount handlers in the correct router, wire dependencies, and add coverage in `tests/test_endpoints.py`.
- When changing configuration: edit `config/config.yml`, update `tests/config.yml` to mirror new keys, adjust `ConfigValue` usages, and refresh deployment docs if the change affects environments.
- When optimizing performance: profile first, inspect `load.py::_memory_usage()`, prefer feather storage, and refine CWB/CQP queries instead of bypassing caches.

## Error Handling & Logging
- Raise `FastAPI.HTTPException` for client-facing errors, rely on Loguru configuration for structured logs, and ensure all CWB operations fail fast when registry paths are invalid.

## Data Versioning
- Track corpus versions separately from metadata (`config.yml` under `metadata.version`) and place assets under `data/v{version}/cwb/` and `data/metadata/{version}/` to keep deployments reproducible.
