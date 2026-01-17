# Test Organization

This directory contains the test suite for the Swedeb API project, organized into different categories for better maintainability and faster test execution.

## Directory Structure

```
tests/
├── integration/         # Integration tests using real CWB corpus and full API
├── api_swedeb/         # Unit tests for API layer (mocked dependencies)
├── core/               # Unit tests for core business logic (mocked dependencies)
├── penelope/           # Tests for the vendored penelope library
├── legacy/             # Legacy integration tests
├── profiling/          # Performance profiling scripts
└── test_data/          # Test data fixtures
```

## Test Categories

### Unit Tests (`api_swedeb/`, `core/`)
- **Purpose**: Test individual components in isolation with mocked dependencies
- **Characteristics**:
  - Fast execution (< 6 seconds for full suite)
  - No external dependencies (CWB, real corpus data)
  - Use mocks and fixtures for dependencies
  - Can run without full data setup
- **Run with**: `pytest tests/ --ignore=tests/integration --ignore=tests/legacy`
- **Coverage target**: >90% for all modules

### Integration Tests (`integration/`)
- **Purpose**: Test complete workflows using real CWB corpus and API endpoints
- **Characteristics**:
  - Require real corpus data and CWB setup
  - Test end-to-end functionality
  - Slower execution (~4 seconds)
  - Use fixtures from `conftest.py`: `corpus`, `api_corpus`, `fastapi_client`
- **Run with**: `pytest tests/integration`
- **Files moved here**:
  - `test_kwic.py` - KWIC endpoint tests
  - `test_endpoints.py` - API endpoint smoke tests
  - `test_ngrams.py` - N-gram service integration tests
  - `test_speeches.py` - Speech retrieval tests
  - `test_speakers.py` - Speaker filtering tests
  - `test_word_trends.py` - Word trends analysis tests
  - `test_meta.py` - Metadata tests
  - `test_corpus.py` - Corpus loading tests
  - `test_bug.py` - Bug regression tests
  - `test_load_corpus.py` - Corpus data loading tests

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

- **Total tests**: ~550
- **Unit tests**: ~450 (passed: 452, skipped: 5)
- **Integration tests**: ~100 (passed: 94, skipped: 5, failed: 2 pre-existing)
- **Overall coverage**: 95%
- **Execution time**: 
  - Unit tests: ~5 seconds
  - Integration tests: ~4 seconds
  - Total: ~10 seconds

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
