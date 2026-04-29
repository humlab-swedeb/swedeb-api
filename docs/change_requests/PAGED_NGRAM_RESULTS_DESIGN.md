# Change Request: Paged N-Gram Results Design

**Status**: Ready for implementation — KWIC and speeches ticket patterns are established  
**Scope**: n-gram paging, pre-search estimation, progressive result loading, bulk archive export, and sync endpoint deprecation  
**Goal**: define a ticket-based n-gram design aligned with the KWIC flow — both tools use CWB keyword windows as their data source

---

## Summary

N-gram paging should be designed separately from KWIC.

The current n-gram pipeline already reduces raw keyword windows into an aggregated result table. That means the cache payload, supported reuse, and validation target differ from KWIC. The recommended MVP is to cache the final aggregated n-gram table for one exact query and support page and sort reuse only. Changing filters or recomputing counts should create a new ticket.

This proposal follows the KWIC ticket flow as its primary template, not the speeches flow. Both KWIC and n-grams retrieve raw keyword windows from CWB before further processing, so their performance profile, shard decomposition strategy, and estimation approach are closely analogous. The speeches ticket flow is a simpler single-shot pattern that does not apply here.

## Problem

`GET /v1/tools/ngrams/{search}` currently returns the full n-gram result in one response, and the client keeps the full table in memory.

That creates the same broad UX and payload problems as KWIC:

1. the browser waits for the full response before rendering
2. the full result stays resident in client memory
3. page and sort changes reuse client memory instead of server-side paging

But n-grams differ from KWIC in one important way: the backend already collapses raw windows into an aggregated table before the API response is built. After that reduction, the final table no longer supports within-ticket metadata re-filtering or recomputation of counts for a narrower subset.

## Scope

This proposal covers:

1. a pre-search hit estimate endpoint
2. a ticketed n-gram submit/status/results workflow with progressive shard delivery
3. the canonical cached payload for n-gram results
4. supported and unsupported reuse within one ticket
5. export behavior for paged n-gram results
6. rollout order relative to the KWIC ticket flow

## Non-Goals

This proposal does not cover:

1. re-filtering cached n-gram results by year, party, gender, or other metadata
2. recomputing counts for narrower subsets from an already aggregated cached result
3. changing the underlying n-gram extraction or aggregation algorithm

## Current Behavior

The current n-gram pipeline behaves like this:

1. `GET /v1/tools/ngrams/{search}` queries keyword windows from the corpus.
2. The backend transforms windows into n-grams.
3. The result is aggregated into `ngram`, `window_count`, and deduplicated `documents`.
4. The mapper converts that table into the public API shape.
5. The frontend receives the full n-gram result set in one response.

## Proposed Design

### Established Patterns to Reuse

The following patterns are already implemented and tested; n-gram paging should reuse them unchanged:

- **`ResultStore`** — disk-backed artifact storage, ticket lifecycle, expiry, cleanup, and byte-budget enforcement. N-gram tickets are stored here alongside KWIC and speeches tickets, separated by ticket type/namespace.
- **`TicketStateStore`** — shared ticket metadata and counters backed by `cache.ticket_state_backend_url` (Redis). Allows ticket status and pending counts to survive process boundaries.
- **Celery multiprocessing dispatch** — production mode dispatches to the `multiprocessing` Celery queue (same queue as KWIC), where the worker runs `--pool=solo` and may safely use `multiprocessing.Pool`. Development mode (`celery_enabled: false`) uses FastAPI `BackgroundTasks` with single-process execution and skips the `PARTIAL` phase. N-gram queries over a large year range and wide n-gram width can be slow; the same year-range shard decomposition that proved necessary for KWIC applies here.
- **Deprecated endpoint pattern** — the existing synchronous `GET /v1/tools/ngrams/{search}` moves to `deprecated_endpoints.py` once the ticketed path is validated; it is not removed immediately.
- **Bulk archive export** — follows the `KWICArchiveService` pattern: validate the source ticket, create an archive ticket, serialize the cached Feather artifact (CSV, JSONL, or Excel) in a `BackgroundTasks` job, and return `202 ArchivePrepareResponse` with `archive_ticket_id`, `retrieval_url`, and `expires_at`. The `retrieval_url` targets the existing tool-agnostic downloads router (`GET /v1/downloads/{id}`, `GET /v1/downloads/{id}/download`).
- **Download retrieval page** — the frontend route `/download/:archiveTicketId` already handles the four-state (pending / ready / failed / expired) retrieval page; no frontend changes are needed for the archive export path.

