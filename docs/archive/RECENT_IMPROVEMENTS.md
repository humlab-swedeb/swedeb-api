# Recent Improvements

Snapshot date: 2026-04-23

This document summarizes the major improvements we have made recently across `swedeb-api` and `swedeb_frontend`, with related backend and frontend changes grouped together.

## Executive Summary

Over the last couple of weeks, the main change across both repositories has been a shift from large synchronous result delivery to ticket-based, paginated workflows for expensive searches. On the backend, this introduced server-side result caching, async ticket execution, paged KWIC and word-trend speech retrieval, more consistent speech download handling, and follow-up worker and staging stability fixes. On the frontend, the matching work replaced client-heavy result handling with server-side pagination, improved download flows, and tightened error handling around ticket expiry and loading states.

Performance work was the second major theme. In `swedeb-api`, word-trends execution was reduced substantially for common-word queries, DTM grouping and corpus-loading behavior were optimized, and unused Penelope/DTM code was removed or folded into the active runtime. In `swedeb_frontend`, the word-trends page was reworked to use parallel requests and progressive rendering, which reduced perceived wait time and made the page usable earlier during long-running searches.

The codebase was also cleaned up structurally. The backend moved further toward explicit services, thinner routers, clearer dependency wiring, and better separation between active and legacy code paths. The frontend simplified store/component responsibilities, consolidated ticket-aware table behavior, and cleaned up analytics and build workflow logic. In parallel, both repositories gained stronger operational support through release and staging workflow work, and the backend in particular added a much broader automated test surface to support these architectural changes.

## How this summary was compiled

This write-up is based on three sources:

1. The current `CHANGELOG.md` files in both repositories
2. `origin/main..origin/staging` branch diffs and recent commit history
3. Recent GitHub issues and pull requests, especially work updated since 2026-04-09

One important caveat: the changelogs do not yet capture most of the April 2026 work. The branch diffs and issue/PR history are therefore the more accurate source for the last couple of weeks.

## Scope at a glance

- `swedeb-api`: `origin/main..origin/staging` currently spans a very large backend modernization wave, including API restructuring, ticketed async workflows, performance work, deployment hardening, documentation expansion, and extensive new tests.
- `swedeb_frontend`: `origin/main..origin/staging` captures a concentrated UI/data-flow update focused on ticket-based pagination, better progressive loading, PDF navigation, release workflow cleanup, and store/component simplification.

## 1. Ticketed search workflows and paginated result delivery

This has been one of the biggest joint improvements across backend and frontend.

### Backend

The API moved several heavy result flows away from large synchronous responses and toward ticket-based, artifact-backed workflows:

- Paged KWIC results via a server-side result cache and ticket lifecycle
- Async, paged word-trend speeches results
- Async speeches queries with page-by-page retrieval
- Reuse of cached speech IDs and manifest metadata when downloading speeches from ticketed results
- ZIP delivery consistency for ticketed speech exports, including the recent fix to wrap CSV/JSON ticket downloads in ZIP archives

Key related issues and PRs include:

- `swedeb-api#267`: paged KWIC results via ticket-based server-side cache
- `swedeb-api#304`: paged word-trend speeches via async ticket flow
- `swedeb-api#263`, `#264`, `#265`, `#266`: speech download alignment, deduplication, manifest metadata, and download workflow cleanup
- PR `#268`: Paged KWIC Results via Server-side cache
- PR `#305`: Paged word trends speeches
- PR `#307`: Introduce async speech worker flow
- PR `#311`: Worker stability fixes
- `swedeb-api#312`: ZIP ticketed speech downloads

Technically, this work introduced or expanded:

- `ResultStore` and ticket lifecycle management
- dedicated ticket services for KWIC and word-trend speeches
- artifact-backed pagination over Feather/Arrow output
- better separation between routing, service logic, and cached result delivery
- more predictable download behavior across tools

### Frontend

The frontend was updated in parallel to consume those ticketed flows instead of trying to hold everything client-side:

- KWIC now uses ticket submission, polling, and server-side pagination
- Speeches search now uses ticket-based paging and download actions
- Word-trends speech tables now use the new paged ticket flow
- Download buttons were aligned with the new ticket endpoints
- Pagination, expiry, and loading/error states were hardened

Key related issues and PRs include:

