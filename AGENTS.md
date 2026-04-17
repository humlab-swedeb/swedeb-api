# AGENT INSTRUCTIONS - Swedeb API

## Current Architecture (Post-Archival Migration State)
**Summary**: The Corpus facade class and pass-through util wrappers are gone. Services are injected directly into routes via FastAPI's `Depends()` mechanism, while the old ZIP-backed speech lookup path has been archived under `api_swedeb/legacy/`.

- **Pattern**: Direct service dependency injection with singleton caching (@lru_cache)
- **Active Services**: CorpusLoader, MetadataService, WordTrendsService, SearchService, NGramsService, KWICService
- **Removed**: `api_swedeb/api/utils/corpus.py` (the monolithic facade wrapper)
- **Router Changes**: Routes now inject services directly, not a generic corpus object
- **Archived Runtime**: Legacy speech lookup code now lives in `api_swedeb/legacy/speech_lookup.py` and `api_swedeb/legacy/load.py`
- **Compatibility Shims**: `api_swedeb/core/speech_text.py` is a temporary re-export shim; avoid adding new production logic there
- **Testing**: Active runtime tests live under `tests/api_swedeb/` and `tests/integration/`; archived legacy unit tests live under `tests/legacy/`

## Scope & Ownership
- Build, test, and optimize the FastAPI backend that exposes Swedish parliamentary debate data backed by IMS Open Corpus Workbench (CWB) and Penelope corpora.
- Maintain compatibility with historical data (1867–present) from the SWERIK project and the existing directory layout.
- Keep Codex instructions authoritative; treat this file as mandatory context before every task.

## Configuration & Startup
- `ConfigStore` is a **dataclass instance** (not a static/class-method type). The module-level singleton is accessed via `get_config_store()` from `api_swedeb.core.configuration.inject`.
- Initialize the configuration context via `get_config_store().configure_context(source='config/config.yml')` (use `tests/config.yml` inside tests) before reading any configuration value. The module-level alias `configure_context` is bound at import time and **cannot be patched** in tests — always prefer the explicit `get_config_store().configure_context(...)` form.
- `ConfigValue("path.to.key").resolve()` internally calls `get_config_store().config()`, so patching `get_config_store` in tests is sufficient to intercept all config resolution.
- Resolve configuration values with `ConfigValue("path.to.key").resolve()` using dot notation and respect custom YAML constructors `!jj` and `!join` plus the `PYRIKSPROT_` env override prefix.
- Keep environment variables (`DATA_DIR`, `METADATA_FILENAME`, `TAGGED_CORPUS_FOLDER`, `FOLDER`, `TAG`, `KWIC_CORPUS_NAME`, `KWIC_DIR`) defined and absolute when referencing corpus assets.

### Patching ConfigStore in Tests
Patch the `get_config_store` function so that `ConfigValue.resolve()` sees an isolated store:
```python
from unittest.mock import patch
from api_swedeb.core.configuration.inject import ConfigStore

# Unit test fixture — isolated in-memory store
@pytest.fixture()
def config_store() -> Generator[ConfigStore, None, None]:
    store = ConfigStore()
    store.configure_context(source={"key": "value"}, env_prefix=None)
    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store

# Integration test fixture — real config, no patch needed
@pytest.fixture(scope="module", autouse=True)
def configure_config_store():
    from api_swedeb.core.configuration.inject import get_config_store
    get_config_store().configure_context(source="config/config.yml")
    yield
```
**Scope rule**: a fixture that triggers `ConfigValue.resolve()` (e.g. `CorpusLoader()`) must run *after* the store is configured. Declare `config_store` as a parameter of such fixtures, or use matching scopes, to guarantee ordering.

### Performance Optimization
1. Profile with `make profile-kwic-pyinstrument`
2. Check speech index memory usage: `load.py::_memory_usage()`
3. Use feather format for large DataFrames
4. Consider CWB query optimization via CQP patterns