### New Service

Add `NGramsTicketService` to `api_swedeb/api/services/`, following `KWICTicketService` as the primary template:

- `estimate_hits(search, filter_opts) -> int | None` — DTM column sum reusing `WordTrendsService.estimate_hits()`; called by the estimate endpoint before any ticket is created
- `submit_query(query_params, result_store, background_tasks_or_celery) -> NGramsTicketAccepted`
- `get_status(ticket_id, result_store) -> NGramsTicketStatus` — includes `shards_complete`, `shards_total`, and `aggregate_version` during `PARTIAL`
- `get_page(ticket_id, page, page_size, sort_by, result_store) -> NGramsPage` — reads `current_aggregate.feather` during `PARTIAL` (the live running aggregate); reads `merged.feather` at `READY`

Add `NGramsArchiveService` for bulk archive, following `KWICArchiveService`.

Wire both in `api_swedeb/api/dependencies.py` and `AppContainer`.

### API Contract

Add the following endpoints alongside the existing `GET /v1/tools/ngrams/{search}`:

```
GET    /v1/tools/ngrams/estimate                  → {estimated_hits: int | null, in_vocabulary: bool}
POST   /v1/tools/ngrams/query                     → 202 NGramsTicketAccepted
GET    /v1/tools/ngrams/status/{ticket_id}        → NGramsTicketStatus
GET    /v1/tools/ngrams/page/{ticket_id}          → NGramsPage
POST   /v1/tools/ngrams/archive/{ticket_id}       → 202 ArchivePrepareResponse
```

The estimate endpoint accepts the same `search` parameter and shared `CommonParams` filters as the query endpoint. It delegates to `WordTrendsService.estimate_hits()` (DTM column sum, no CQP query) and mirrors the contract of `GET /v1/tools/kwic/estimate`. The frontend should debounce this call and show colour-coded guidance near the search button, consistent with the KWIC UX.

The submit request body mirrors the current `GET /v1/tools/ngrams/{search}` parameters (`search`, `width`, `target`, `mode`, plus shared `CommonParams` filters).

The `POST /v1/tools/ngrams/query` endpoint follows the same `ResultStorePendingLimitError → 429` pattern as `POST /v1/tools/kwic/query`.

All new static-path ngram routes (`/ngrams/estimate`, `/ngrams/query`, `/ngrams/status/{ticket_id}`, `/ngrams/page/{ticket_id}`, `/ngrams/archive/{ticket_id}`) must be registered in `tool_router.py` **before** the existing `GET /ngrams/{search}` route. FastAPI matches routes in declaration order, so a static prefix like `/ngrams/estimate` must appear first or it will be captured by the `{search}` path parameter.

### Progressive Loading Flow

The n-gram ticket flow mirrors the KWIC progressive shard model:

**Production mode** (`celery_enabled: true`):

1. `POST /v1/tools/ngrams/query` creates a ticket and enqueues `execute_ngrams_ticket` on the `multiprocessing` Celery queue
2. the Celery worker uses `Pool.imap_unordered()` over year-range shards; each shard completes keyword-window retrieval and aggregation for its year slice
3. as each shard completes, the worker merges it into the running aggregate (`current_aggregate.feather`) via `groupby ngram → sum window_count, union documents`, writes atomically (`.tmp` → rename), then increments `shards_complete` and `aggregate_version` in `TicketStateStore` (Redis); the ticket advances to `PARTIAL` on the first shard
4. clients poll the status endpoint; when `aggregate_version` advances, the client silently refreshes the current page — not page 1 — so the user continues browsing while results accumulate
5. after all shards are merged, the worker renames `current_aggregate.feather` to `merged.feather`, transitions to `READY`, and removes any intermediate files
6. the download endpoint block-polls until `READY` (controlled by `kwic.download_wait_timeout_s`), then streams `merged.feather`

**Development mode** (`celery_enabled: false`):

