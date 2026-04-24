# Testing Guide

## Purpose

This guide documents how the Swedeb API codebase is validated. It focuses on the current test levels, test responsibilities, fixture and test-data strategy, supported test commands, and the validation contributors are expected to do before merge or promotion.

It is not the main guide for local project bootstrap or runtime operations. Local setup and day-to-day contributor workflow belong in [DEVELOPMENT.md](./DEVELOPMENT.md). Deployment, release, rollback, and runtime monitoring belong in [OPERATIONS.md](./OPERATIONS.md).

## Table of Contents

- [Purpose](#purpose)
- [Audience and Scope](#audience-and-scope)
- [Testing Goals](#testing-goals)
- [Test Levels and Responsibilities](#test-levels-and-responsibilities)
- [Test Environment and Prerequisites](#test-environment-and-prerequisites)
- [Test Data, Fixtures, and Mocking Strategy](#test-data-fixtures-and-mocking-strategy)
- [Common Test Commands](#common-test-commands)
- [Validation Before Merge](#validation-before-merge)
- [Manual Smoke Testing](#manual-smoke-testing)
- [CI Test Execution](#ci-test-execution)
- [Troubleshooting and Common Pitfalls](#troubleshooting-and-common-pitfalls)
- [Related Documents](#related-documents)

## Audience and Scope

This document is for contributors and maintainers working in the repository.

It covers:

- the active test layers in `tests/`
- what each test layer is meant to protect
- how the checked-in test environment is assembled
- repository-specific fixture, mocking, and configuration rules
- the supported local commands for routine validation
- what contributors should run before opening or updating a pull request

It does not cover:

- general Python or pytest tutorials
- endpoint-by-endpoint API reference
- production deployment validation or incident handling
- architecture rationale better kept in design documentation
- a catalog of every single test file

Treat `docs/archive/` as historical material only, not as the source of truth for current testing practice.

## Testing Goals

The current test suite is designed to support a few practical goals:

- protect active production behavior in the FastAPI routes, services, mappers, and core modules
- keep fast, targeted checks possible for normal development work
- validate CWB-backed query behavior against checked-in corpus fixtures rather than against live external data
- isolate legacy fallback coverage so new feature work stays focused on the active runtime
- make performance-sensitive paths observable through opt-in benchmarks and profiling rather than by slowing every default test run

Testing in this repository is intentionally split between fast isolated tests and slower data-backed validation. The default `pytest` configuration excludes benchmarks, but it does include the regular unit, integration, regression, and legacy trees unless individual tests are skipped.

## Test Levels and Responsibilities

### Unit and component tests

Most active low-level coverage lives under `tests/api_swedeb/`, which mirrors the runtime package structure. This is the primary home for tests of:

- API endpoint wiring and app factory behavior
- services
- core helpers and CWB utility code
- schemas and mappers
- workflow/build-time helpers that are still part of the active codebase

These tests should stay as isolated as practical. Prefer mocks, in-memory objects, and narrowly scoped fixtures when you are testing logic that does not need the real corpus or the full application stack.

### Integration tests

`tests/integration/` covers behavior that uses the real application wiring, checked-in corpus fixtures, and the FastAPI test client. This is where the repository currently tests:

- endpoint reachability and response shape
- CWB-backed query paths
- KWIC, n-grams, metadata, speech lookup, and corpus-loading flows
- interactions between services, configuration, corpus data, and API routes

This is effectively the repository's end-to-end layer for backend behavior. There is no separate contract-test or external system test suite checked in today.

### Regression tests

`tests/regression/` holds behavior and parity checks that are useful when refactors risk subtle output drift. Some regression tests are intentionally skipped, slow, or data-sensitive. Use this directory when you need to lock in a previously observed bug or protect a fragile formatting/parity rule.

### Legacy compatibility tests

`tests/legacy/` is reserved for the archived fallback path and preserved compatibility behavior. Keep new feature work out of this directory unless the task explicitly concerns the archived runtime in `api_swedeb/legacy/`.

### Benchmarks and profiling

Performance checks are opt-in:

- `tests/benchmarks/` contains `pytest-benchmark` tests and is excluded from default runs by the global marker expression in [pyproject.toml](../pyproject.toml).
- `tests/profiling/` contains manual profiling helpers.
- `make profile-kwic-pyinstrument` writes HTML output to `tests/output/`.

Benchmarks are useful when you change large-result queries, download/export paths, or other potentially expensive operations. They are not part of the default merge gate.

## Test Environment and Prerequisites

Use the normal project development environment first:

- Python 3.13
- `uv`
- development dependencies installed via the repo's standard setup

For most contributors, the practical baseline is:

```bash
uv sync --extra dev
uv run pytest tests/
```

The checked-in pytest configuration lives in [pyproject.toml](../pyproject.toml) and currently enforces:

- quiet output with short extra reporting
- strict marker handling
- duration reporting
- `-m 'not benchmark'`, which skips benchmark tests by default

The repository does not rely on an external sample-data checkout for the normal test suite. Instead, the data-backed tests use the checked-in fixtures under `tests/test_data/`.

The important environment pieces are:

- [tests/test.env](../tests/test.env): version variables used during test setup
- [tests/templates/config.yml.jinja](../tests/templates/config.yml.jinja): session config template
- [tests/templates/registry.jinja](../tests/templates/registry.jinja): session CWB registry template
- [tests/conftest.py](../tests/conftest.py): the authoritative bootstrap for the shared pytest environment

The repository also contains [tests/config.yml](../tests/config.yml), but the main pytest session currently generates `tests/output/config.yml` dynamically from the templates above. For most runtime-style tests, `tests/conftest.py` is the source of truth.

Integration-style paths instantiate `ccc.Corpora(...)` against the generated registry and checked-in test corpus. In practice, that means your local environment must be able to import and run the same CWB-backed Python stack that the application itself uses.

## Test Data, Fixtures, and Mocking Strategy

### Checked-in test data

The main data fixtures live under `tests/test_data/` and include:

- versioned corpus data
- registry data
- metadata fixtures
- tagged frames
- DTM inputs
- speech/bootstrap-corpus fixtures

Use these for integration, regression, and benchmark coverage when real corpus behavior matters.

### Shared pytest fixtures

The most important shared fixtures are in [tests/conftest.py](../tests/conftest.py):

- `configure_config_store`: session-scoped and `autouse=True`; initializes the global config store before dependent fixtures run
- `config_file_path`: generates `tests/output/config.yml` plus a registry file for the test session
- `corpus`: creates a CWB corpus using a unique temporary data directory
- `corpus_loader`: warms the active runtime loader and its cached data
- `speech_index`: returns a function-scoped deep copy for test isolation
- `person_codecs`: returns a function-scoped clone for test isolation
- `fastapi_app` and `fastapi_client`: provide the application and request client used by integration tests

`tests/output/` is generated working state, not source data. It is safe to treat it as disposable test output.

### Mocking and configuration policy

Use the test layer to decide how much realism you need:

- In `tests/api_swedeb/`, prefer mocks or small in-memory fixtures when the logic under test does not require the real corpus.
- In `tests/integration/`, use the shared runtime fixtures when you need realistic config, CWB registry access, or API wiring.
- In `tests/legacy/`, keep coverage focused on archived behavior only.

When a test needs an isolated configuration store, patch `api_swedeb.core.configuration.inject.get_config_store` and configure the replacement store before anything calls `ConfigValue.resolve()`. This pattern already appears in `tests/api_swedeb/core/configuration/test_inject.py`, benchmark tests, and some regression tests.

That ordering matters. If a fixture instantiates `CorpusLoader()` or otherwise resolves config too early, it will read from the wrong context.

## Common Test Commands

Full default suite:

```bash
uv run pytest tests/
make test
```

Target the active unit and component tests:

```bash
uv run pytest tests/api_swedeb
```

Target integration coverage:

```bash
uv run pytest tests/integration
```

Target regression or legacy coverage explicitly:

```bash
uv run pytest tests/regression
uv run pytest tests/legacy
```

Run a single file or test while iterating:

```bash
uv run pytest tests/api_swedeb/api/services/test_search_service.py
uv run pytest tests/integration/test_endpoints.py -k kwic
```

Generate coverage reports:

```bash
make coverage
```

Run benchmarks only:

```bash
uv run pytest tests/benchmarks -m benchmark --benchmark-only -v
```

Run the checked-in KWIC profiler:

```bash
make profile-kwic-pyinstrument
```

`make clean-dev` is useful when you want to clear `.pytest_cache`, coverage output, `tests/output/`, and other generated local artifacts before re-running a troublesome test path.

## Validation Before Merge

Use the narrowest test target that proves your change first, then widen the scope when the change crosses boundaries.

Typical expectations:

- route-only or mapper-only change: start with the closest file or package under `tests/api_swedeb/`
- service, config, CWB, or loader change: run the relevant package plus affected integration tests
- endpoint behavior change: run the endpoint/service tests and the matching integration tests
- archived fallback change: include `tests/legacy/`
- performance-sensitive query or export change: consider benchmarks or `make profile-kwic-pyinstrument`

The normal pre-PR baseline is:

1. run targeted pytest commands for the changed area
2. run broader validation if the change crosses service, router, config, corpus, or CWB boundaries
3. run `make tidy`
4. update [TESTING.md](./TESTING.md) if the supported test workflow, fixture policy, or validation expectations changed

## Manual Smoke Testing

Before handing a deployed or locally staged build over to testers, run the concise
[manual smoke-test checklist](./SMOKE_TEST_CHECKLIST.md). It covers startup, API documentation, metadata, KWIC,
word trends, n-grams, speech retrieval, ticketed query flows, ZIP downloads, and basic error handling.

## CI Test Execution

The checked-in GitHub workflows under `.github/workflows/` are currently release and image-build workflows:

- `test.yml`
- `staging.yml`
- `release.yml`

They build and publish images, and in production they run semantic-release, but they do not currently run `pytest` as part of a dedicated CI test job.

That means local test execution remains the primary automated validation path before merge and before promoting changes into the deployment branches. The repository's current CI/CD workflows provide packaging and release validation, not a substitute for running the test suite locally.

## Troubleshooting and Common Pitfalls

- Config-related failures: inspect [tests/conftest.py](../tests/conftest.py), `tests/test.env`, and the generated `tests/output/config.yml` before assuming the runtime config is wrong.
- Wrong ConfigStore context: patch `get_config_store` and configure the store before creating objects that resolve config values.
- Benchmark confusion: benchmark tests are skipped by default because pytest runs with `-m 'not benchmark'`. Use `-m benchmark --benchmark-only` when you want them.
- Coverage command behavior: `make coverage` is useful for report generation, but the current target ends with `|| true`, so it is not the best fail-fast command when you want the shell to stop on test failures.
- Active versus legacy runtime: if the code change targets the active service-based runtime, put new tests under `tests/api_swedeb/` or `tests/integration/`, not `tests/legacy/`.
- Generated output and cache noise: if repeated runs behave strangely, clean local artifacts with `make clean-dev` and rerun the narrowest failing target.

## Related Documents

- [DEVELOPMENT.md](./DEVELOPMENT.md)
- [DESIGN.md](./DESIGN.md)
- [SMOKE_TEST_CHECKLIST.md](./SMOKE_TEST_CHECKLIST.md)
- [OPERATIONS.md](./OPERATIONS.md)
- [AGENTS.md](../AGENTS.md)
- [pyproject.toml](../pyproject.toml)
