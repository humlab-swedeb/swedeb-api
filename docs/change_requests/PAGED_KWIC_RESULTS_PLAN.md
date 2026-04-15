# Implementation Plan: Paged KWIC Results

## Execution Status

Current execution progress:

- Proposal approved as the implementation baseline: `docs/change_requests/PAGED_KWIC_RESULTS_DESIGN.md`
- Follow-up n-gram proposal split out: `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`
- Phase 0 finalized in the design: request/response contracts, manifest metadata, sort rules, and module targets are now frozen
- Phase 1 foundation implemented: shared `create_app()`, lifespan-managed `ResultStore`, dependency wiring, and cache config keys
- Phase 2 store foundation implemented: ticket metadata, Feather artifacts, expiry cleanup, sweeper loop, and eviction rules
- Phase 3 API implemented: ticket schemas, submit/status/results endpoints, shared filter normalization, and ticket paging behavior
- Phase 4 download integration implemented: ticket-based speech download, direct artifact-backed archive generation, and `ticket_id` conflict handling
- Phase 5 frontend migration implemented: ticket submit/poll/page flow, server-side KWIC pagination, ticket-based speech download, and synchronous CSV/XLSX export preservation
- Phase 6 validation started: parity sample locked, ticket download baseline verified, and initial query/page latency recorded in `docs/change_requests/PAGED_KWIC_RESULTS_VALIDATION.md`
- Backend implementation: **COMPLETED**
- Frontend implementation: **COMPLETED**
- Validation and benchmarks: **IN PROGRESS**

Status by phase:

1. Phase 0: **COMPLETED**
2. Phase 1: **COMPLETED**
3. Phase 2: **COMPLETED**
4. Phase 3: **COMPLETED**
5. Phase 4: **COMPLETED**
6. Phase 5: **COMPLETED**
7. Phase 6: **IN PROGRESS**

## Scope

This plan implements `docs/change_requests/PAGED_KWIC_RESULTS_DESIGN.md`.

Target outcomes:

1. Add an additive ticket-based KWIC workflow alongside the existing synchronous endpoint.
2. Persist mapped KWIC result artifacts on disk with short-lived server-side reuse.
3. Add server-side page and sort retrieval for cached KWIC results.
4. Add ticket-based speech download using cached speech IDs and manifest metadata.
5. Migrate the frontend to an opt-in ticket flow while keeping current CSV/XLSX export on the synchronous path.
6. Validate parity, non-happy-path behavior, cleanup, and performance before rollout.

## Non-Goals

This plan does not implement:

1. n-gram paging; see `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`
2. within-ticket re-filtering of KWIC results
3. ticket-based CSV/XLSX export for the frontend
4. multi-worker shared-cache support

## Guiding Principles

- Keep `GET /v1/tools/kwic/{search}` unchanged.
- Keep router logic thin and push behavior into services and mappers.
- Cache the mapped KWIC API frame, not the raw KWIC service frame.
- Use one canonical app factory and lifespan path.
- Keep rollout reversible and frontend adoption explicit.

## Work Breakdown

## Phase 0: Freeze Contracts and Scaffolding

### Tasks

1. Freeze request and response contracts
- Finalize `KWICFilterRequest` and `KWICQueryRequest`.
- Finalize `KWICTicketAccepted`, `KWICTicketStatus`, and `KWICPageResult`.
- Freeze allowed sort fields and default ordering.

2. Freeze artifact contract
- Define the canonical cached artifact as the mapped KWIC API frame plus `_ticket_row_id`.
- Freeze `speech_ids` ordering and checksum rules.
- Freeze manifest metadata fields for ticket-based download.

3. Freeze module layout
- Decide the canonical app factory module.
- Decide the `ResultStore` module path.
- Decide the dependency entrypoints to add in `api_swedeb/api/dependencies.py`.

### Deliverables

- Finalized schema section in `PAGED_KWIC_RESULTS_DESIGN.md`.
- Finalized app factory and `ResultStore` module targets.
- Finalized sort/order/download rules.

### Progress Checklist

- [x] Request models named and field list approved
- [x] Response models named and field list approved
- [x] Sort fields frozen
- [x] Default order frozen
- [x] Artifact column contract frozen
- [x] Speech ID ordering rule frozen
- [x] Checksum rule frozen
- [x] Manifest field list frozen
- [x] Canonical app factory target chosen
- [x] `ResultStore` module target chosen

### Exit Criteria

- No unresolved contract questions remain for the backend MVP.

## Phase 1: App Factory, Lifespan, and ResultStore Skeleton

### Tasks

1. Introduce canonical app construction
- Add one `create_app()` entrypoint.
- Move middleware and router assembly behind that factory.
- Make `main.py`, `docker/main.py`, and test app setup use the same factory.