1–2. Same ticket creation. `BackgroundTasks` dispatches single-process execution.
3. Skips `PARTIAL`; the full aggregated result is written directly with `store_ready()`.

### Canonical Cached Payload

Shard files and the final `merged.feather` store the aggregated n-gram table, not raw keyword windows.

Recommended artifact columns:

1. `ngram`
2. `window_count`
3. `documents`
4. `_ticket_row_id`

`documents` can remain in the current compact backend representation inside the artifact. The page response converts it to the public API shape.

This approach:

1. matches the current backend aggregation boundary
2. supports exact-query page and sort reuse cleanly
3. avoids storing the much larger raw window payload
4. allows the frontend to display partial results and a progress bar during `PARTIAL`, consistent with the KWIC UX

### Supported Reuse Within One Ticket

Supported:

1. paging the exact-query result table
2. sorting the exact-query result table
3. export from the cached exact-query result, if a dedicated export contract is added

Not supported:

1. changing metadata filters inside the same ticket
2. recomputing counts for narrower subsets from the cached aggregate
3. deriving a new aggregate from the cached result without rerunning the query

Changing the search term or any metadata filter should create a new ticket.

### Sorting

For the MVP, allow only:

1. `sort_by=ngram`
2. `sort_by=count`

Always apply `_ticket_row_id` as the final tie-breaker so repeated paging is deterministic.

If `sort_by` is omitted, default to `_ticket_row_id` ascending.

### Export Behavior

N-gram export should use the `KWICArchiveService` pattern rather than client-side reconstruction:

1. `POST /v1/tools/ngrams/archive/{ticket_id}` validates the source ticket and returns `202 ArchivePrepareResponse` with a bearer `retrieval_url` targeting the existing downloads router.
2. Archive execution serializes the cached aggregated n-gram artifact to CSV, JSONL, or Excel in a `BackgroundTasks` job.
3. The frontend can render the `retrieval_url` immediately as a copyable link and optionally open the existing `/download/:archiveTicketId` retrieval page.
4. The existing synchronous export path (if any) remains on the deprecated endpoint until the ticketed path is validated.

The `POST /v1/tools/speeches/download` deprecation note in the original draft is not applicable here; that endpoint covers speech text retrieval, not n-gram export.

### Persistence and Lifecycle

Reuse the existing `ResultStore`, `TicketStateStore`, lifespan, cleanup, and byte-budget machinery without changes. N-gram tickets are logically separated from KWIC and speeches tickets by ticket type so cleanup, metrics, and validation remain clear.

### Client-Side Refresh Behaviour During PARTIAL

The frontend polls `GET /v1/tools/ngrams/status/{ticket_id}`. When `aggregate_version` advances the client refreshes the **current page** (not page 1) so the user continues browsing while aggregation is in progress. Two UX constraints apply:

- **Sort by ngram**: fully stable at all times — the alphabetical position of an n-gram cannot change as counts grow.
- **Sort by count**: approximate during `PARTIAL` — counts only increase, so a row can gain rank but not lose it. A banner or sort-column label should read "Approximate — updating" while `status === 'partial'`.

No UI change is needed until `aggregate_version` advances, so the polling interval can be relatively low (e.g. 2 s) without causing spurious re-renders.

## Risks And Tradeoffs

1. Caching the final aggregated table keeps the MVP simple, but it makes within-ticket re-filtering impossible.
2. `documents` can still be large for high-frequency n-grams, even after deduplication.
3. Export behavior will regress if it is not handled explicitly during frontend migration.
4. The running-aggregate model writes at most two files per ticket (`current_aggregate.feather` and `merged.feather`), so temporary disk overhead is minimal — substantially lower than the KWIC model's N shard files.
5. The DTM-based estimate counts keyword occurrences, not unique n-gram combinations; for wide n-gram widths the estimate will be a looser upper bound than for KWIC.

## Design Decisions Resolved

**1. Running-aggregate model replaces the KWIC shard-file model** ✓

`ResultStore.store_shards_ready()` merges shards with a plain `pd.concat()`. That is correct for KWIC, where each shard row is independent, but wrong for n-grams: the same n-gram (e.g. "social demokrati") may appear in multiple year-range shards and must be summed, not duplicated.