### Avoiding Unnecessary Wrappers
- **Rule**: No utility wrapper functions that just call a single service method
- **Bad Pattern**: `utils/ngrams.py` → `def get_ngrams(): return service.get_ngrams()`
- **Good Pattern**: Route directly injects service and calls method, applies mapper
- **Exception**: Keep `common_params.py` for shared query parameter handling only
- If you create a util function, it must:
  - Have complex business logic (not just a pass-through)
  - Be reused by multiple routes or services
  - Not duplicate service responsibility

### Refactoring Patterns (Recent Improvements)
- **Removed Wrapper Pattern**: Deleted `utils/ngrams.py`, `utils/word_trends.py`, `utils/kwic.py`
  - Reason: Unnecessary indirection between routes and services
  - Benefit: Cleaner code path, easier to understand flow
- **Added Service Pattern**: Created `KWICService` to encapsulate KWIC logic
  - Reason: Needed persistent access to loader and codecs
  - Benefit: Reusable, testable, follows existing pattern
- **Enhanced Services**: Added helpers like `WordTrendsService.get_search_hits()`
  - Reason: Related functionality grouped with service
  - Benefit: Cohesive service interface, easier discoverability
- **Result**: 3 fewer files, clearer architecture, same functionality

## Data Loading & Storage (`api_swedeb/core/`)
- Use `api_swedeb/core/load.py` helpers to load speech indexes and DTMs; check the feather cache via `is_invalidated(source, target)` before falling back to CSV.gz.
- Treat `api_swedeb/core/load.py` as the home for active shared load helpers only; the archived ZIP loader now lives in `api_swedeb/legacy/load.py`.
- Honor `USED_COLUMNS` and `SKIP_COLUMNS` to minimize memory and keep load times acceptable.
- Keep document-term matrices based on `penelope.corpus.VectorizedCorpus` and manage token vocabularies through the provided token2id mappings.

## API Design (`api_swedeb/api/`)
- Register routes only in `api_swedeb/api/v1/endpoints/tool_router.py` (`/v1/tools`) or `metadata_router.py` (`/v1/metadata`)
- Inject services directly via `Depends()`: `get_corpus_loader()`, `get_metadata_service()`, `get_word_trends_service()`, `get_search_service()`, `get_ngrams_service()`
- Each service is a singleton (cached) and handles specific domain logic
- Common query params via `CommonQueryParams` (KWIC filters, year ranges, etc.)
- `CorpusLoader` uses the prebuilt `bootstrap_corpus` backend exclusively; `api_swedeb/legacy/` is archived and debug-only. Do not add new feature work to the archived legacy backend.
- Keep KWIC, word trends, n-grams, and speech retrieval endpoints performant by enforcing cutoffs (default `cut_off=200000`) and cached corpora.

## CWB Integration (`api_swedeb/core/cwb/`)
- Build CQP expressions through `cwb/compiler.py` and execute via the `ccc` package; never bypass the compiler when constructing queries.
- Route all CWB access through validated registry/data directories and keep `/tmp/ccc-*` isolated per test to avoid shared-state pollution.

## Testing & Tooling
- Run `uv run uvicorn main:app --reload` for local dev, `uv run pytest tests/` for test suites, and `make tidy` (Black + isort) before every commit; `make black` and `make isort` remain available when partial formatting is needed.
- Generate coverage with `make coverage` when verifying broad changes and profile KWIC workloads via `make profile-kwic-pyinstrument` (output lives in `tests/output/`).
- Rely on fixtures from `tests/conftest.py`: `configure_config_store` (session-scoped `autouse=True`) runs once to configure the global store; `api_corpus` provides `CorpusLoader` instance (module-scoped); instantiate services directly in tests; use function-scoped fixtures (`speech_index`, `person_codecs`) for test isolation via cloning.
- For **unit tests** that need an isolated `ConfigStore`, patch `api_swedeb.core.configuration.inject.get_config_store` inside a `yield` fixture at the appropriate scope (see the Patching ConfigStore in Tests section above).
- Keep legacy-only unit coverage in `tests/legacy/`; prefer updating `tests/api_swedeb/` only for active production behavior and rollout-sensitive backend selection.

