# Multiuser Usage Assessment

## Purpose

This note assesses the current ticket-based async execution flow for concurrent use by many users and browser clients.

It focuses on the recently introduced ticket, Celery, and result-store paths, with brief coverage of frontend polling behavior where that behavior materially affects backend load.

This note began as a static code and configuration assessment. It now also records a repeatable staged load-test baseline for the Phase 1 and Phase 2 ticket deployment shapes. It is still not a full production-corpus benchmark.

## Scope Reviewed

The assessment is based on the current implementation in these areas:

- `api_swedeb/api/services/result_store.py`
- `api_swedeb/api/services/kwic_ticket_service.py`
- `api_swedeb/api/services/word_trend_speeches_ticket_service.py`
- `api_swedeb/api/v1/endpoints/tool_router.py`
- `api_swedeb/celery_app.py`
- `api_swedeb/celery_tasks.py`
- `api_swedeb/app.py`
- `config/config.yml`
- `src/stores/kwicDataStore.js`
- `src/stores/wordTrendsDataStore.js`
- `src/stores/speechesDataStore.js`

## Executive Summary

The current implementation may be workable in the narrowest deployment shape, but it should not yet be treated as robust for the Phase 1 and Phase 2 deployment shapes covered by this document.

The main problem is not ordinary thread safety inside a single process. The main problem is that ticket metadata and capacity tracking are process-local while task execution and artifact files are cross-process. That creates correctness and operability risks under realistic multi-user deployment conditions.

Using the rollout terminology from this document:

- **Phase 1** is to make the current one app-container, one uvicorn-worker API deployment robust under real multi-user load.
- **Phase 2** is to make multiple API processes safe, such as multiple uvicorn workers in one deployment unit.
- Multi-container horizontal scaling is deferred to a separate follow-up change request.

In short:

- the current implementation is closest to a Phase 1 starting point, but is not yet robust enough even there
- the current design is not safe for Phase 2 because ticket truth still depends too much on API-process-local state
- multi-container horizontal scaling is intentionally out of scope for this document and is tracked separately
- frontend polling will amplify backend load under many active clients
- the speeches ticket path is more fragile than the Celery-backed KWIC path because it still performs heavy work inside the API process

## Overall Assessment

### Current rating

**Not yet ready for high-confidence multiuser operation across the Phase 1 and Phase 2 deployment shapes.**

### What works reasonably well

- Ticket IDs are UUID-based and do not present an obvious collision risk.
- Artifact writes use a partial file and then replace it atomically, which reduces the chance of readers seeing half-written output.
- The `ResultStore` uses a lock, so the in-process ticket map is protected against simple thread races inside one process.
- The Celery task ID is aligned with the ticket ID, which is a good basis for a shared control-plane design.

### What blocks high-confidence multiuser use

- Ticket state is not truly shared across API processes.
- Result-store cleanup is destructive at process startup.
- Queue limits and artifact-capacity limits are enforced only per process, not globally.
- Client polling is frequent and uncoordinated.
- Some paged result paths re-read and re-sort full artifacts on every page request.

## Findings

### 1. Ticket metadata is process-local, so multi-instance status and retrieval are unreliable

**Severity:** High

The API stores `ResultStore` on `app.state`, which means each API process keeps its own in-memory ticket map.

Consequences:

- A ticket created through one API process is not guaranteed to be visible through another API process.
- A valid Celery task can still produce `404 Ticket not found or expired` if the next status or result request reaches a different API process.
- API restarts lose the in-memory ticket map even if Redis still knows the task state and the artifact file still exists.

Why this matters for many users:

- Any load balancer without strict session affinity can surface intermittent ticket lookup failures.
- Rolling restarts can invalidate active user flows.
- Support and incident handling become difficult because the system has no durable shared ticket registry.

This is the largest correctness risk in the current design.

### 2. Result-store startup cleanup is destructive across processes

**Severity:** High

Every `ResultStore` startup performs cleanup that removes existing artifact files from the shared cache directory.

This behavior is especially risky because:

- the API process creates a `ResultStore` at application startup
- Celery worker processes also create their own `ResultStore`
- worker-side stores are created lazily and call synchronous startup logic

Consequences:

- A newly started process can remove artifacts created by an already-running process.
- In-flight or recently completed tickets can be invalidated during worker churn or deployment events.
- The system becomes sensitive to process restarts in ways that users will observe as missing results or inconsistent paging.