2. Add `ResultStore` skeleton
- Add a dedicated `ResultStore` class.
- Add app-state storage via lifespan.
- Add dependency access through `get_result_store(request)`.

3. Add config keys
- Add cache config keys to `config/config.yml` and `tests/config.yml`:
  - `cache.result_ttl_seconds`
  - `cache.cleanup_interval_seconds`
  - `cache.max_artifact_bytes`
  - `cache.max_pending_jobs`
  - `cache.root_dir`
  - `cache.max_page_size`

### Deliverables

- Canonical app factory
- Lifespan-managed `ResultStore`
- Config keys in production and test config

### Progress Checklist

- [x] `create_app()` added
- [x] `main.py` uses `create_app()`
- [x] `docker/main.py` uses `create_app()`
- [x] Test app uses `create_app()`
- [x] `ResultStore` class added
- [x] `ResultStore` stored in `app.state`
- [x] `get_result_store(request)` dependency added
- [x] Cache config added to `config/config.yml`
- [x] Cache config added to `tests/config.yml`
- [x] Startup cleanup hook added
- [x] Shutdown cleanup hook added

### Exit Criteria

- All runtime entrypoints and tests construct the app through one lifespan path.

## Phase 2: ResultStore Persistence, Cleanup, and Concurrency

### Tasks

1. Implement ticket metadata handling
- Add ticket creation, state transitions, and metadata persistence.
- Store `speech_ids`, `manifest_meta`, and artifact size.

2. Implement disk artifact lifecycle
- Write artifacts atomically.
- Load mapped KWIC artifacts from disk.
- Delete expired or corrupt artifacts.

3. Implement locking and budget accounting
- Guard ticket state mutation and byte-budget accounting with a process-local lock.
- Define `pending`, `ready`, `error`, and cleanup transitions.
- Count `max_pending_jobs` as accepted tickets still in `pending` state.

4. Implement cleanup flows
- Request-path cleanup
- Periodic sweeper
- Startup stale-artifact cleanup
- Oldest-ready eviction under byte pressure

### Deliverables

- Working `ResultStore` with cleanup and locking
- Artifact persistence using Feather/Arrow IPC
- Explicit byte-budget and pending-job enforcement

### Progress Checklist

- [x] Ticket creation method implemented
- [x] Ticket state enum/contract implemented
- [x] Atomic artifact write implemented
- [x] Artifact load method implemented
- [x] Expired artifact delete path implemented
- [x] Corrupt/missing artifact delete path implemented
- [x] Process-local lock added
- [x] Budget accounting added
- [x] Pending-job accounting added
- [x] Request-path cleanup added
- [x] Periodic sweeper added
- [x] Startup cleanup added
- [x] Oldest-ready eviction added

### Exit Criteria

- `ResultStore` can safely accept, complete, expire, and evict tickets under single-worker concurrent request load.

## Phase 3: Backend KWIC Ticket API

### Tasks

1. Add request/response schemas
- Add submit, status, and page schemas.
- Add validation for page size and sort fields.

2. Add submit flow
- Normalize request filters using a pure helper.
- Create a ticket immediately.
- Reject on queue saturation.
- Schedule background execution without adding a second process pool around KWIC.

3. Add query completion flow
- Call `KWICService.get_kwic()`.
- Map the result with `kwic_to_api_frame(...)`.
- Add `_ticket_row_id`.
- Persist the artifact and ready metadata.

4. Add status and results endpoints
- Return `202` for pending results.
- Return `409` for error results.
- Return `404` for expired or unknown tickets.
- Return `400` for invalid sort or out-of-range page requests.

### Deliverables

- `POST /v1/tools/kwic/query`
- `GET /v1/tools/kwic/status/{ticket_id}`
- `GET /v1/tools/kwic/results/{ticket_id}`

### Progress Checklist

- [x] Submit request schema added
- [x] Status response schema added
- [x] Page response schema added
- [x] Filter normalization helper added
- [x] Submit endpoint added
- [x] Status endpoint added
- [x] Results endpoint added
- [x] Queue saturation path returns `429`
- [x] Pending results path returns `202`
- [x] Error results path returns `409`
- [x] Expired/unknown path returns `404`
- [x] Invalid sort path returns `400`
- [x] Out-of-range page path returns `400`
- [x] Default ordering uses `_ticket_row_id`
- [x] Sort tie-breaker uses `_ticket_row_id`

### Exit Criteria

- The ticketed KWIC backend works end-to-end without changing the existing synchronous endpoint.

## Phase 4: Ticket-Based Download Integration

### Tasks

1. Extend download service contract
- Add a dedicated path that accepts `speech_ids` plus `manifest_meta` directly.
- Preserve existing body-ids and query-filter flows.

2. Add endpoint precedence handling
- Make `ticket_id` mutually exclusive with user-supplied selection-bearing filters and body `ids`.
- Ignore default sort/pagination params when checking for conflicts.
- Return explicit `400`, `404`, or `409` behavior.