## Git Workflow & Releases
- Follow the four-branch deployment flow: feature PRs → `dev`, promote sequentially `dev`→`test`→`staging`→`main`, and expect only `test`, `staging`, `main` to trigger CI/CD builds.
- Keep commits in Conventional Commit format (`feat:`, `fix:`, `docs:`, `chore:`) and declare `BREAKING CHANGE:` footers when necessary to drive semantic-release version bumps.
- Build Docker images solely through `.github/scripts/build-and-push-image.sh`; expect runtime frontend assets to be fetched by `download-frontend.sh` and push outputs to `ghcr.io/humlab-swedeb/swedeb-api` with environment-specific compose files (`compose.test.yml`, `compose.staging.yml`, `docker-compose.yml`).

## Documentation & Knowledge Base
- Consult `docs/DEVELOPMENT.md`, `README.md`, `pyproject.toml`, `Makefile`, `.github/scripts/`, `docker/`, and `config/` before changing developer-facing documentation or local workflow guidance.
- Keep `docs/DEVELOPMENT.md` focused on developer-facing content: purpose and audience, prerequisites, local setup, local configuration, project structure, common commands, code quality checks, development workflow, debugging, and related documents.
- Do not put production deployment procedures, rollback, backup/recovery, incident handling, or endpoint-by-endpoint API reference into `docs/DEVELOPMENT.md`; keep those in `docs/OPERATIONS.md`, `docs/DESIGN.md`, generated API docs, or other specialized documentation.
- Consult `docs/OPERATIONS.md` plus current workflow files, scripts, container definitions, and runtime configuration before changing release processes or infrastructure.
- Keep `docs/OPERATIONS.md` focused on operations: environments, runtime configuration and secrets, operational assumptions, data layout, build artifacts, deployment flow, CI stages, CD triggers/release process, post-deployment verification, rollback, health/observability, and backup/recovery basics.
- Do not put local development setup, contributor workflow, unit-test patterns, or general Git guidance into `docs/OPERATIONS.md`; keep those in `docs/DEVELOPMENT.md` or other developer-facing docs.
- Treat `docs/archive/` as historical reference only, not the source of truth for current development or operational procedures.
- Keep API contracts discoverable via `/docs` (Swagger) and `/redoc`; update schemas in `api_swedeb/schemas/` alongside endpoint changes.

## Common Implementation Tasks
- When adding endpoints: define schemas under `api_swedeb/schemas/`, create/extend services in `api_swedeb/api/services/`, inject services via `Depends()` in routers, call service methods (not corpus methods), add tests in `tests/api_swedeb/api/` with mocked services
- When changing configuration: edit `config/config.yml`, update `tests/config.yml` to mirror new keys, adjust `ConfigValue` usages, refresh `docs/DEVELOPMENT.md` if local setup or local configuration guidance changes, and refresh `docs/OPERATIONS.md` if runtime environments, secrets, deployment flow, or operational procedures change.
- When changing developer tooling or local workflow: refresh `docs/DEVELOPMENT.md` if prerequisites, setup steps, common commands, validation steps, or repository-specific development conventions change.
- When optimizing performance: profile first, inspect `load.py::_memory_usage()`, prefer feather storage, and refine CWB/CQP queries instead of bypassing caches.
- When changing speech retrieval behavior: prefer `api_swedeb/core/speech_store.py`, `api_swedeb/core/speech_repository_fast.py`, and `api_swedeb/workflows/prebuilt_speech_index/`; touch `api_swedeb/legacy/` only when the task explicitly concerns the archived fallback path.

## Legacy Handling
- Do not move preserved runtime lookup code into `api_swedeb/workflows/`; that package is for offline/build-time pipeline code.
- If you must update the archived fallback path, keep runtime logic in `api_swedeb/legacy/` and matching unit tests in `tests/legacy/`.
- Do not add new dependencies or new feature work to the archived shim modules unless the task explicitly requires maintaining rollback compatibility.

## Error Handling & Logging
- Raise `FastAPI.HTTPException` for client-facing errors, rely on Loguru configuration for structured logs, and ensure all CWB operations fail fast when registry paths are invalid.

## Data Versioning
- Track corpus versions separately from metadata (`config.yml` under `metadata.version`) and place assets under `data/v{version}/cwb/` and `data/metadata/{version}/` to keep deployments reproducible.