This is a concrete concurrency hotspot because it creates cross-process interference against shared filesystem state.

### 3. Pending-job limits are local counters, not global concurrency control

**Severity:** High

`max_pending_jobs` is enforced against the local in-memory ticket map only. The configured value is currently `2`.

Consequences:

- The effective system-wide pending-job count grows with the number of API processes.
- Operators cannot reason about the real queue limit from configuration alone.
- Under load, the system can accept more jobs than intended and then fail later from CPU, memory, or artifact-storage pressure.

The configured limit gives a false sense of global protection.

### 4. Artifact-capacity tracking is also local and can drift from reality

**Severity:** High

Artifact byte accounting is maintained in a per-process `_artifact_bytes` counter. It is not rebuilt from disk on startup and it is not shared across API or worker processes.

Consequences:

- Multiple processes can independently believe there is free capacity and overcommit the shared cache directory.
- Eviction decisions are made from incomplete local knowledge.
- Capacity enforcement will be approximate at best and misleading at worst.

This is not only a performance concern. It can turn into user-visible failures when one process evicts or deletes data another process still assumes is available.

### 5. The speeches ticket flow still runs heavy work in the API process

**Severity:** Medium to High

The `/speeches/query` flow still uses `BackgroundTasks` inside the API process instead of Celery-backed worker isolation.

Consequences:

- A burst of user requests can consume API worker time directly.
- The web tier is exposed to long-running data work under load.
- This path is more likely to degrade general API responsiveness than the Celery-backed ticket flows.

Compared with the KWIC and word-trend speeches flows, this path is more fragile under concurrent usage.

### 6. Frontend polling will amplify backend load under many browser clients

**Severity:** Medium

The frontend polling interval is `1000 ms` with up to `120` attempts in all three ticketed stores.

Consequences:

- Many simultaneous users generate a steady stream of status requests.
- Polling continues even though jobs may still be queue-bound or CPU-bound for long periods.
- Status traffic competes with actual result generation and page retrieval.

This is unlikely to break correctness by itself, but it will increase load noticeably in real use.

### 7. Paged result retrieval is heavier than it looks

**Severity:** Medium

Ready-ticket page retrieval reads the full Feather artifact and sorts the full DataFrame before slicing the requested page.

Consequences:

- Repeated browsing of a large result set creates repeated disk I/O and CPU work.
- The system does not get the full benefit of server-side paging when many users browse large tickets.
- A few popular tickets can still create meaningful backend load even after the expensive search itself has finished.

This is a throughput hotspot rather than a correctness defect.

### 8. Test coverage does not appear to exercise real multi-process failure modes

**Severity:** Medium

There is meaningful unit coverage around Celery-state mapping and artifact storage, but the current tests do not appear to validate the failure modes most likely in production:

- multiple API processes with separate in-memory stores
- multiple worker processes touching the same cache directory
- restart behavior with in-flight tickets
- load-balancer routing across different API instances
- global limit enforcement under concurrent submissions

This increases the chance that the current design behaves correctly in isolated tests but fails under real deployment patterns.

## Risk Summary

| Area                                 | Risk level  | Main issue                                            |
|--------------------------------------|-------------|-------------------------------------------------------|
| Ticket status consistency            | High        | In-memory metadata is not shared across API processes |
| Artifact survival across restarts    | High        | Startup cleanup can delete shared artifacts           |
| Pending-job throttling               | High        | Limit is local, not global                            |
| Artifact-capacity enforcement        | High        | Byte accounting is local, not global                  |
| Speeches ticket execution            | Medium-High | Heavy work remains in API process                     |
| Polling load                         | Medium      | 1-second polling across many clients                  |
| Page retrieval cost                  | Medium      | Full artifact reads and sorts per page request        |
| Test coverage for deployment reality | Medium      | Missing multi-process and restart-focused validation  |

## Action Items

### Priority 0: Correctness and safety

1. Move ticket metadata from process-local memory to a shared store.
   Use Redis or another shared backing store as the source of truth for ticket lifecycle state, expiry, and error metadata.

2. Remove destructive artifact deletion from normal process startup.
   Startup should clean only incomplete temporary files, not all existing artifacts in the shared cache directory.