The n-gram shard model therefore diverges from the KWIC model. Instead of accumulating N independent shard files and merging at the end, the Celery worker maintains a single **running aggregate** per ticket:

1. When each year-range shard completes, the worker reads `current_aggregate.feather` (if it exists), merges the new shard into it via `groupby ngram → sum window_count, union documents`, and atomically replaces the file (write to `current_aggregate.feather.tmp`, rename).
2. After the merge, the worker increments `shards_complete` in `TicketStateStore` and increments `aggregate_version` (a monotonically increasing integer stored alongside the ticket state).
3. The ticket remains in `PARTIAL` status until all shards are processed, then the worker renames `current_aggregate.feather` to `merged.feather` and transitions to `READY`.

The `get_page` endpoint reads `current_aggregate.feather` during `PARTIAL` and `merged.feather` at `READY`. The `load_artifact` path in `ResultStore` must be extended to handle this single-file layout; the multi-shard-file glob and concat logic used for KWIC is not needed here.

This model is cheaper at read time than the KWIC approach (no per-request glob + concat of N shard files) and produces a correctly aggregated result at every snapshot. It requires a new `aggregate_version` counter in `TicketStateStore` and atomic file replacement in the worker — both are straightforward extensions of existing patterns.

## Required Implementation Tasks

The following gaps exist between the current codebase and what this CR requires. They must be addressed in roughly the order listed.

**1. Implement the n-gram multiprocess worker with running-aggregate merge**

There is no `execute_ngrams_multiprocess()` or n-gram worker function. The worker must:

- replicate the isolated `CorpusCreateOpts` + temporary work-directory pattern from `kwic_worker` to avoid GDBM file-locking conflicts
- call `query_keyword_windows()` plus `compile_n_grams()` per year-range shard
- after each shard completes, read `current_aggregate.feather` (if it exists), merge via `groupby ngram → sum window_count, union documents`, and atomically replace the file
- increment `shards_complete` and `aggregate_version` in `TicketStateStore` after each merge

`api_swedeb/core/kwic/multiprocess.py` and `kwic_worker` are the primary implementation template.

**2. Verify `inject_year_filter()` in the n-gram code path**

`inject_year_filter()` from `api_swedeb/core/kwic/utility.py` is used by the KWIC worker to narrow each shard's CQP query. The opts format is compatible (same `mappers.query_params_to_CQP_opts()` output), but `inject_year_filter` has not been tested or exercised through `query_keyword_windows()`. Verify the round-trip before building the shard orchestrator.

**3. Fix `NGramsService` to use `Depends()` injection**

`GET /v1/tools/ngrams/{search}` in `tool_router.py` constructs `NGramsService()` directly instead of using `Depends(get_ngrams_service)`. Move the existing synchronous endpoint to the dependency-injected pattern before adding `NGramsTicketService` alongside it, so that both code paths share the same app-scoped corpus instance.

**4. Define estimate semantics for multi-token searches**

`WordTrendsService.estimate_hits(word, ...)` takes a single word token. N-gram queries take a phrase (e.g. `"social demokrati"` composed of two tokens). Decide which token to use as the proxy (most likely the pivot or first keyword) and document in the response that the estimate is a loose upper bound, especially for multi-token inputs and wide `width` values.



## Testing And Validation

The n-gram ticket flow should not be considered complete until all of the following pass:

1. concatenating all ticketed pages in default order reproduces the same mapped n-gram rows as the current synchronous endpoint for the same exact query
2. repeated requests for the same ticket and sort settings return stable totals and stable row order
3. `PARTIAL` status returns `shards_complete`, `shards_total`, and `aggregate_version`; `get_page` reads `current_aggregate.feather` and returns correctly aggregated rows (no duplicate n-grams, summed counts)
4. `aggregate_version` increments exactly once per completed shard; at `READY`, `merged.feather` matches the final running aggregate and `current_aggregate.feather` is removed
5. expiry and cleanup behave the same way as the KWIC ticket flow
6. the archive export reproduces the same rows as the paged result for the same ticket
7. the `ResultStorePendingLimitError → 429` guard triggers correctly under concurrent submissions
8. the estimate endpoint returns a non-null value for in-vocabulary words and `in_vocabulary: false` for unknown terms

