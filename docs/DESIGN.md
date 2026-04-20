# Design Guide

## Purpose

This guide describes the current design of the Swedeb API backend. It focuses on system structure, component boundaries, key runtime flows, data/persistence design, cross-cutting concerns, and the design decisions that shape how the codebase works today.

It is not the main guide for local setup, contributor workflow, testing policy, or deployment operations. Those topics belong in [DEVELOPMENT.md](./DEVELOPMENT.md), [TESTING.md](./TESTING.md), and [OPERATIONS.md](./OPERATIONS.md).

## Table of Contents

- [Design Guide](#design-guide)
  - [Purpose](#purpose)
  - [Table of Contents](#table-of-contents)
  - [Audience and Scope](#audience-and-scope)
  - [System Context and Boundaries](#system-context-and-boundaries)
  - [High-Level Architecture](#high-level-architecture)
  - [Components and Responsibilities](#components-and-responsibilities)
    - [App and API layer](#app-and-api-layer)
    - [Dependency and service layer](#dependency-and-service-layer)
    - [Core runtime modules](#core-runtime-modules)
    - [Offline workflow layer](#offline-workflow-layer)
    - [Legacy boundary](#legacy-boundary)
  - [Key Flows and Interactions](#key-flows-and-interactions)
    - [1. Application startup](#1-application-startup)
    - [2. Metadata and speech-listing flow](#2-metadata-and-speech-listing-flow)
    - [3. Synchronous KWIC flow](#3-synchronous-kwic-flow)
    - [4. Ticketed KWIC flow](#4-ticketed-kwic-flow)
    - [5. Speech download flow](#5-speech-download-flow)
  - [Data and Persistence Design](#data-and-persistence-design)
    - [Configuration](#configuration)
    - [Read-only runtime data](#read-only-runtime-data)
    - [Writable runtime state](#writable-runtime-state)
  - [Cross-Cutting Concerns](#cross-cutting-concerns)
    - [Validation and API contracts](#validation-and-api-contracts)
    - [Error handling](#error-handling)
    - [Logging](#logging)
    - [Performance](#performance)
    - [Security and access model](#security-and-access-model)
  - [Constraints and Assumptions](#constraints-and-assumptions)
  - [Design Decisions and Tradeoffs](#design-decisions-and-tradeoffs)
  - [Known Limitations or Technical Debt](#known-limitations-or-technical-debt)
  - [Related Documents](#related-documents)

## Audience and Scope

This document is for developers and maintainers who need to understand how the backend is structured before changing it.

It covers:

- the current FastAPI application shape
- boundaries between routers, services, mappers, schemas, and core modules
- how corpus, metadata, and speech data flow through the runtime
- the offline/runtime split between corpus-building workflows and the live API
- design-level constraints and tradeoffs that matter when evolving the system

It does not cover:

- step-by-step local development setup
- deployment, rollback, observability, or incident procedures
- endpoint-by-endpoint request and response reference
- detailed unit-test catalogs or CI workflow commentary
- archived designs unless they still explain an active constraint

Treat `docs/archive/` and `docs/change_requests/` as supporting context, not as the source of truth for the active runtime design.

## System Context and Boundaries

Swedeb API is a FastAPI backend that exposes Swedish parliamentary debate data through a small set of metadata and analysis endpoints.

At runtime, the backend depends on four main data sources:

- a CWB corpus for KWIC and n-gram queries
- a vectorized DTM corpus for word-trend and speech-index operations
- a SQLite metadata database for speaker, party, office, and related codec data
- a prebuilt `bootstrap_corpus` stored as Feather files for fast speech retrieval and metadata-enriched speech listings

In production mode (`development.celery_enabled: true`), the backend also depends on:

- Redis as the Celery broker and task-state backend for ticketed KWIC query execution

The public API surface is currently organized into two routers:

- `/v1/tools` for analysis, retrieval, and download endpoints
- `/v1/metadata` for metadata lists and speaker queries

The backend can also mount static frontend assets at `/public` when `create_app()` is given a `static_dir`, but the primary responsibility of this repository remains the backend API and corpus-access layer.

## High-Level Architecture

The runtime follows a direct service-injection design.

```text
FastAPI app
  -> routers
  -> dependency factories
  -> focused services
  -> core corpus / config / storage modules
  -> pandas / pyarrow / cwb-ccc / SQLite-backed data sources
```

`api_swedeb.app.create_app()` is the composition root. It:

- initializes configuration from `SWEDEB_CONFIG_PATH` or `config/config.yml`
- builds the app-scoped `AppContainer` through the FastAPI lifespan hook
- creates and manages the `ResultStore` through the FastAPI lifespan hook
- configures CORS from `fastapi.origins`
- mounts `/public` when static assets are supplied
- registers the tools and metadata routers

The runtime does not use a large domain facade. Instead, routers depend directly on focused services through factories in `api_swedeb/api/dependencies.py`. Those factories read from an app-scoped `AppContainer` stored on `app.state`, so expensive loaders and metadata structures are reused across requests without relying on module-global singletons.

The main architectural layers are:

- routers: HTTP contract and request/response orchestration
- services: use-case logic
- mappers: DataFrame/domain result to API schema projection
- schemas: Pydantic request and response models
- core modules: configuration, CWB query compilation/execution, speech storage/retrieval, and data-loading utilities
- workflows: offline corpus-building processes that produce runtime artifacts

## Components and Responsibilities

### App and API layer

The entry point is [main.py](../main.py), which builds the app through [api_swedeb/app.py](../api_swedeb/app.py). Routers live in:

- [api_swedeb/api/v1/endpoints/tool_router.py](../api_swedeb/api/v1/endpoints/tool_router.py)
- [api_swedeb/api/v1/endpoints/metadata_router.py](../api_swedeb/api/v1/endpoints/metadata_router.py)

`api_swedeb/api/params.py` defines shared query-parameter objects so filtering semantics are centralized rather than reimplemented per endpoint.

### Dependency and service layer

`api_swedeb/api/dependencies.py` wires the main services and a few lower-level objects:

- `CorpusLoader`
- `MetadataService`
- `SearchService`
- `WordTrendsService`
- `NGramsService`
- `KWICService`
- `KWICTicketService`
- `DownloadService`
- `ResultStore`
- CWB corpus creation helpers

The key services are:

- `CorpusLoader`: lazy access to DTM corpus, prebuilt speech index, metadata codecs, and speech repository
- `MetadataService`: read-only metadata tables
- `SearchService`: speech listing, speaker lookup, single-speech retrieval, and batch speech access
- `WordTrendsService`: vocabulary filtering and time-series aggregation over the vectorized corpus
- `NGramsService`: CWB-backed n-gram extraction
- `KWICService`: synchronous KWIC query execution and metadata join
- `KWICTicketService`: paged KWIC ticket lifecycle; dispatches to Celery (production, multiprocessing) or FastAPI `BackgroundTasks` (development, singleprocessing) based on `development.celery_enabled`
- `DownloadService`: streamed archive generation for speech downloads
- `ResultStore`: disk-backed storage for generated KWIC result artifacts

### Core runtime modules

The main core subsystems are:

- `core/configuration/`: `Config`, `ConfigStore`, and `ConfigValue`
- `core/load.py`: DTM and speech-index loading, Feather invalidation checks, and index slimming
- `core/cwb/`: CQP expression compilation and CWB helpers
- `core/kwic/`: single-process and multiprocessing KWIC execution
- `core/speech_store.py`: low-level Feather storage access for prebuilt speech data
- `core/speech_repository.py`: higher-level speech retrieval built on `SpeechStore`
- `core/speech_utility.py`: formatting and URL/link derivation used by API mappers
- `core/word_trends.py` and `core/speech_index.py`: DTM-driven analysis helpers

### Offline workflow layer

`api_swedeb/workflows/prebuilt_speech_index/` builds the precomputed `bootstrap_corpus` used by the runtime. This is intentionally separated from the live API: the runtime reads prebuilt artifacts; it does not reconstruct them on demand.

### Legacy boundary

`api_swedeb/legacy/` contains archived fallback runtime code. It is preserved for rollback/forensics and matching legacy tests, but it is not the design center of the active application.

## Key Flows and Interactions

### 1. Application startup

At startup, the app configures the active `ConfigStore` context, builds the FastAPI application, creates an app-scoped `AppContainer`, and starts a `ResultStore` rooted at `cache.root_dir`. This makes service wiring and ticket artifact cleanup part of application state rather than ad hoc global handling.

### 2. Metadata and speech-listing flow

Metadata requests go from router -> service -> DataFrame -> Pydantic models. For speech listings, `SearchService` reads from the prebuilt speech index exposed by `CorpusLoader`, applies filter options, and then the mapper layer derives API-facing fields such as:

- formatted `speech_name`
- Wikidata links
- PDF links

This keeps HTTP formatting concerns out of the core storage and retrieval layer.

### 3. Synchronous KWIC flow

The synchronous `/v1/tools/kwic/{search}` path:

1. parses shared filter parameters
2. builds a CWB corpus via dependency helpers
3. turns request parameters into CQP options
4. executes KWIC through `core.kwic`
5. joins KWIC rows with the prebuilt speech index
6. maps the result to the public KWIC schema

The important design choice here is that speaker and speech metadata are joined from the prebuilt speech index rather than decoded on the fly from metadata codecs during every query.

### 4. Ticketed KWIC flow

The paged KWIC path is designed for larger or slower queries and operates in one of two modes controlled by `development.celery_enabled`.

**Production mode** (`celery_enabled: true`, default for `config/config.yml`):

1. the client submits a `KWICQueryRequest`
2. `KWICTicketService` creates a ticket through `ResultStore`
3. `celery_app.send_task("api_swedeb.execute_kwic_ticket", ...)` enqueues the task with the ticket ID as the Celery task ID
4. a separate Celery worker process executes the query using `multiprocessing.Pool` (`kwic.use_multiprocessing: true`)
5. the resulting DataFrame is serialized to Feather in the shared `ResultStore` directory
6. clients poll ticket status (sourced from `celery_app.AsyncResult`) and fetch paged results from `ResultStore`

**Development mode** (`celery_enabled: false`, default for `config/debug.config.yml`):

1–2. Same ticket creation.
3. `BackgroundTasks.add_task(execute_ticket, ...)` schedules in-process execution
4. the resulting DataFrame is serialized to Feather in the result-store directory
5. clients poll ticket status (sourced from `ResultStore`) and fetch paged results

The important design constraint is that `multiprocessing.Pool().map()` deadlocks when called from FastAPI's thread-pool-backed `BackgroundTasks`. Production mode avoids this by moving the query into a true separate process (Celery worker). Development mode disables multiprocessing and relies on `BackgroundTasks`, which enables native debugger support without a Redis dependency.

### 5. Speech download flow

Speech download requests either:

- derive speech IDs from current filter selections, or
- reuse the speech IDs already captured in a KWIC ticket manifest

`DownloadService` then batches text retrieval through `SearchService` and `SpeechRepository`, and streams the result as ZIP by default. The service also supports tar.gz and jsonl.gz strategies, but the public route currently serves ZIP responses.

## Data and Persistence Design

### Configuration

Configuration is runtime-resolved through `ConfigValue(...).resolve()` against the active `ConfigStore`. The default app context comes from `SWEDEB_CONFIG_PATH` or `config/config.yml`.

This makes configuration a first-class runtime dependency rather than a loose collection of environment variables spread across modules.

### Read-only runtime data

The runtime is built around read-mostly analytical data:

- DTM/document index files loaded through `penelope.corpus.VectorizedCorpus`
- CWB registry and data directories
- metadata tables from SQLite
- prebuilt Feather artifacts under `speech.bootstrap_corpus_folder`

The prebuilt speech corpus is especially important. It consists of:

- one Feather file per protocol
- `speech_lookup.feather` for lookup locations
- `speech_index.feather` for the full metadata-enriched speech index
- `manifest.json` for build provenance

The canonical identifier is `speech_id`. `document_name` remains an important historical/public identifier, but the active repository design treats `speech_id` as the stable lookup key for batch retrieval and ticket manifests.

### Writable runtime state

The main writable runtime persistence is `ResultStore`, which writes ticket artifacts as Feather files under `cache.root_dir`. This is ephemeral application state, not a long-lived source dataset.

In production mode, Redis holds a second layer of ephemeral state:

- task queue: pending Celery tasks waiting for worker pickup
- task execution state: PENDING → STARTED → SUCCESS/FAILURE
- small task return values: ticket ID and row count

Large KWIC DataFrames are always stored in `ResultStore` (filesystem), not in Redis, because Celery's Redis result backend is not sized for multi-megabyte row results.

## Cross-Cutting Concerns

### Validation and API contracts

Pydantic schemas define the public request and response contracts, and FastAPI exposes generated API documentation at `/docs` and `/redoc`.

### Error handling

Routers translate service and store failures into HTTP errors such as:

- `400` for bad pagination or invalid parameter combinations
- `404` for missing tickets or resources
- `409` for ticket conflicts or failed async jobs
- `429` when the pending-ticket limit is exceeded

Lower-level storage and retrieval code often returns degraded results or logs errors instead of crashing the whole request path, especially in speech-retrieval code.

### Logging

The codebase uses Loguru for structured runtime logging. Logging appears in configuration-sensitive, storage-sensitive, and performance-sensitive areas such as CWB access, speech storage, and result-store behavior.

### Performance

Performance-related design choices are visible throughout the runtime:

- lazy loading in `CorpusLoader`
- singleton reuse of expensive services
- Feather/Arrow storage for fast columnar access
- precomputed speech metadata in the bootstrap corpus
- batched protocol reads in `SpeechStore`
- optional multiprocessing for KWIC
- ticketed/paged KWIC to avoid forcing every large query into one synchronous response

### Security and access model

The app currently configures CORS, but it does not implement built-in authentication or authorization. The current design assumes a trusted deployment boundary around the API rather than an internal auth subsystem in this repository.

## Constraints and Assumptions

- Runtime configuration and mounted data paths must agree; the application does not dynamically discover corpus layout.
- The active runtime assumes the offline bootstrap-corpus workflow has already been run for the configured corpus version.
- CWB registry and data directories must be valid for query endpoints to work.
- `speech_id` must remain stable across the prebuilt speech index and any batch retrieval or ticket-manifest workflow.
- The filesystem-backed `ResultStore` is local to the running deployment unit; it is not a distributed job/result system.
- The active backend design centers on the prebuilt repository path, not the archived ZIP-based legacy runtime.

## Design Decisions and Tradeoffs

- Service dependency injection instead of a big monolithic facade: simpler routing and clearer ownership. Dependency lifecycle is handled through an explicit app-scoped container built during FastAPI lifespan.
- Prebuilt speech corpus instead of runtime ZIP parsing: much faster speech retrieval and cleaner batch access, but it adds a required offline build artifact and version-alignment constraint.
- DataFrame-centric service boundaries: efficient for analytical operations and mapper projection, but it keeps much of the domain logic tied to pandas and Arrow-style structures.
- Celery + Redis for production KWIC execution: moves ticket queries into a separate worker process so `multiprocessing.Pool` can be used safely. Adds Redis and a worker container to the deployment but enables near-linear CPU scaling for large queries. A `development.celery_enabled` toggle preserves the simpler `BackgroundTasks` path for local development without Redis.
- Disk-backed ticket artifacts alongside Celery: Redis holds only small task metadata; large KWIC DataFrames remain in the filesystem `ResultStore`. This keeps Redis memory bounded and reuses the existing artifact lifecycle management.
- Archived legacy runtime kept in-repo: useful for compatibility and rollback analysis, but it creates a second code path that must be clearly excluded from new feature work.

## Known Limitations or Technical Debt

- `ResultStore` is host-local and filesystem-backed, so ticket execution and artifact lookup are not designed for horizontally distributed execution. In production, the API container and the Celery worker container must share the same `cache.root_dir` volume.
- Multiprocessing in KWIC queries requires Celery workers in production. Development mode (`celery_enabled: false`) disables multiprocessing to avoid deadlocking FastAPI's `BackgroundTasks` thread pool.
- There is no built-in authentication/authorization layer in the backend.
- The `/v1/tools/topics` endpoint is still a stub.
- The repository still carries compatibility-oriented code and archived legacy modules. Please avoid using them when working on core logic.

## Related Documents

- [DEVELOPMENT.md](./DEVELOPMENT.md)
- [TESTING.md](./TESTING.md)
- [OPERATIONS.md](./OPERATIONS.md)
- [README.md](../README.md)
- generated FastAPI docs at `/docs` and `/redoc`