3. Make status and result lookup resilient to API restarts and cross-instance routing.
   The API should be able to reconstruct ticket state from shared metadata plus artifact presence, instead of requiring the original in-memory ticket entry.

4. Rework global concurrency and capacity control.
   Enforce `max_pending_jobs` and artifact-capacity limits in a shared, atomic control plane rather than per-process counters.

### Priority 1: Load and scalability

5. Move the `/speeches/query` async path onto Celery as well.
   Keep long-running search work out of the API process so the web tier stays responsive under user bursts.

6. Reduce polling pressure.
   Increase polling interval, add backoff, honor `Retry-After` consistently, or move to a push-based or long-poll status model.

7. Reduce page retrieval cost for ready tickets.
   Cache sorted indices, persist sort-ready views, or move to a storage/query approach that supports page slicing without full DataFrame reads and full re-sorts on every request.

### Priority 2: Operability and validation

8. Add restart and multi-instance integration tests.
   Explicitly test ticket submission on one API process and status/result retrieval on another.

9. Add worker-churn tests.
   Validate that a new Celery worker process cannot delete artifacts created by another worker.

10. Add concurrency-limit tests against realistic deployment topology.
    Verify global behavior with multiple API processes and multiple worker processes.

11. Run staged load tests before treating the current design as horizontally scalable.
    Include mixed workloads for KWIC, word-trend speeches, speeches tickets, paging, and download behavior.

## Recommended Minimum Acceptance Criteria Before Declaring Multiuser Readiness

The system should not be treated as ready for high-confidence multiuser deployment until all of the following are true:

- ticket status survives API restart
- ticket status and result retrieval work across different API instances
- artifact files survive worker startup and restart
- queue and storage limits are enforced globally, not per process
- speeches async work is isolated from the API process or intentionally capacity-limited
- staged load testing confirms acceptable latency and error rate under concurrent polling and page retrieval

## Conclusion

The current async ticket-based system is a meaningful improvement for isolating some long-running work, especially KWIC execution, but it is still built around a process-local state model. That is the core architectural weakness for concurrent multi-user use.

The main hotspots are not small implementation races inside a single process. The hotspots are shared-filesystem behavior, process-local ticket state, non-global limit enforcement, and client polling volume. Those issues should be addressed before relying on this design for the Phase 1 and Phase 2 deployment shapes covered here.

## Implementation Plan

This section turns the action items above into a concrete change plan with proposed code changes, validation scope, and rollout order.

Status note:

- The findings and risk statements above describe the baseline assessment that motivated this work.
- This implementation plan now covers Phase 1 and Phase 2 only.
- Phase 3 multi-container work is tracked separately in `docs/change_requests/MULTIUSER_PHASE3_MULTI_CONTAINER_SCALING.md`.
- The checklists below track implementation progress after that assessment.
- Items marked complete reflect code and focused validation already added in the repository.
- Items marked remaining are still needed before the phase should be treated as complete.

### Design goal

Keep the current high-level split intact:

- Redis and Celery remain the control plane for async work.
- Feather artifacts remain the data plane for large result sets.
- The API remains responsible for status polling, result paging, and downloads.

The main change is that ticket lifecycle state must stop depending on process-local memory.

### Two-phase rollout in this document

The concurrency work can be staged around deployment topology:

1. make the current single app-container, single uvicorn-worker API deployment robust under real multi-user load
2. remove API-process affinity so multiple API processes in one deployment unit are safe

Those phases share the same root fix: move ticket state and global accounting out of API-process memory.

Multi-container horizontal scaling is a separate follow-up scope and is not required for Phase 1 or Phase 2 to be deployable.

## Progress Checklist

### Overall progress