Test fixtures should follow the pattern in `tests/api_swedeb/api/` with mocked services; use the existing `configure_config_store` fixture for integration tests.

## Acceptance Criteria

1. the existing `GET /v1/tools/ngrams/{search}` endpoint remains unchanged
2. the ticketed n-gram flow is additive
3. the cached payload is explicitly defined as the final aggregated table
4. the proposal does not claim support for within-ticket re-filtering or recomputation
5. export behavior is explicitly defined before frontend migration begins

## Phased Delivery

Each phase ships independently and provides user value without requiring the next phase to be complete.

### Phase 1 — Estimate endpoint (prerequisite cleanup included)

Delivers: debounce + colour-coded hit guidance in the frontend before any ticket machinery exists.

1. Fix `NGramsService` to use `Depends(get_ngrams_service)` in `tool_router.py` (Implementation Task 3 — trivial, done in this PR).
2. Add `GET /v1/tools/ngrams/estimate` delegating to `WordTrendsService.estimate_hits()`; wire frontend debounce and colour-coded guidance consistent with the KWIC UX.
3. Resolve estimate semantics for multi-token searches (Implementation Task 4); document the proxy-token choice in the response.

The existing synchronous endpoint is unchanged. No ticket state, no `ResultStore` changes.

#### Phase 1 checklist — backend

- [ ] **`tool_router.py` line 650**: replace `service = NGramsService()` with `Depends(get_ngrams_service)`; add the dependency parameter to `get_ngram_results`
- [ ] **`api_swedeb/schemas/ngrams_schema.py`**: add `NGramsEstimateResult(in_vocabulary: bool, estimated_hits: int | None)`
- [ ] **`tool_router.py`**: register `GET /ngrams/estimate` **before** the existing `GET /ngrams/{search}` route, following the `GET /kwic/estimate` pattern; delegate to `word_trends_service.estimate_hits()` with a single proxy token (pivot word or first token); return `NGramsEstimateResult`
- [ ] **`api_swedeb/api/dependencies.py`**: verify `get_ngrams_service` is already wired; no change expected
- [ ] Decide and document proxy-token rule for multi-token searches (e.g. first whitespace-split token); add a comment to the endpoint docstring

#### Phase 1 checklist — frontend

- [ ] **`src/stores/nGramDataStore.js`**: add `estimatedHits: null`, `inVocabulary: null`, `estimateRequestSequence: 0` to state; add `fetchEstimate(search)` action mirroring `kwicDataStore.fetchEstimate()`, calling `GET /tools/ngrams/estimate`
- [ ] **`src/stores/nGramDataStore.js`**: debounce the `fetchEstimate` call on search-input change (reuse the same debounce pattern as KWIC, ~400 ms)
- [ ] **`src/components/toolsFilterData/`**: add `ngramEstimate.vue` component modelled on `kwicEstimate.vue`; bind to `nGramDataStore.estimatedHits` and `inVocabulary`
- [ ] **`src/components/toolsFilters.vue`**: mount `<ngramEstimate />` for the ngrams tool, following how `<kwicEstimate />` is conditionally rendered
- [ ] **`src/i18n/sv/index.js`** and **`src/i18n/en-US/index.js`**: add `ngramEstimateHitsPrefix`, `ngramEstimateHits`, `ngramEstimateNotInVocabulary`, `ngramEstimateHighWarning` keys (can reuse same wording as KWIC keys; separate keys allow future divergence)
- [ ] Manual test: type a known word, verify green/orange/grey banner appears; type an unknown word, verify "not in vocabulary" banner
- [ ] **Phase review**: assess whether the Phase 2 checklist needs updating based on findings from Phase 1 (e.g. proxy-token decision, unexpected `Depends()` coupling, or i18n key naming); update the document before starting Phase 2

### Phase 2 — Single-process ticketed path (frontend migration)

Delivers: the frontend migrates to the ticket flow; paged results and export work end-to-end without multiprocessing.