- `swedeb_frontend#164`: optimize word trends page loading and rendering performance
- `swedeb_frontend#165`: per-tab loading indicators for word trends
- `swedeb_frontend#166`: pagination fails silently when tickets expire
- `swedeb_frontend#167`: expired ticket shows "no results" instead of expiration message
- `swedeb_frontend#170`: prevent false no-results flash in ticketed result tables
- PR `#156`: add pagination workflow / ticketed request-response flow
- PR `#168`: implement server-side pagination for speeches
- PR `#169`: improve performance for word trends
- PR `#171`: fix false no-results flash in ticketed result tables

The net effect is that the browser no longer needs to materialize or sort huge result sets locally for these tools.

## 2. Performance improvements and scalability work

The other dominant theme has been performance, especially for large corpora and common-word searches.

### Backend

#### Word trends

`swedeb-api#302` optimized word trends for small word lists by slicing the vector space before grouping. For common words such as `att`, this reduced query time dramatically.

Important result from the issue write-up:

- Before: 30+ seconds for a common-word HTTP query
- After: around 3 seconds

#### DTM and corpus processing

Several recent issues and PRs focused on DTM loading, grouping, and tree-shaking of unused corpus code:

- `swedeb-api#301`: DTM corpus loading optimization
- `swedeb-api#282` to `#299`: grouping, naming, type conversion, vocabulary matching, and removal of unnecessary materialization
- PR `#303`: optimize DTM performance and processing
- PR `#277`: refactor and clean up deprecated/unused Penelope-related code

Supporting repo notes from the recent work:

- The biggest corpus-loading gain came from eager startup loading rather than replacing the NPZ format
- DTM grouping was optimized to reduce allocations and improve large-scale grouping performance by roughly `1.3x` to `2.4x`, depending on dataset size
- Unused DTM and Penelope modules were removed or folded into `api_swedeb/core`, which reduced indirection and improved maintainability

#### KWIC and worker stability

Performance work also targeted KWIC execution and runtime stability:

- `swedeb-api#254`: multiprocessing KWIC issues
- PR `#278`: Celery and Redis integration work
- PR `#279`: KWIC performance optimization
- PR `#311`: worker stability fixes

This work improved not only throughput, but also how the API behaves under long-running or concurrent requests.

### Frontend

The frontend improvements focused on perceived speed and progressive rendering, especially on the Word Trends page.

From `swedeb_frontend#164` and `#165`:

- trends and speeches requests were moved from sequential to parallel execution
- chart/table content can appear before speeches finish loading
- loading indicators were split by tab instead of blocking the whole page
- chart reactivity and animation delays were cleaned up

The practical result is that the page now feels faster even when the backend is still processing the slower speech retrieval part.

## 3. Architecture cleanup, refactoring, and tree-shaking

Much of the recent work was not just feature delivery, but simplification of the codebase.

### Backend

The backend saw a large structural cleanup:

- move toward an app-scoped container and direct service injection
- thinner routers and clearer service boundaries
- removal of pass-through utility wrappers in favor of dedicated services
- migration of active runtime logic into `api_swedeb/api/` and `api_swedeb/core/`
- legacy ZIP-backed lookup paths pushed into `api_swedeb/legacy/`
- introduction of prebuilt speech index / repository-oriented runtime paths
- consolidation of DTM-related logic under `api_swedeb/core/dtm/`

The `origin/main..origin/staging` diff shows this especially clearly:

- many old `api/utils/*` wrappers were removed
- new service modules were added for corpus loading, metadata, search, n-grams, KWIC, word trends, downloads, and ticket handling
- many tests were added at service, endpoint, integration, regression, profiling, and workflow layers

This is also where the tree-shaking work landed most visibly: removing or isolating unused Penelope/DTM code and replacing broad dependencies with locally-owned runtime paths.

### Frontend

The frontend cleanup was smaller in file count but still important:

- result logic became more store-driven and ticket-aware
- speech table responsibilities were split into clearer components
- metadata and download flows were cleaned up
- analytics logic was extracted into a composable
- release/build responsibilities were simplified in CI/CD scripts

Key items include:

- `swedeb_frontend#161`: refactor gtag event resolution
- extraction and cleanup of ticket-aware table/store logic
- dependency and build tooling cleanup from the major package update branch and follow-up fixes

## 4. PDF and document navigation improvements

