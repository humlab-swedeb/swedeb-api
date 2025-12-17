# AI Coding Agent Instructions - Swedeb API

## Project Overview
Backend API for Swedish parliamentary debates (Swedeb) - a FastAPI application analyzing parliamentary speech data using the IMS Open Corpus Workbench (CWB). The system processes historical Swedish parliamentary data (1867-2020+) from the SWERIK project.

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
- Two main routers: `tool_router.py` (prefix `/v1/tools`) and `metadata_router.py` (prefix `/v1/metadata`)
- FastAPI Depends pattern for shared state: `get_shared_corpus()`, `get_cwb_corpus()`, `get_corpus_decoder()`
- Common query params via `CommonQueryParams` dependency injection
- KWIC (Keyword in Context), word trends, n-grams, and speech retrieval endpoints

### CWB Integration (`api_swedeb/core/cwb/`)
- Uses `ccc` (cwb-ccc) package for Corpus Workbench queries
- CQP (Corpus Query Processor) pattern compilation in `cwb/compiler.py`
- Registry directory and data directory configured per environment
- Shared `/tmp/ccc-*` data directory for test isolation

## Development Workflows

### Running & Testing
```bash
# Local development with auto-reload
poetry run uvicorn main:app --reload

# Run tests with pytest
poetry run pytest tests/

# Code formatting (REQUIRED before commits)
make tidy        # Runs black + isort
make black       # Black with --line-length 120 --target-version py311
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
- Frontend assets embedded at build time (downloaded via `download-frontend.sh`)
- Images pushed to GitHub Container Registry: `ghcr.io/humlab-swedeb/swedeb-api`
- Environment-specific compose files: `compose.test.yml`, `compose.staging.yml`, `docker-compose.yml`

## Code Patterns & Conventions

### FastAPI Dependencies
```python
# Shared corpus instance (singleton pattern)
corpus: api_swedeb.Corpus = Depends(get_shared_corpus)

# Common query params (year ranges, filters)
commons: CommonParams = Annotated[CommonQueryParams, Depends()]
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
- `corpus()` - CWB corpus instance (module-scoped)
- `api_corpus()` - Full API corpus with vectorized data (module-scoped)
- `speech_index()` - Deep copy for test isolation (function-scoped)
- `person_codecs()` - Cloned codecs (function-scoped)
- Always use cached fixtures (`_cached` suffix) as base for function-scoped copies

### Penelope Integration
- Internal package for text analysis: `penelope/corpus/`, `penelope/utility/`
- VectorizedCorpus: Sparse matrices (scipy.sparse.csr_matrix) with document index
- Token2Id mappings for vocabulary management

## Critical Implementation Notes

### Performance
- KWIC queries have `cut_off` parameter (default 200K) to prevent timeout
- Speech index loaded once at startup, cached in memory
- CWB data directory uses `/tmp/ccc-*` for subprocess isolation

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
1. Define response schema in `api_swedeb/schemas/`
2. Add utility function in `api_swedeb/api/utils/`
3. Add route decorator and handler in `tool_router.py` or `metadata_router.py`
4. Use existing dependency injection patterns
5. Add tests in `tests/test_endpoints.py`

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