1. Add `NGramsTicketService` backed by `BackgroundTasks` (single-process, dev mode): skip `PARTIAL`, write directly to `merged.feather` via `store_ready()`, transition immediately to `READY`.
2. Add the three ticket endpoints: `POST /v1/tools/ngrams/query`, `GET /v1/tools/ngrams/status/{ticket_id}`, `GET /v1/tools/ngrams/page/{ticket_id}`; wire in `dependencies.py` and `AppContainer`.
3. Add `POST /v1/tools/ngrams/archive/{ticket_id}` and `NGramsArchiveService`; validate export output against the synchronous baseline.
4. Migrate the frontend to the ticket flow; validate paging, sorting, and export.
5. Move `GET /v1/tools/ngrams/{search}` to `deprecated_endpoints.py` once the ticketed path is confirmed stable.

No `aggregate_version`, no `current_aggregate.feather`, no multiprocessing changes needed in this phase.

#### Phase 2 checklist — schemas

- [ ] **`api_swedeb/schemas/ngrams_schema.py`**: add
  - `NGramsQueryRequest(search, width, target, mode, from_year, to_year, party_id, who, gender_id, chamber_abbrev)`
  - `NGramsTicketAccepted(ticket_id, expires_at)`
  - `NGramsTicketStatus(ticket_id, status, shards_complete, shards_total, aggregate_version, total_hits, error)`
  - `NGramsPageItem(ngram, count, documents)` (mirrors current `NGramResultItem`)
  - `NGramsPage(ticket_id, status, page, page_size, total_hits, items: list[NGramsPageItem])`
- [ ] **`api_swedeb/schemas/__init__.py`**: export new schema classes

#### Phase 2 checklist — service

- [ ] **`api_swedeb/api/services/ngrams_ticket_service.py`** (new file, template: `kwic_ticket_service.py`):
  - `submit_query(request, result_store) -> NGramsTicketAccepted`: create ticket via `result_store.create_ticket(ticket_type="ngrams", ...)`, raise `ResultStorePendingLimitError → 429` on capacity breach
  - `get_status(ticket_id, result_store) -> NGramsTicketStatus`
  - `get_page_result(ticket_id, result_store, page, page_size, sort_by, sort_order) -> NGramsPage | NGramsTicketStatus`: load `merged.feather`, apply sort, slice page, map rows to `NGramsPageItem`
  - `execute_ticket(ticket_id, request, ngrams_service, result_store)`: run `ngrams_service` synchronously, write result via `result_store.store_ready(ticket_id, df)`, transition to `READY`; no `PARTIAL` in this phase
- [ ] **`api_swedeb/api/services/__init__.py`**: export `NGramsTicketService`

#### Phase 2 checklist — wiring

- [ ] **`api_swedeb/api/container.py`**: add `ngrams_ticket_service: NGramsTicketService` field; initialise in `_create_default()`
- [ ] **`api_swedeb/api/dependencies.py`**: add `get_ngrams_ticket_service(container) -> NGramsTicketService`

#### Phase 2 checklist — router

- [ ] **`tool_router.py`**: register all new static-path routes **before** `GET /ngrams/{search}`:
  - `GET /ngrams/estimate` (already done in Phase 1)
  - `POST /ngrams/query → 202 NGramsTicketAccepted`
  - `GET /ngrams/status/{ticket_id} → NGramsTicketStatus`
  - `GET /ngrams/page/{ticket_id} → NGramsPage | NGramsTicketStatus`
  - `POST /ngrams/archive/{ticket_id} → 202 ArchivePrepareResponse`
- [ ] `POST /ngrams/query`: follow the `submit_kwic_query` pattern; dispatch via `background_tasks.add_task(ngrams_ticket_service.execute_ticket, ...)` only (no Celery branch yet)
- [ ] `GET /ngrams/status/{ticket_id}`: follow `get_kwic_ticket_status`; set `Retry-After` header on `PENDING`
- [ ] `GET /ngrams/page/{ticket_id}`: follow `get_kwic_ticket_results`; return `JSONResponse(202)` on `PENDING`, `JSONResponse(409)` on `ERROR`

#### Phase 2 checklist — archive

- [ ] **`api_swedeb/api/services/ngrams_archive_service.py`** (new file, template: `kwic_archive_service.py`): `prepare()`, `execute_archive_task()` serialising `merged.feather` to CSV / JSONL / Excel via `BackgroundTasks`
- [ ] Wire `NGramsArchiveService` in `container.py` and `dependencies.py`
- [ ] `POST /ngrams/archive/{ticket_id}` in router: validate source ticket is `READY`, return `202 ArchivePrepareResponse` with `retrieval_url` pointing to `/v1/downloads/{archive_ticket_id}`

