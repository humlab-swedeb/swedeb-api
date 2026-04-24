# Recent Swedeb Improvements

Snapshot date: 2026-04-23

This document combines the recent improvement in the `swedeb-api` and `swedeb_frontend` repositories.

## Executive Summary

Over the last couple of weeks, the main change in Swedeb has been a move from large synchronous API calls to server-side, ticket-based, and paginated workflow. The backend now has server-side result caching, async ticket execution, paged KWIC and word-trend speech retrieval, more consistent speech-download handling, and follow-up worker and staging stability fixes. The frontend has been updated to consume those flows through server-side pagination, improved download that utilizes server-side caching, and more explicit handling of loading, expiry, and error states.

Performance was the second major theme. In `swedeb-api`, word-trend execution for common-word searches was reduced substantially, DTM grouping and corpus-loading behavior were optimized, and unused Penelope/DTM code was removed or folded into the active runtime. In `swedeb_frontend`, the word-trends page was reworked to use parallel requests and progressive rendering, reducing perceived wait time and making the page usable earlier during long-running searches.

The codebase has been cleaned up structurally. The backend has moved further toward explicit services, thinner routers, clearer dependency wiring, and a cleaner split between active and legacy paths. The frontend simplified store/component responsibilities, consolidated ticket-aware table behavior, and cleaned up analytics and build workflow logic. In parallel, both repositories have better CI/CD release and staging workflows, and the backend has much improved automated test code coverage.


## Detailes

### 1. Search and Result Delivery

The largest change is the introduction of **a ticket-based search workflows** across all the tools except n-grams.

On the backend, this includes:

- paged KWIC results via a server-side result cache
- async, paged word-trend speeches retrieval
- async speeches queries with page-based retrieval
- reuse of cached speech IDs and manifest metadata when downloading from ticketed results
- ZIP-based delivery for ticketed speech exports

On the frontend, this includes

- KWIC ticket submission, polling, and server-side pagination
- ticket-based speeches paging and downloads
- word-trend speech tables wired to paged ticket flows
- better handling of ticket expiry during pagination
- improved loading and empty-state transitions in ticketed result tables

The main system-level outcome is that the browser **no longer needs to store or handle large result sets locally** for these tools.

### 2. Performance and Scalability

The next major area was performance work across both the backend runtime and the user-facing experience.

Backend improvements included:

- added a new and faster indexing storage structure for speech data
  - added a new pre-computed speech index with decoded metadata
  - switched to pre-computed speech storage (indexed feather files - previouly zipped JSON files)
- added a serverside ticket-based task queue system implemented using Celery and Redis frameworks
- faster word-trend execution by slicing the vector space (DTM) before grouping
- DTM grouping grouping optimizations (SciPy improvements)
- changed default Pandas storage format to Pyarrow instead of Numpy.
- improved corpus-loading (preloading) based on benchmarking 
- KWIC and worker stability improvements aimed at long-running and concurrent request behavior

Frontend improvements included:

- parallel API requests on the Word Trends page - don't wait for all data before display
- browser no longer fetches data locally - it's fetched on demand via server side paging
- all downloads are now stream server side
- faster rendering so chart/table content can appear before speeches finish loading
- split loading states by tab instead of blocking the whole view
- ...

The combined effect is both lower backend processing time and better perceived responsiveness in the UI.

### 3. Architecture Cleanup and Tree-Shaking

Recent work also simplified the internal structure of the system.

Backend cleanup included:

- more explicit service-based architecture
- thinner routers and clearer dependency injection
- removal of pass-through utility wrappers
- migration of active runtime logic into `api_swedeb/api/` and `api_swedeb/core/`
- isolation of older fallback logic into `api_swedeb/legacy/`
- consolidation of DTM-related logic under the active core runtime
- removal or deactivation of unused Penelope/DTM paths

Frontend cleanup included:

- clearer store ownership for ticket-aware result flows
- cleanup of speech-table responsibilities
- simplified download and metadata flows
- extraction of analytics logic into a composable
- build/release workflow cleanup following package and CI changes

This was not just feature growth; it was active removal of complexity and dead weight.

### 4. Speech Downloads

Speech download behavior was tightened across both repositories.

Backend changes included:

- support for filtered and ticket-based speech ZIP downloads through the newer download path
- manifest metadata included in ZIP archives
- speech ID deduplication before archive generation
- recent alignment of ticketed CSV/JSON downloads so they now stream ZIP responses for consistency

Frontend changes included:

- use of the newer POST-based speech download flow where appropriate
- fixes so downloads are not limited to the current visible page
- alignment of ticket-based export actions with the new backend contract

This area is a clear example of backend/frontend work being delivered as one coherent feature set.

### 5. PDF and Navigation Improvements

Another shared improvement was better movement between search results and scanned source documents.

Backend support was extended with page-range functionality, while the frontend introduced a pagewise PDF viewer route and supporting UI. Together, those changes improved the connection between API-derived result context and PDF navigation.

### 6. Deployment, Staging, and Operations

Both repositories saw changes that improved build, release, and deployment handling.

Backend operations work included:

- staging and test workflow updates
- improved Docker and Podman support
- Quadlet configuration for staging services
- network and worker fixes for Celery/Redis-based processing
- substantially expanded operational and development documentation

Frontend operations work included:

- simplification of release/build logic around assets and tarball flows
- cleanup of CI/CD workflow behavior
- package upgrade follow-up fixes
- clearer CI/CD documentation

Taken together, these changes improved not only runtime behavior but also the path to deploying and validating that runtime.

### 7. Testing and Engineering Discipline

The backend gained a much broader automated test surface, including:

- endpoint tests
- service tests
- integration tests
- regression suites
- profiling scripts
- workflow and prebuilt-index tests

The frontend changes were validated more through store/component behavior, linting, and staged issue/PR workflows than through a large automated UI test suite, but the recent work still shows better discipline around:

- error handling
- loading-state modeling
- separation of concerns between stores and components

## Paired Changes Across Backend and Frontend

The clearest backend/frontend pairings are:

1. **Paged search results**
   Backend added ticket/result-store infrastructure; frontend moved KWIC, speeches, and word-trend speech tables onto it.

2. **Word-trends performance**
   Backend reduced compute time; frontend surfaced the improvement through parallel and progressive rendering.

3. **Speech downloads**
   Backend aligned manifests, deduplication, and ZIP streaming; frontend aligned download actions and full-result export behavior.

4. **PDF navigation**
   Backend added page-range support; frontend added the pagewise PDF route and UI.

5. **Operational maturity**
   Backend hardened staging workers and containers; frontend simplified its release/build pipeline to match the updated deployment model.

## Overall Assessment

This was not a narrow bug-fix period. It was a broader consolidation phase across Swedeb.

The main results were:

- expensive result flows moved from synchronous delivery to ticketed, paginated workflows
- performance bottlenecks in word trends, KWIC, DTM processing, and UI rendering were addressed
- the backend became more service-oriented and easier to reason about
- unused or obsolete runtime code was removed or isolated
- speech download behavior became more consistent across tools
- frontend UX now reflects backend progress more accurately through progressive loading and clearer failure handling
- deployment, staging, documentation, and test coverage all improved alongside the feature work

The combined effect is a system that is faster, more maintainable, more consistent between backend and frontend, and easier to operate.