- [x] Added a shared ticket metadata layer backed by Redis for ticket lifecycle state.
- [x] Refactored `ResultStore` to use shared ticket metadata instead of relying only on process-local state.
- [x] Removed destructive startup cleanup that deleted valid ready artifacts.
- [x] Added restart-safe startup behavior for API and worker-side `ResultStore` instances.
- [x] Added shared pending-job accounting across store instances.
- [x] Added shared artifact-byte accounting across store instances.
- [x] Added worker-churn coverage to verify a new store startup does not delete another store's ready artifact.
- [x] Moved `/speeches/query` onto the ticket-service pattern with Celery-backed execution in production mode.
- [x] Added speeches ticket service, route coverage, and integration coverage.
- [x] Added backend `Retry-After` hints for pending ticket responses.
- [x] Reduced frontend polling pressure with bounded backoff that honors retry hints.
- [x] Reduced repeated page-sort cost with artifact caching and cached sorted positions.
- [x] Added true multi-process API integration coverage that submits on one API process and polls or pages on another.
- [x] Added API-level pending-limit and artifact-capacity coverage across separate API app instances.
- [x] Added startup counter-repair and expired-ticket cleanup coverage for shared-state recovery scenarios.
- [x] Validated the design under real multi-worker uvicorn topology instead of only per-service or per-store tests.
- [x] Added a repeatable staged load-test harness for the current Phase 1 and Phase 2 deployment shapes.
- [x] Audited the remaining speeches ticket lifecycle for creating-process assumptions and added cross-instance download coverage.
- [x] Added frontend regression coverage for the shared ticket polling backoff helper used by the ticket stores.

### Phase 1 checklist

Completed:

- [x] Introduced shared ticket metadata through `ticket_state_store.py`.
- [x] Wired shared ticket metadata into `ResultStore` and the ticket services.
- [x] Removed destructive startup artifact deletion and kept startup cleanup limited to partial files.
- [x] Added startup behavior that preserves ready artifacts across worker churn and service restart.
- [x] Enforced pending-job limits through shared state instead of only per-process memory.
- [x] Enforced artifact-capacity accounting through shared state instead of only per-process memory.
- [x] Migrated `/speeches/query` to the worker-backed ticket flow used by the other async endpoints in production mode.
- [x] Added backend pending-response retry hints.
- [x] Reduced frontend polling pressure with bounded backoff.
- [x] Reduced repeated page-read cost with artifact caching and cached sorted positions.
- [x] Added focused service, endpoint, and integration validation for the new ticket flows.
- [x] Added broader validation for expiry-driven counter repair and expired-ticket cleanup when shared counter keys need rebuilding.
- [x] Added and ran a staged load-test baseline for the current one-API-process deployment shape.
- [x] Added frontend regression coverage for the shared ticket polling backoff helper used by the ticket stores.

Remaining:

- None for the scoped Phase 1 backend and polling-hardening work tracked in this document.

### Phase 2 checklist

Completed:

- [x] Added restart-style shared-state tests that recreate store instances and verify ready tickets still resolve.
- [x] Added cross-instance service tests that create a ticket with one store instance and read it from another.
- [x] Added concurrent shared pending-limit coverage across store instances.
- [x] Added shared artifact-capacity coverage across store instances.
- [x] Added worker-churn coverage aligned with the Phase 2 validation goals.
- [x] Added a true API-level multi-process test that submits through API process A and polls or pages through API process B.
- [x] Added API-process-level pending-limit and artifact-capacity tests instead of relying only on store-level concurrency tests.
- [x] Validated behavior with more than one uvicorn worker in the same deployment unit.
- [x] Added and ran a staged load-test baseline for the current two-worker deployment shape.
- [x] Audited the remaining speeches ticket lifecycle for creating-process assumptions and added cross-instance download coverage.

Remaining:

- None for the scoped Phase 2 single-deployment multi-process work tracked in this document.

Deferred follow-up:

- Phase 3 multi-container deployment work has been split into `docs/change_requests/MULTIUSER_PHASE3_MULTI_CONTAINER_SCALING.md`.
- Future reconsideration of a dedicated speeches Celery queue has been split into `docs/change_requests/SPEECHES_DEDICATED_QUEUE_FOLLOWUP.md`.

### Staged load-test baseline

Command used:

- `python scripts/loadtest_ticket_deployments.py --output tests/output/loadtest_ticket_deployments.json`

Harness notes:

- The script starts the minimal uvicorn-backed ticket test app used by the multi-worker integration tests.
- Each ticket query uses a fixed 125 ms artificial search delay so queueing and worker distribution are visible instead of completing trivially.
- Each deployment shape runs three stages: `light` = 8 requests at concurrency 4, `medium` = 16 requests at concurrency 8, `heavy` = 32 requests at concurrency 16.
- Each request submits `/v1/tools/speeches/query`, polls the ticket until `ready`, and retrieves the first page.
- Results are stored in `tests/output/loadtest_ticket_deployments.json` for later comparison.

Observed baseline:

- Phase 1, one uvicorn worker: `light` 18.23 req/s with p95 end-to-end latency 235.40 ms; `medium` 34.39 req/s with p95 252.40 ms; `heavy` 37.64 req/s with p95 493.81 ms.
- Phase 2, two uvicorn workers: `light` 20.71 req/s with p95 end-to-end latency 202.51 ms; `medium` 36.07 req/s with p95 231.22 ms; `heavy` 57.08 req/s with p95 289.74 ms.
- All stages completed with zero submit failures, zero status failures, and zero page failures.
- The Phase 2 heavy stage improved throughput by about 52% and reduced p95 end-to-end latency by about 41% relative to the Phase 1 heavy stage.
- The two-worker baseline observed requests on both worker PIDs during every stage, which is consistent with the shared-state routing expectations validated elsewhere in this document.

Interpretation:

- The current Phase 1 shape remains correct under the staged harness, but heavy bursts show the expected single-worker latency growth.
- The current Phase 2 shape preserves correctness and materially improves burst handling for the ticket control plane.
- This baseline is sufficient to close the current staged-load-test item for Phase 1 and Phase 2 ticket deployment shapes.
- A later production-like benchmark should still use real corpus queries and the full deployment stack if the goal shifts from control-plane robustness to absolute user-facing capacity planning.

### Follow-up audit outcome

- The remaining Phase 2 audit focused on whether ticket-backed download operations still depended on the API process that accepted the original submit request.
- The main unvalidated slice was download behavior, because the download endpoints use shared ticket metadata and artifact access differently from status and page retrieval.
- Cross-instance integration coverage now verifies both `GET /v1/tools/speeches/download/{ticket_id}` and `POST /v1/tools/speeches/download?ticket_id=...` when the ticket is submitted through one API instance and downloaded through another.
- Cross-instance integration coverage now also verifies `GET /v1/tools/word_trend_speeches/download/{ticket_id}` for both CSV and JSON responses when the ticket is submitted through one API instance and downloaded through another.
- No additional creating-process assumption was found in the scoped ticket download lifecycle after that coverage was added.

### Phase 1: Make the current one-API-process deployment robust

**Goal:** Make the current deployment model safe for many concurrent users while keeping a single API process.

**Assumed topology:**

- one app container
- one uvicorn worker
- Redis
- Celery worker containers
- shared artifact volume between API and workers

This phase still includes cross-process behavior because Celery workers already run separately from the API process.

#### Work included in Phase 1

- introduce shared ticket metadata
- remove destructive artifact startup cleanup
- enforce global pending and artifact-capacity limits
- migrate speeches tickets to Celery-backed worker isolation
- reduce polling pressure and obvious page-read inefficiencies enough for the current deployment model

#### Proposed code changes for Phase 1

##### 1. Introduce shared ticket metadata

**Goal:** Make ticket status, expiry, and error metadata readable after restart and independent of API-local memory.

1. Add a shared ticket-state service backed by Redis.

   Suggested new module:

   - `api_swedeb/api/services/ticket_state_store.py`

   Suggested responsibilities:

   - create ticket records
   - read ticket records by ID
   - update ticket status transitions
   - maintain TTL and expiry
   - store compact metadata only
   - provide atomic counters for pending jobs

2. Keep `ResultStore` focused on artifacts, not ticket truth.

   In `api_swedeb/api/services/result_store.py`:

   - remove ticket lifecycle ownership from `_tickets` as the primary source of truth
   - keep artifact-path calculation and artifact load/store helpers
   - keep partial-file handling and artifact deletion helpers
   - retain in-process locking only for local filesystem mutation, not global queue state

3. Update the ticket services to read and write shared metadata first.

   In:

   - `api_swedeb/api/services/kwic_ticket_service.py`
   - `api_swedeb/api/services/word_trend_speeches_ticket_service.py`

   change the flow to:

   - create ticket in shared ticket-state store
   - enqueue Celery task using the shared ticket ID
   - update shared state on success or failure
   - look up status from shared state before checking artifact presence

4. Update dependency wiring.

   In `api_swedeb/api/dependencies.py` and app/container wiring:

   - provide a singleton `TicketStateStore`
   - inject it into the ticket services
   - stop relying on `app.state.result_store` as the sole ticket lookup mechanism