#### Phase 2 checklist — deprecation

- [ ] Move `GET /v1/tools/ngrams/{search}` handler to **`api_swedeb/api/v1/endpoints/deprecated_endpoints.py`** once ticketed path passes validation; keep it registered but add deprecation header or OpenAPI `deprecated=True`

#### Phase 2 checklist — frontend

- [ ] **`src/stores/nGramDataStore.js`**: add ticket-flow state (`ticketId`, `ticketStatus`, `page`, `pageSize`, `sortBy`, `sortOrder`, `totalHits`, `requestSequence`); replace `getNGramsResult` with `submitQuery()` → `POST /tools/ngrams/query`; add `pollStatus()` → `GET /tools/ngrams/status/{ticket_id}`; add `fetchPage(page, pageSize, sortBy, sortOrder)` → `GET /tools/ngrams/page/{ticket_id}`
- [ ] **`src/stores/nGramDataStore.js`**: replace client-side sort (`nGrams.sort(...)`) with server-side `sort_by` / `sort_order` query params on `fetchPage`
- [ ] **`src/stores/nGramDataStore.js`**: replace `downloadNGramTableCSV` / `downloadNGramTableExcel` with `POST /tools/ngrams/archive/{ticket_id}` + navigate to `/download/:archiveTicketId`
- [ ] **`src/pages/` or relevant component**: add pagination controls bound to `nGramDataStore.page` and `totalHits`
- [ ] Manual test: submit a query, verify `READY` transition, page through results, download archive, confirm CSV matches paged data

#### Phase 2 checklist — tests (backend)

- [ ] `tests/api_swedeb/api/test_ngrams_ticket.py` (new): mock `NGramsTicketService`; test `submit → status → page` happy path; test `429` on capacity breach; test `404` on unknown ticket; test `202` on `PENDING` page request
- [ ] Integration test: real corpus, submit query, assert `merged.feather` matches synchronous endpoint output for same params
- [ ] Archive test: assert CSV rows match paged rows for same ticket
- [ ] **Phase review**: assess whether the Phase 3 checklist needs updating based on findings from Phase 2 (e.g. `ResultStore` extension scope, `TicketStateStore` counter design, shard-size heuristics, or frontend polling behaviour); update the document before starting Phase 3

### Phase 3 — Progressive PARTIAL with multiprocessing

Delivers: fast first results and live progress updates for large queries; client-side refresh behaviour activates automatically.

1. Implement `execute_ngrams_multiprocess()` and the n-gram worker with running-aggregate merge (Implementation Task 1): `query_keyword_windows()` + `compile_n_grams()` per shard, atomic `current_aggregate.feather` replacement, `shards_complete` + `aggregate_version` increments in `TicketStateStore`.
2. Verify `inject_year_filter()` round-trips correctly through the n-gram code path (Implementation Task 2).
3. Extend `ResultStore.load_artifact()` to read `current_aggregate.feather` during `PARTIAL`.
4. Switch `NGramsTicketService` to dispatch to the `multiprocessing` Celery queue in production mode.
5. Validate `PARTIAL` → `READY` flow: `aggregate_version` increments, no duplicate n-grams, stable sort-by-ngram, approximate sort-by-count with frontend label.

#### Phase 3 checklist — n-gram worker

- [ ] **`api_swedeb/core/ngrams/`** (new module or extend existing): add `ngrams_worker(shard_args) -> pd.DataFrame` function following `kwic_worker` in `api_swedeb/core/kwic/multiprocess.py`; use isolated `CorpusCreateOpts` + temporary work directory to avoid GDBM file-locking conflicts; call `inject_year_filter()` then `query_keyword_windows()` then `compile_n_grams()`
- [ ] **verify `inject_year_filter()`**: write a focused unit test that calls `inject_year_filter()` with representative opts and confirms the CQP string round-trips correctly through `query_keyword_windows()`; fix any incompatibility before building the orchestrator
- [ ] **`execute_ngrams_multiprocess(ticket_id, request, ngrams_service, result_store)`**: partition year range into shards (same logic as KWIC); use `Pool.imap_unordered()` with `ngrams_worker`; after each shard:
  - read `current_aggregate.feather` (if exists), merge via `df.groupby("ngram").agg({"window_count": "sum", "documents": union_set})`, write atomically to `current_aggregate.feather.tmp` then rename
  - call `result_store.advance_partial(ticket_id)` (or equivalent) to increment `shards_complete`
  - increment `aggregate_version` in `TicketStateStore`
  - transition ticket to `PARTIAL` on first shard if still `PENDING`
