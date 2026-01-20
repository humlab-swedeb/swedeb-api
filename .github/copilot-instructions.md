# AI Coding Agent Instructions - Swedeb API

## Project Overview
Backend API for Swedish parliamentary debates (Swedeb) - a FastAPI application analyzing parliamentary speech data using the IMS Open Corpus Workbench (CWB). The system processes historical Swedish parliamentary data (1867-2020+) from the SWERIK project.

## Current Architecture (Post-Refactoring - Complete)
**Summary**: All unnecessary wrapper layers removed. The system uses clean direct service injection with mappers for result transformation. No facade or util wrappers remain.

- **Pattern**: Direct service injection via FastAPI's `Depends()` mechanism with singleton caching
- **Services** (`api_swedeb/api/services/`):
  - `CorpusLoader` - Manages CWB, vectorized corpus, and codec resources
  - `MetadataService` - Parliament metadata (parties, genders, chambers, office types, speakers)
  - `WordTrendsService` - Word frequency analysis and trends (includes `get_search_hits()` helper)
  - `SearchService` - Speech search and retrieval
  - `NGramsService` - N-gram analysis
  - `KWICService` - Keyword-in-context analysis (NEW: replaces utils wrapper)
- **Mappers** (`api_swedeb/mappers/`):
  - Transform service DataFrames to API response schemas (kwic, word_trends, ngrams)
  - No business logic, only schema conversion
- **Utils** (`api_swedeb/api/utils/`):
  - `common_params.py` - Query parameter handling only (all other utils deleted)
- **Benefits**: Single responsibility per service, easy testing, minimal abstraction layers, clear data flow
- **Router Pattern**: Routes inject services → call methods → apply mapper → return schema
- **Deleted Wrappers**: `utils/ngrams.py`, `utils/word_trends.py`, `utils/kwic.py` (replaced with direct service + mapper pattern)

## Architecture & Core Components

### Configuration System (`api_swedeb/core/configuration/`)
- **Critical**: Always initialize ConfigStore before accessing any configuration
- Use `ConfigStore.configure_context(source='config/config.yml')` at application startup
- Access values via `ConfigValue("key.nested").resolve()` - supports dot notation
- YAML config uses custom constructors: `!jj` (path join), `!join` (string join)
- Environment variables override YAML via `PYRIKSPROT_` prefix
- Test configuration: `tests/config.yml`, production: `config/config.yml`

### Data Loading Pattern (`api_swedeb/core/load.py`)
- Speech index: Feather format for performance, falls back to CSV.gz
- Document-term matrices (DTM): Uses `penelope.corpus.VectorizedCorpus`
- Always check feather cache before loading: `is_invalidated(source, target)`
- Memory-optimized columns defined in `USED_COLUMNS`, skip `SKIP_COLUMNS`

### API Structure (`api_swedeb/api/`)
- **Routers**: `v1/endpoints/tool_router.py` (`/v1/tools`) and `metadata_router.py` (`/v1/metadata`)
- **Service Injection** via `Depends()`: `get_corpus_loader()`, `get_metadata_service()`, `get_word_trends_service()`, `get_search_service()`, `get_ngrams_service()`, `get_kwic_service()`
- **Services**: All singletons (cached) with specific domain responsibilities
- **Result Transformation**: Mappers convert service output (DataFrames) to API schemas
- **Query Parameters**: `CommonQueryParams` dependency for common filters (year, party, gender, etc.)
- **Endpoints**:
  - KWIC: Uses `KWICService.get_kwic()` + `kwic_to_api_model()` mapper
  - Word Trends: Uses `WordTrendsService` methods + word_trends mappers
  - N-grams: Uses `NGramsService.get_ngrams()` directly
  - Speeches: Uses `SearchService` methods

### CWB Integration (`api_swedeb/core/cwb/`)
- Uses `ccc` (cwb-ccc) package for Corpus Workbench queries
- CQP (Corpus Query Processor) pattern compilation in `cwb/compiler.py`
- Registry directory and data directory configured per environment
- Shared `/tmp/ccc-*` data directory for test isolation

## Development Workflows

### Running & Testing
```bash
# Local development with auto-reload
uv run uvicorn main:app --reload

# Run tests with pytest
uv run pytest tests/

# Code formatting (REQUIRED before commits)
make tidy        # Runs black + isort
make black       # Black with --line-length 120 --target-version py313
make isort       # isort with --profile black

# Coverage report
make coverage    # Generates XML and HTML reports
```

### Environment Setup
1. Configure data paths in `.env` or `.env_example`
2. Required variables: `DATA_DIR`, `METADATA_FILENAME`, `TAGGED_CORPUS_FOLDER`, `FOLDER`, `TAG`, `KWIC_CORPUS_NAME`, `KWIC_DIR`
3. Use absolute paths for corpus data directories

### Profiling
```bash
make profile-kwic-pyinstrument  # Profile KWIC queries, outputs to tests/output/
```

## Git Workflow & CI/CD

### Branch Strategy (Four-Branch Progressive Deployment)
- `dev` → Integration (NO auto-builds, manual testing only)
- `test` → Auto-builds images tagged `{version}-test`, `test`, `test-latest`
- `staging` → Auto-builds images tagged `{version}-staging`, `staging`
- `main` → Production releases with semantic versioning