5. Extend configuration.

   In:

   - `config/config.yml`
   - `tests/config.yml`

   add explicit configuration for shared ticket-state prefixes, TTL, and optional Redis namespace separation from Celery task keys.

##### Suggested data model

Each ticket record should be compact and JSON-serializable. Suggested fields:

- `ticket_id`
- `kind` such as `kwic`, `word_trend_speeches`, `speeches`
- `status`
- `created_at`
- `expires_at`
- `ready_at`
- `error`
- `total_hits`
- `artifact_path`
- `query_meta`
- `manifest_meta`

##### Test coverage for shared ticket metadata

- unit tests for shared ticket create, update, expiry, and status transitions
- API tests that create a ticket with one service instance and read it back with a separate service instance
- restart-style tests that recreate the service object and confirm the ticket still exists
- tests for failure transitions when the Celery task returns `FAILURE`

##### 2. Remove destructive startup behavior

**Goal:** Prevent process startup from deleting valid artifacts created by other processes.

1. Split startup cleanup in `api_swedeb/api/services/result_store.py` into two behaviors:

   - safe cleanup of orphaned partial files
   - explicit artifact garbage collection for expired tickets only

2. Remove the current behavior that deletes all `*.feather` files during normal startup.

3. Add a garbage-collection method that:

   - queries shared ticket metadata
   - deletes only artifacts for expired or terminally invalid tickets
   - can run periodically in the API process or in a dedicated maintenance task

4. Make worker startup idempotent and non-destructive.

   In worker-side store initialization in:

   - `api_swedeb/api/services/kwic_ticket_service.py`
   - `api_swedeb/api/services/word_trend_speeches_ticket_service.py`

   ensure worker creation never performs global artifact cleanup.

##### Test coverage for artifact-startup safety

- startup tests proving valid artifacts survive new API-store creation
- worker-start tests proving valid artifacts survive new worker-store creation
- partial-file cleanup tests proving stale `.partial` or `.tmp` files are still removed
- GC tests proving only expired ticket artifacts are deleted

##### 3. Enforce global pending and capacity limits

**Goal:** Make queue and storage limits mean the same thing regardless of process count.

1. Move `max_pending_jobs` enforcement into the shared ticket-state store.

   Suggested implementation shape:

   - atomic increment when creating a `pending` ticket
   - atomic decrement on transition to `ready`, `error`, or expiry
   - reject new tickets when the shared counter reaches the configured ceiling

2. Replace local `_artifact_bytes` accounting with shared capacity accounting.

   Options, in preferred order:

   - store artifact byte totals in Redis with atomic updates
   - or compute live usage from the filesystem during GC plus shared counters for recent mutations

3. Make eviction decisions from shared metadata, not process-local memory.

4. Record artifact size into shared ticket metadata after successful write so any API instance can reason about cache pressure.

##### Test coverage for global limit enforcement

- concurrent submission tests verifying the global pending limit across multiple service instances
- artifact-capacity tests across multiple store instances sharing the same directory
- eviction tests proving the oldest eligible ready tickets are removed based on shared metadata
- expiry tests proving counters are repaired correctly when tickets age out

##### 4. Migrate speeches tickets to Celery-backed isolation

**Goal:** Keep heavy speech-query work out of the API process under concurrent user load.

1. Extract a dedicated speeches ticket service.

   Suggested new module:

   - `api_swedeb/api/services/speeches_ticket_service.py`

2. Mirror the existing ticket-service pattern used by KWIC and word-trend speeches:

   - submit ticket
   - enqueue Celery task
   - update shared ticket metadata
   - read result artifact for paging and downloads

3. Add a Celery task wrapper in `api_swedeb/celery_tasks.py`.

4. Update `api_swedeb/api/v1/endpoints/tool_router.py` so `/speeches/query` no longer executes the heavy search work through API-local `BackgroundTasks` in production mode.

5. Keep speech queries on the default queue for Phase 1 and Phase 2.

   Revisit a dedicated speeches queue only as a later operational optimization if staged load testing shows that mixed default-queue traffic causes unacceptable latency or worker contention.

##### Test coverage for speeches-ticket migration

- unit tests for `SpeechesTicketService` submit, execute, status, and page retrieval
- endpoint tests for `/speeches/query`, `/speeches/status/{ticket_id}`, and `/speeches/page/{ticket_id}`
- Celery integration tests matching the current KWIC style
- regression tests ensuring downloads still work for ticket-based speeches results