- [ ] After all shards: rename `current_aggregate.feather` → `merged.feather`, transition to `READY`, remove `.tmp` if present

#### Phase 3 checklist — ResultStore

- [ ] **`api_swedeb/api/services/result_store.py`**: extend `load_artifact()` to detect `current_aggregate.feather` when ticket is `PARTIAL` and return it; the existing shard-file glob/concat path is not used for n-gram tickets
- [ ] Add `aggregate_version` field to `TicketMeta` (or store it as a side-channel in `TicketStateStore`); increment atomically after each shard merge
- [ ] Ensure cleanup removes `current_aggregate.feather` and `merged.feather` on ticket expiry

#### Phase 3 checklist — TicketStateStore / schemas

- [ ] **`api_swedeb/schemas/ngrams_schema.py`**: confirm `NGramsTicketStatus.aggregate_version` field is present (added in Phase 2 schema definition); no schema change needed if already included
- [ ] **`TicketStateStore`**: add `increment_aggregate_version(ticket_id) -> int` method; store as `{ticket_id}:aggregate_version` key in Redis alongside existing counters

#### Phase 3 checklist — celery dispatch

- [ ] **`api_swedeb/celery_tasks.py`**: register `execute_ngrams_ticket` Celery task wrapping `execute_ngrams_multiprocess()`, following the pattern of `execute_kwic_ticket`
- [ ] **`tool_router.py` `POST /ngrams/query`**: add Celery branch (guarded by `celery_enabled`) sending `execute_ngrams_ticket` to the `multiprocessing` queue via `celery_app.send_task()`; keep `BackgroundTasks` branch for dev mode
- [ ] **`_get_worker_ngrams_service()`**: add `@lru_cache(maxsize=1)` worker-singleton helper in `ngrams_ticket_service.py` (or a dedicated worker module) mirroring `_get_worker_kwic_service()`

#### Phase 3 checklist — frontend

- [ ] **`src/stores/nGramDataStore.js`**: update `pollStatus()` to track `aggregate_version`; when version advances, call `fetchPage(currentPage, ...)` silently (no spinner, no scroll reset)
- [ ] **result table or sort column**: show "Approximate — updating" label on the count column while `ticketStatus === 'partial'`; remove label at `READY`
- [ ] Manual test with a wide year range: verify first page appears before all shards complete, count column updates in place, "Approximate" label disappears at `READY`

#### Phase 3 checklist — tests

- [ ] Unit test `ngrams_worker`: mock `query_keyword_windows` and `compile_n_grams`; assert shard output is a correctly aggregated DataFrame
- [ ] Unit test running-aggregate merge: two shards with overlapping n-grams; assert output has summed `window_count` and unioned `documents`, no duplicates
- [ ] Integration test `PARTIAL` → `READY`: submit a wide-year query with Celery disabled; inject a two-shard mock; assert `aggregate_version` increments and `current_aggregate.feather` becomes `merged.feather`
- [ ] Integration test concurrent submissions: assert `ResultStorePendingLimitError → 429` fires before the n-gram worker starts
- [ ] **Phase review**: confirm all three phases are complete and no deferred items remain open; update `Status` in the document header and record any residual technical debt in `docs/DESIGN.md` or `TODO.md`

## Final Recommendation

Implement n-gram paging aligned with the KWIC flow: `Pool.imap_unordered()` over year-range shards, `PARTIAL` status with shard progress counters, `merged.feather` at `READY`, pre-search DTM estimate, and `NGramsArchiveService` for bulk export via the existing downloads router.

For the MVP, cache the final aggregated n-gram table for exact-query reuse, support page and sort only, and treat any filter change or recomputation need as a new ticket.