Another cross-cutting feature area was pagewise PDF viewing.

### Backend

- PR `#290`: add page range endpoint and related backend support

### Frontend

- PR `#163`: add `PdfPageWise` component and route
- better navigation between API data and PDF pages
- improvements to related PDF UX and link behavior

This work gives users a more direct bridge between search hits and the scanned source material.

## 5. Speech download improvements

Speech download behavior was tightened up significantly across the stack.

### Backend

The backend now has a clearer download story:

- `POST /speeches/download` supports filtered downloads and ticket-based downloads using cached speech IDs
- manifest metadata is generated and included in ZIPs
- speech IDs are deduplicated before archive generation
- recent ticketed CSV/JSON download endpoints now return ZIP streams for consistency

Key issues:

- `swedeb-api#263`, `#264`, `#265`, `#266`, `#312`

### Frontend

The frontend matched that work by:

- sending download requests through the newer POST-based download path where appropriate
- ensuring full result downloads are not limited to the current visible page
- wiring ticket-based CSV/JSON exports into the refreshed tables

This area is a good example of backend/frontend changes moving in lockstep rather than independently.

## 6. Deployment, staging, and operational hardening

The recent work also improved how the system is built, deployed, and tested outside local development.

### Backend

`swedeb-api` saw a major operations and runtime hardening wave:

- new staging and test workflows
- improved Docker and Podman handling
- Podman Quadlet configuration for staging services
- private network configuration for staging containers
- Celery/Redis deployment fixes and synchronization work
- much stronger operational documentation

Key PRs include:

- `#309`: Podman Quadlet configuration
- `#311`: worker stability fixes
- `#280`: local container workflow documentation
- `#281`: Dockerfile and dependency cleanup

The repository now also has significantly expanded documentation in:

- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/OPERATIONS.md`
- `docs/TESTING.md`

### Frontend

The frontend CI/release pipeline also moved forward:

- deprecation of older container-build assumptions in favor of asset/tarball flows
- cleanup of build-assets and release workflow behavior
- staging/test naming simplification
- dependency upgrades and follow-up fixes
- clearer CI/CD documentation

Key PRs/issues include:

- PR `#159`: major frontend package updates
- `swedeb_frontend#158`: deprecate Docker image builds
- `swedeb_frontend#157`: package upgrades

## 7. Test coverage and engineering discipline

Both repos gained a substantial amount of new verification around the new architecture.

### Backend

This is especially visible in `swedeb-api`, where the diff shows a very large expansion of:

- endpoint tests
- service tests
- integration tests
- profiling scripts
- regression suites
- workflow and prebuilt-index tests

This testing growth matters because many of the recent changes were architectural and performance-related, not just UI polish.

### Frontend

The frontend work was validated more through linting, staged issue/PR flow, and component/store behavior updates than through an automated test suite, but the recent changes clearly show improved discipline in:

- tighter store error handling
- clearer loading-state management
- more explicit separation of component responsibilities

## Backend and frontend changes that clearly belong together

These are the strongest paired stories across the two repositories:

1. **Paged search results**
   Backend added ticket/result-store infrastructure; frontend moved KWIC, speeches, and word-trend speech tables onto it.

2. **Word trends performance**
   Backend optimized word-trend computation; frontend switched to parallel/progressive rendering so users see the gain.

3. **Speech downloads**
   Backend aligned download endpoints, manifests, deduplication, and ZIP streaming; frontend updated download actions and avoided current-page-only exports.

4. **PDF navigation**
   Backend added page-range support; frontend delivered a pagewise PDF viewer route and UI.

5. **Operational maturity**
   Backend hardened staging workers and container flows; frontend simplified its release/build pipeline to match the evolving deployment model.

## Bottom line

The last couple of weeks were not a small bug-fix phase. They were a broad consolidation phase across both repositories:

- heavy result flows moved from synchronous delivery to ticketed, paginated workflows
- large performance problems in word trends, KWIC, and DTM processing were addressed
- the backend architecture became more service-oriented and easier to reason about
- old or unused runtime code was removed or archived
- speech downloads became more consistent and robust
- frontend UX now reflects backend progress more accurately through progressive loading and better error handling
- deployment, staging, docs, and tests were all upgraded alongside the feature work

This means the system is now not just faster, but also more maintainable, more observable, and more consistent across backend and frontend.