3. Preserve stable ordering and checksum
- Use first-occurrence `_ticket_row_id` order for deduplicated speech IDs.
- Use checksum over sorted unique `speech_id` values.

### Deliverables

- Download service method for `speech_ids + manifest_meta`
- `/speeches/download?ticket_id=...` ticket path
- Conflict detection helper for selection-bearing filters

### Progress Checklist

- [x] Download service direct-input method added
- [x] Ticket manifest metadata shape implemented
- [x] Ticket download path added to router
- [x] `ticket_id` vs `ids` conflict handling added
- [x] `ticket_id` vs selection-filter conflict handling added
- [x] Default sort/pagination params ignored in conflict detection
- [x] Pending ticket download returns `409`
- [x] Expired ticket download returns `404`
- [x] Stable speech ordering implemented
- [x] Stable checksum implemented

### Exit Criteria

- Ticket-based download produces a stable, validated archive without re-deriving selection from `CommonQueryParams`.

## Phase 5: Frontend Opt-In Migration

### Tasks

1. Add ticket workflow to frontend store
- Update `kwicDataStore.js` to submit, poll, and fetch pages.
- Keep the old synchronous flow available during rollout.

2. Update table behavior
- Switch `kwicDataTable.vue` to server-side pagination mode for the new flow.
- Preserve user-visible page and sort behavior.

3. Preserve export behavior
- Keep CSV/XLSX export on the synchronous flow for the MVP.
- Do not make the frontend fetch all pages to rebuild export.

### Deliverables

- Frontend ticket flow behind an explicit opt-in path
- Server-side paged table behavior
- Export preserved on existing flow

### Progress Checklist

- [x] Store submit action added
- [x] Store status polling added
- [x] Store page fetch action added
- [x] Table switched to server-side pagination for ticket flow
- [x] Total count wired to paged response
- [x] Pending/error UI state added
- [x] Existing synchronous path still callable
- [x] CSV/XLSX export still works through synchronous path
- [x] No frontend code fetches all pages for export

### Exit Criteria

- Frontend can opt into ticketed paging without breaking existing export behavior.

## Phase 6: Validation, Benchmarking, and Rollout

### Tasks

1. Functional parity
- Compare paged ticket output against the current synchronous KWIC endpoint after mapping.
- Validate stable totals and ordering.

2. Download validation
- Validate deduplicated speech IDs from the cached artifact.
- Validate manifest content, ordering, and checksum.

3. Cleanup and reliability
- Validate expiry, startup cleanup, and corrupt artifact behavior.
- Validate queue saturation and byte-budget exhaustion behavior.

4. Benchmarking
- Measure initial query execution versus the current synchronous endpoint.
- Measure cached page fetch latency.
- Measure artifact storage behavior under eviction pressure.

5. Rollout
- Keep the existing KWIC endpoint live.
- Enable frontend opt-in gradually.
- Defer n-gram work to `PAGED_NGRAM_RESULTS_DESIGN.md`.

### Deliverables

- Parity report
- Download validation report
- Cleanup/reliability summary
- Benchmark report
- Rollout checklist completion

### Progress Checklist

- [x] Paged rows match synchronous mapped endpoint for the same query
- [x] Stable totals verified
- [x] Stable ordering verified
- [x] Ticket download speech ID baseline verified
- [x] Ticket download manifest verified
- [x] Expiry cleanup verified
- [x] Startup cleanup verified
- [x] Corrupt artifact behavior verified
- [x] Queue saturation behavior verified
- [x] Byte-budget exhaustion behavior verified
- [x] Query latency benchmark recorded
- [x] Page latency benchmark recorded
- [x] Artifact budget behavior recorded
- [x] Existing synchronous KWIC endpoint still live
- [x] Frontend opt-in rollout path documented

### Exit Criteria

- The ticketed KWIC path meets parity and reliability requirements and can be rolled out without removing the existing endpoint.

## Final Readiness Checklist

- [x] One canonical app factory exists and is used by runtime, Docker, and tests
- [x] `ResultStore` lifecycle is managed by FastAPI lifespan
- [x] Mapped KWIC frame is the cached artifact contract
- [x] Ticket metadata includes `speech_ids` and `manifest_meta`
- [x] Non-happy-path API behavior is fully defined and implemented
- [x] Ticket download works without re-deriving filter selection from `CommonQueryParams`
- [x] Frontend ticket flow is opt-in
- [x] CSV/XLSX export remains on the synchronous flow for the MVP
- [x] Validation and benchmark reports exist
- [ ] Follow-up n-gram work remains separate

## Final Recommendation

Implement the plan in order.

Do backend infrastructure and validation before frontend migration, keep the synchronous KWIC path intact throughout, and do not begin n-gram paging until the KWIC ticket flow has been validated in practice.