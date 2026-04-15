# Test Organization

This directory contains the test suite for the Swedeb API project, organized into different categories for better maintainability and faster test execution.

## Directory Structure

```
tests/
├── integration/         # Integration tests using real CWB corpus and full API
├── api_swedeb/         # Unit tests mirroring the api_swedeb module structure
│   ├── api/            # Tests for API layer (routers, endpoints)
│   │   └── utils/      # Tests for API utility modules
│   └── core/           # Tests for core business logic
│       ├── configuration/  # Configuration system tests
│       └── cwb/        # CWB integration tests
├── penelope/           # Tests for the vendored penelope library
├── legacy/             # Legacy integration tests
├── profiling/          # Performance profiling scripts
└── test_data/          # Test data fixtures
```

## Test Categories

### Unit Tests (`api_swedeb/`)
- **Purpose**: Test individual components in isolation with mocked dependencies
- **Structure**: Mirrors the `api_swedeb/` module structure for easy navigation
  - `api_swedeb/api/` → `tests/api_swedeb/api/`
  - `api_swedeb/core/` → `tests/api_swedeb/core/`
- **Characteristics**:
  - ⚡ Fast execution (~0.79 seconds for full suite!)
  - No external dependencies (CWB, real corpus data)
  - Use mocks and fixtures for dependencies
  - Can run without full data setup
  - **100% isolation** - no real corpus required
- **Run with**: `pytest tests/api_swedeb`
- **Coverage target**: >90% for all modules (currently 96%)
- **Test count**: ~490 tests

### Integration Tests (`integration/`)
- **Purpose**: Test complete workflows using real CWB corpus and API endpoints
- **Characteristics**:
  - Require real corpus data and CWB setup
  - Test end-to-end functionality
  - Moderate execution time (~5 seconds total)
  - Use fixtures from `conftest.py`: `corpus`, `api_corpus`, `fastapi_client`, `person_codecs`, `speech_index`
- **Run with**: `pytest tests/integration`
- **Test count**: ~120 tests
- **Files include**:
  - `test_tool_router.py` - API tool endpoint integration tests
  - `test_metadata_router.py` - API metadata endpoint integration tests
  - `test_kwic.py`, `test_kwic_core.py` - KWIC endpoint and core functionality tests
  - `test_ngrams.py`, `test_ngrams_core.py` - N-gram service integration tests
  - `test_cwb_integration.py` - CWB/CQP query execution tests
  - `test_speeches.py` - Speech retrieval tests
  - `test_speech_index.py` - Speech index with real data
  - `test_speakers.py` - Speaker filtering tests
  - `test_word_trends.py` - Word trends analysis tests
  - `test_meta.py` - Metadata tests
  - `test_corpus.py` - Corpus loading tests
  - `test_bug.py` - Bug regression tests
  - `test_load_corpus.py` - Corpus data loading tests
  - `test_endpoints.py` - API endpoint smoke tests

### Legacy Tests (`legacy/`)
- **Purpose**: Older integration tests maintained for compatibility
- **Run with**: `pytest tests/legacy`

## Running Tests

### All tests (unit + integration)
```bash
pytest tests/
```

### Unit tests only (fast, no CWB required)
```bash
pytest tests/ --ignore=tests/integration --ignore=tests/legacy
```

### Integration tests only
```bash
pytest tests/integration
```

### With coverage report
```bash
pytest tests/ --cov=api_swedeb --cov-report=term-missing --cov-report=xml
```

### Unit tests with coverage (recommended for development)
```bash
pytest tests/ --ignore=tests/integration --ignore=tests/legacy --cov=api_swedeb
```

## Fixtures

Key fixtures are defined in `conftest.py`:

- **`corpus`** (module-scoped): Real CWB corpus instance
- **`api_corpus`** (module-scoped): Full Swedeb API corpus with loaded data
- **`fastapi_client`** (module-scoped): FastAPI test client for endpoint tests
- **`speech_index`** (function-scoped): Copy of speech index for test isolation
- **`person_codecs`** (function-scoped): Cloned person codecs

## Current Test Statistics

- **Total tests**: ~580
- **Unit tests**: ~504 (all in tests/api_swedeb/, properly isolated with mocks)
- **Integration tests**: ~120 (all in tests/integration/, use real corpus data)
- **Overall coverage**: 96%
- **Execution time**: 
  - Unit tests: ~3 seconds ⚡ (no I/O, fully mocked)
  - Integration tests: ~5 seconds (real CWB corpus, file I/O)
  - Total: ~8 seconds

## Test Organization Philosophy

### Unit Tests (`tests/api_swedeb/`)
**MUST be isolated** - no real data, no file I/O, no external dependencies:
- ✅ Use `@patch`, `Mock`, `MagicMock` from `unittest.mock`
- ✅ Create fixture-based mocks (e.g., `mock_corpus()` that returns mock objects)
- ✅ Can run without CWB corpus installation
- ✅ Fast execution (<3 seconds)
- ❌ DO NOT use `corpus`, `api_corpus`, `person_codecs`, `fastapi_client` fixtures
- ❌ DO NOT load real files or databases

### Integration Tests (`tests/integration/`)
**Can use real data** - test complete workflows with real dependencies:
- ✅ Use `corpus`, `api_corpus`, `person_codecs` fixtures from conftest.py
- ✅ Use `fastapi_client` for end-to-end API testing
- ✅ Load real CWB corpus data
- ✅ Test actual file I/O operations
- ⚠️ Requires CWB corpus setup
- ⏱️ Slower execution (~5 seconds)

## Contributing

When adding new tests:

1. **Unit tests** go in `tests/api_swedeb/` or `tests/core/` matching the source structure
   - Use mocks for all external dependencies
   - Target specific functions/methods
   - Aim for >90% coverage

2. **Integration tests** go in `tests/integration/`
   - Use real corpus fixtures
   - Test complete user workflows
   - Focus on critical paths

3. **Naming convention**: 
   - Test files: `test_*.py`
   - Test functions: `test_*`
   - Test classes: `Test*`

4. **One-to-one file mapping**: Prefer `tests/core/test_module.py` for `api_swedeb/core/module.py`