##### 5. Reduce polling pressure and page cost

**Goal:** Lower backend load from browsers and ready-ticket browsing in the current deployment model.

1. Update frontend polling behavior in:

   - `src/stores/kwicDataStore.js`
   - `src/stores/wordTrendsDataStore.js`
   - `src/stores/speechesDataStore.js`

   Suggested changes:

   - start with a slower interval such as 2 to 3 seconds
   - apply exponential or stepped backoff
   - honor `Retry-After` when the backend returns `202` or `429`
   - stop polling early for terminal ticket states

2. Consider exposing suggested retry timing from the backend status endpoints.

3. Reduce page-read cost on the backend.

   Options:

   - precompute and cache default-order row IDs
   - cache sorted indices for supported sort fields
   - switch to Arrow dataset or another layout that supports cheaper filtered page access

4. Ensure download paths use the ticket artifact directly when available, rather than re-running legacy full-result fetches.

##### Test coverage for polling and paging changes

- frontend store tests for polling backoff logic
- API tests verifying `Retry-After` behavior on pending and throttled responses
- backend performance regression tests for repeated page access on large artifacts

#### Phase 1 exit criteria

Phase 1 should be considered complete when all of the following are true:

- one API process can survive concurrent user load without relying on process-local ticket truth
- API restart does not lose active ticket state
- worker startup does not delete valid artifacts
- global pending and capacity limits are enforced against the current deployment
- `/speeches/query` no longer performs production-grade heavy work in the API process
- polling and ready-ticket browsing are meaningfully less expensive than they are now

### Phase 2: Make multiple API processes safe

**Goal:** Remove API-process affinity so multiple API processes can share the same workload safely.

**Examples of Phase 2 topology:**

- one app container started with more than one uvicorn worker
- one deployment unit running more than one API process on the same host

This phase does not require multiple app containers yet. It requires that no request depends on the specific API process that created the ticket.

#### Work included in Phase 2

- prove ticket submission on one API process and status/result retrieval on another
- prove pending and capacity limits behave identically across multiple API processes
- prove artifact reads and deletions remain correct when multiple API processes touch the same shared state
- remove any remaining app-state assumptions from the ticket lifecycle

#### Proposed validation and hardening for Phase 2

1. Multi-process API test

   - create ticket through API process A
   - poll and fetch results through API process B
   - verify no in-memory affinity is required

2. Restart survivability test

   - create ticket
   - recreate API process or service layer
   - verify status and results remain accessible

3. Concurrent submit test across API processes

   - simulate concurrent submissions from multiple API processes
   - verify the shared pending limit is respected exactly

4. Artifact-capacity test across API processes

   - simulate multiple API processes updating and reading shared capacity state
   - verify eviction and capacity enforcement remain deterministic

5. Worker-churn test

   - create artifact through worker A
   - initialize worker B
   - verify artifact is still present

#### Phase 2 exit criteria

Phase 2 should be considered complete when all of the following are true:

- ticket lookup no longer depends on which API process created the ticket
- multi-worker uvicorn deployment behaves the same as one-worker deployment for ticket lifecycle correctness
- global limits remain exact across API processes
- restart and worker-churn tests pass consistently

### Recommended implementation order

Use this order to reduce risk while keeping changes incremental:

1. complete the Phase 1 correctness fixes for the current deployment
2. validate and harden multi-process API behavior for Phase 2
3. treat multi-container horizontal scaling as a separate follow-up after Phases 1 and 2 are deployable

This order fixes correctness first and optimization second.

### Suggested definition of done

Treat the concurrency work as complete only when all of the following are true:

- ticket lookup no longer depends on the API process that created the ticket
- API restart does not lose active ticket state
- worker startup does not delete valid artifacts
- global pending and capacity limits are enforced atomically
- `/speeches/query` no longer performs production-grade heavy work in the API process
- frontend polling volume is reduced or bounded by backend guidance
- integration tests cover restart and multi-process API scenarios
- validation confirms the Phase 1 and Phase 2 deployment shapes are deployable without Phase 3 work

Horizontal scaling across multiple API containers or replicas is intentionally excluded from this definition of done. The dedicated follow-up scope lives in `docs/change_requests/MULTIUSER_PHASE3_MULTI_CONTAINER_SCALING.md`.