### Commit Convention (Conventional Commits - CRITICAL)
- Format: `<type>[scope]: <description>`
- `feat:` - Minor version bump (new features)
- `fix:` - Patch version bump (bug fixes)
- `docs:`, `chore:` - No version bump
- `BREAKING CHANGE:` in footer - Major version bump
- Used by semantic-release for automatic versioning

### PR Workflow
1. Feature branch → PR to `dev` (no builds triggered)
2. `dev` → `test` (triggers CI/CD, creates test images)
3. `test` → `staging` (triggers CI/CD, creates staging images)
4. `staging` → `main` (triggers release workflow, semantic versioning)

### Docker Build Pipeline
- Single unified build script: `.github/scripts/build-and-push-image.sh`
- Frontend assets downloaded at runtime (via )`download-frontend.sh`)
- Images pushed to GitHub Container Registry: `ghcr.io/humlab-swedeb/swedeb-api`
- Environment-specific compose files: `compose.test.yml`, `compose.staging.yml`, `docker-compose.yml`

## Code Patterns & Conventions

### FastAPI Dependencies & Service Injection
```python
# Direct service injection with mapper pattern
from api_swedeb.api.dependencies import get_kwic_service, get_word_trends_service
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.mappers.kwic import kwic_to_api_model
from api_swedeb.mappers.word_trends import word_trends_to_api_model

@router.get("/kwic/{search}")
async def get_kwic(search: str, kwic_service: KWICService = Depends(get_kwic_service)):
    # Service handles business logic
    data = kwic_service.get_kwic(corpus=..., commons=..., keywords=search, ...)
    # Mapper transforms to API schema
    return kwic_to_api_model(data)

@router.get("/word_trends/{search}")
async def get_trends(search: str, word_trends_service: WordTrendsService = Depends(get_word_trends_service)):
    df = word_trends_service.get_word_trend_results(search_terms=search.split(","), ...)
    return word_trends_to_api_model(df)
```

### Configuration Access
```python
# At module/application startup
ConfigStore.configure_context(source='config/config.yml')

# Resolving values
registry_dir = ConfigValue("cwb.registry_dir").resolve()
origins = ConfigValue("fastapi.origins").resolve()
```

### Testing Fixtures (`tests/conftest.py`)
- `api_corpus()` - `CorpusLoader` instance (module-scoped) - Resource manager for CWB and vectorized data
- `fastapi_client()` - `TestClient` for testing API endpoints (module-scoped)
- `corpus_loader()` - Provides CorpusLoader for service instantiation in tests
- `speech_index()` - Deep copy for test isolation (function-scoped)
- `person_codecs()` - Cloned codecs (function-scoped)
- **Service Testing**: Instantiate services directly in tests with mocked or real fixtures:
  ```python
  kwic_service = KWICService(loader, person_codecs)
  word_trends_service = WordTrendsService(loader)
  search_service = SearchService(loader)
  ```
- Fixtures support both unit testing (mocked) and integration testing (real data)

### Penelope Integration
- Internal package for text analysis: `penelope/corpus/`, `penelope/utility/`
- VectorizedCorpus: Sparse matrices (scipy.sparse.csr_matrix) with document index
- Token2Id mappings for vocabulary management

## Critical Implementation Notes

### Performance
- KWIC queries have `cut_off` parameter (default 200K) to prevent timeout
- Speech index loaded once at startup, cached in memory
- CWB data directory uses `/tmp/ccc-*` for subprocess isolation
- Mappers are lightweight (schema transformation only) - no performance concern
- Services handle caching (VectorizedCorpus, codecs) - mappers just format output

### Data Versioning
- Corpus version (e.g., `v1.4.1`) and metadata version (e.g., `v1.1.3`) tracked separately
- Version info in `config.yml` under `metadata.version`
- Folder structure: `data/v{version}/cwb/`, `data/metadata/{version}/`

### Error Handling
- FastAPI HTTPException for user-facing errors
- Loguru for structured logging (configured in `conftest.py` for tests)
- Always validate CWB registry directory existence before queries

## Documentation
- Deployment: `docs/DEPLOYMENT.md`, `docs/DEPLOY_DOCKER.md`, `docs/DEPLOY_PODMAN.md`
- Workflow: `docs/WORKFLOW_GUIDE.md`, `docs/WORKFLOW_ARCHITECTURE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- API docs auto-generated at `/docs` (Swagger UI) and `/redoc`

## Common Tasks

### Adding a New Endpoint
1. **Schema**: Define response model in `api_swedeb/schemas/`
2. **Service**: Create or extend service in `api_swedeb/api/services/`
3. **Mapper**: Add mapper function in `api_swedeb/mappers/` (if needed) to transform DataFrame → schema
4. **Dependency**: Add `get_*_service()` function in `api_swedeb/api/dependencies.py` if creating new service
5. **Endpoint**: Add route in `tool_router.py` or `metadata_router.py`:
   ```python
   @router.get("/my_endpoint/{param}")
   async def my_endpoint(param: str, service: MyService = Depends(get_my_service)):
       data = service.get_data(param)  # Returns DataFrame or list
       return my_mapper(data)           # Transform to API schema
   ```
6. **Tests**: Add tests in `tests/api_swedeb/api/services/test_my_service.py` (unit) and `tests/integration/` (e2e)

### Modifying Configuration
1. Update `config/config.yml` with new keys
2. Add `ConfigValue` instances where needed
3. Update `tests/config.yml` for test compatibility
4. Document changes in deployment docs if environment-specific

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
