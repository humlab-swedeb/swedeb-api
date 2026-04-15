# Change Request: Paged KWIC Results via Server-Side Result Cache

**Status**: Revised proposal with accepted implementation decisions and assessment responses  
**Primary area**: `api_swedeb/api/v1/endpoints/tool_router.py`, `KWICService`, download flow  
**Follow-up area**: n-gram paging is covered separately in `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`  
**Affects**: API, frontend (`kwicDataStore.js`, `kwicDataTable.vue`), download flow

---

## 1. Current Architecture

### Request/Response Flow

KWIC searches currently follow this broad request shape:

```text
Client → GET /v1/tools/kwic/{search}?<all-filters>&cut_off=100000
       ← 200 OK { "kwic_list": [ ...up to 100k items... ] }
```

1. The client issues a single synchronous GET with all query filters.
2. `KWICService.get_kwic()` runs the corpus query, materializes the full result as a Pandas DataFrame, and the mapper serializes the entire list to JSON.
3. The frontend stores the full list in Pinia state and applies client-side paging.
4. The user sees nothing until the full response arrives.

### Performance Implications

| Concern                     | Detail                                                                               |
|-----------------------------|--------------------------------------------------------------------------------------|
| **Large payloads**          | A `cut_off=100000` KWIC result can serialize to tens or hundreds of MB of JSON.      |
| **Blocking request path**   | The current endpoint does all corpus work before responding.                         |
| **No incremental feedback** | The browser shows nothing until the corpus scan and JSON serialization are complete. |
| **Repeated full fetches**   | Page or sort changes still require the client to hold the full list locally.         |
| **Server peak memory**      | The full KWIC hit set is already materialized in memory during query execution.      |
| **Client memory**           | The browser keeps the entire list in reactive state.                                 |

---

## 2. Revised Scope

This proposal should be narrowed to a **KWIC-first MVP**.

### In Scope

1. Submit a KWIC query and receive a ticket immediately.
2. Poll ticket readiness.
3. Fetch paged KWIC results from the completed cached artifact.
4. Reuse the same ticket for paging, sorting, and speech download.

### Out of Scope for This MVP

1. Re-filtering a cached result with new year/party/gender constraints.
2. Returning `total_hits` in the initial submit response.
3. N-gram paging; see `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`.

Changing the search term or any metadata filter still creates a **new** ticket. The cache is for reuse of one completed query result, not for incremental recomputation of new filtered subsets.

### Coexistence with Existing Endpoints

Yes. The paging and caching infrastructure should be added **in parallel** with the existing synchronous endpoints.

For the MVP:

1. Keep `GET /v1/tools/kwic/{search}` unchanged.
2. Add the ticketed endpoints alongside it.
3. Let the frontend opt into the new flow explicitly instead of silently changing current clients.

This keeps rollout risk low, preserves backward compatibility, and gives us a clean fallback if the ticketed path exposes operational issues under real workloads.

---

## 3. Revised API Contract

The design uses one clear asynchronous contract: **submit immediately, then poll or request results until ready**.

### Phase 1 — Submit query

```http
POST /v1/tools/kwic/query
Content-Type: application/json

{
  "search": "demokrati",
  "lemmatized": true,
  "words_before": 5,
  "words_after": 5,
  "cut_off": 200000,
  "filters": {
    "from_year": 1970,
    "to_year": 2000,
    "who": null,
    "party_id": [3],
    "gender_id": null,
    "chamber_abbrev": null,
    "speech_id": null
  }
}
```

```http
202 Accepted
{
  "ticket_id": "3f2a1b4c-...",
  "status": "pending",
  "expires_at": "2026-04-15T14:35:00Z"
}
```

The server creates a ticket immediately, schedules the KWIC job, and returns without waiting for the full corpus scan.

The submit body should be represented by dedicated request models such as `KWICQueryRequest` and `KWICFilterRequest`. Filter field names should match the existing filter vocabulary exactly, and filter normalization should be shared with the current GET-based flow through a pure helper rather than through direct reuse of FastAPI `Query(...)` objects.

### Phase 2 — Poll status

```http
GET /v1/tools/kwic/status/{ticket_id}
```

```http
200 OK
{
  "ticket_id": "3f2a1b4c-...",
  "status": "ready",
  "total_hits": 4832,
  "expires_at": "2026-04-15T14:35:00Z"
}
```

Possible states:

| Status    | Meaning                                               |
|-----------|-------------------------------------------------------|
| `pending` | Query accepted and still running                      |
| `ready`   | Result artifact is available for paging/download      |
| `error`   | Query failed; ticket stores a user-safe error message |

### Phase 3 — Fetch a page

```http
GET /v1/tools/kwic/results/{ticket_id}?page=1&page_size=50&sort_by=year&sort_order=asc
```

```http
200 OK
{
  "ticket_id": "3f2a1b4c-...",
  "status": "ready",
  "page": 1,
  "page_size": 50,
  "total_hits": 4832,
  "total_pages": 97,
  "expires_at": "2026-04-15T14:35:00Z",
  "kwic_list": [ ... 50 items ... ]
}
```

If the client requests results before the job is ready:

```http
202 Accepted
{
  "ticket_id": "3f2a1b4c-...",
  "status": "pending",
  "expires_at": "2026-04-15T14:35:00Z"
}
```

### Phase 4 — Download speeches from the same ticket

```http
POST /v1/tools/speeches/download?ticket_id=3f2a1b4c-...
```

The download endpoint reuses the cached speech IDs and the cached normalized query metadata. It does not reconstruct the manifest from the current request query string alone.

For the MVP, frontend CSV/XLSX export should remain on the existing synchronous flow. The ticketed KWIC path should not take over export until a dedicated export endpoint or equivalent server-side export contract exists.

---

## 4. Implementation Approach

### 4.1 Cache Design: Keep Metadata in Memory, Store Results as Artifacts

The earlier in-process `TTLCache` example should **not** store full KWIC DataFrames directly. That keeps the worst-case RAM cost alive after the query finishes and makes OOMs more likely.

Instead:

1. Keep a small in-memory ticket registry for ticket state and metadata only.
2. Write the completed KWIC result to a short-lived artifact on local disk.
3. Enforce a **byte budget**, not just an entry count.

Recommended shape:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class TicketMeta:
    ticket_id: str
    status: Literal["pending", "ready", "error"]
    created_at: datetime
    expires_at: datetime
    artifact_path: str | None
    artifact_bytes: int | None
    total_hits: int | None
    query_meta: dict
    speech_ids: list[str] | None
    manifest_meta: dict | None
    error: str | None = None
```

Suggested storage model:

1. `TTLCache` or a plain dict + eviction logic for `TicketMeta` only.
2. Serialized result artifact per ticket in a temp cache directory, preferably **Feather v2 / Arrow IPC** for the MVP.
3. Explicit cleanup of expired tickets and a global `max_artifact_bytes` budget.

This removes long-lived full-result RAM retention while preserving page reuse.

Canonical artifact contract:

1. The cached artifact should be the mapped KWIC API frame, not the raw `KWICService.get_kwic()` DataFrame.
2. The artifact should be produced by `kwic_to_api_frame(...)` and persisted with one additional hidden `_ticket_row_id` column.
3. The canonical artifact columns are `KWIC_API_COLUMNS` plus `_ticket_row_id`.
4. This keeps sort fields such as `speech_name` valid and makes parity with the synchronous mapped endpoint directly testable.
5. `document_name` remains in the artifact because the current frontend export path still depends on it.

How expired disk artifacts should be removed:

1. **Delete on normal access paths**: every `status`, `results`, `download`, and new `query` request should first run a cheap `cleanup_expired()` pass that removes any ticket whose `expires_at` is in the past and deletes its artifact file before dropping the metadata entry.
2. **Run a periodic sweeper**: start a lightweight background cleanup loop that runs every `cache.cleanup_interval_seconds` and removes expired artifacts even if no new requests arrive.
3. **Clean up on startup**: keep all cache artifacts inside a dedicated cache root such as `/tmp/swedeb-kwic-cache/`, and remove stale files from previous process runs at application startup so crashes or restarts do not leave orphaned artifacts behind.
4. **Evict on byte budget**: when writing a new ready artifact, evict the oldest ready tickets until total on-disk artifact size is back under `cache.max_artifact_bytes`.
5. **Use atomic writes**: write to a temporary filename and rename into place only after the artifact is complete, so cleanup never has to reason about partially written files.
6. **Treat missing files as expired/corrupt**: if metadata exists but the artifact file is gone, delete the metadata entry and return the same not-found-or-expired response.

For the MVP, the safest model is to combine all three cleanup triggers:

1. lazy cleanup on request paths,
2. periodic background sweeping,
3. startup removal of stale cache directories.

That gives good behavior both during active traffic and during idle periods, and it handles process crashes without needing a more complex external garbage collector.

Recommended default:

1. Use **Feather v2 / Arrow IPC** as the on-disk cache format for local, short-lived KWIC result artifacts.
2. Use lightweight compression such as `lz4` by default, or `zstd` if artifact size becomes the tighter constraint.
3. Keep **Parquet** as a follow-up option only if disk footprint or cross-process / remote-storage interoperability becomes more important than read/write latency.

Why Feather is the better fit here:

1. It is already aligned with the repository's existing storage conventions and `pyarrow` is already installed.
2. It is optimized for fast local write/read of full DataFrame-shaped artifacts, which matches the ticket cache use case better than a warehouse-style analytical format.
3. The cache artifacts are short-lived and local, so lower serialization overhead matters more than maximum compression ratio.
4. Arrow-backed reads keep the implementation simple if we later want memory-mapped access or column projection.

Why not make Parquet the default:

1. Parquet is stronger when long-term storage efficiency is the main concern.
2. It usually adds more encode/decode overhead than Feather for short-lived temp artifacts.
3. The KWIC cache is a transient paging artifact, not a durable analytical dataset.

### 4.2 ResultStore Lifecycle and Execution Model

The ticket cache should be implemented as a dedicated `ResultStore` service.

Lifecycle decisions:

1. Initialize `ResultStore` once in a FastAPI lifespan hook.
2. Store the instance in `app.state.result_store`.
3. Expose it through a dependency such as `get_result_store(request)`.
4. On startup: create the cache root, remove stale artifacts, and start the cleanup sweeper.
5. On shutdown: cancel the sweeper and remove leftover partial-write files.
6. Use one canonical app factory with lifespan wiring, and make `main.py`, `docker/main.py`, and test app setup all use that same factory.

Concurrency decisions:

1. `ResultStore` is the sole owner of ticket state and byte-budget accounting.
2. Guard all ticket metadata mutation and budget accounting with a process-local lock.
3. Use explicit ticket states: `pending`, `ready`, `error`, and internal terminal cleanup states such as expired/deleted.
4. Count `cache.max_pending_jobs` as tickets currently accepted and still in `pending` state.
5. Artifact writes may happen outside the lock, but registration of a completed artifact must reacquire the lock before mutating state.

Execution decisions:

The async sketch should **not** wrap `KWICService.get_kwic()` inside a new outer `ProcessPoolExecutor`.

Current behavior already matters here:

1. `KWICService.get_kwic()` defaults to multiprocessing.
2. The KWIC multiprocess path creates a fresh `ccc.Corpus` per worker specifically to avoid CWB/GDBM conflicts.
3. Adding another process pool around that call risks pickling service state or double-spawning worker processes.

Safer approach:

1. Create the ticket immediately.
2. Schedule the job in the application process using a background task or threadpool offload.
3. Let `KWICService.get_kwic()` continue to control its own internal multiprocessing behavior.

Illustrative shape:

```python
from fastapi.concurrency import run_in_threadpool

async def execute_kwic_ticket(ticket_id: str, request: KWICQueryRequest, ...):
    try:
        df = await run_in_threadpool(
            kwic_service.get_kwic,
            corpus,
            commons,
            keywords,
            request.lemmatized,
            request.words_before,
            request.words_after,
            "word",
            request.cut_off,
        )
        result_store.store_ready(ticket_id, df=df, query_meta=normalized_query)
    except Exception as exc:
        result_store.store_error(ticket_id, message=str(exc))
```

The important point is the boundary: offload the blocking request work from the event loop, but do **not** introduce a second layer of process-based parallelism around the current KWIC engine.

### 4.3 Server-Side Paging

The page endpoint should operate on one completed cached result artifact.

Supported reuse within one ticket:

1. Paging.
2. Sorting by an allowed set of columns.
3. Speech download.

Not supported within one ticket:

1. Changing year, party, gender, chamber, or search term.
2. Recomputing the KWIC hit set with new corpus filters.

Paging decisions:

1. Allow `sort_by` only for `year`, `name`, `party_abbrev`, `gender`, `left_word`, `node_word`, `right_word`, and `speech_name`.
2. Add a hidden `_ticket_row_id` column at artifact creation time and always use it as the final tie-breaker.
3. Use `page_size=50` by default and `cache.max_page_size=200` for the MVP.
4. For the MVP, each page request may load the cached artifact and sort it in process.
5. If `sort_by` is omitted, default to `_ticket_row_id` ascending.
6. If the ticket is `pending`, `GET /results/{ticket_id}` returns `202 Accepted` with ticket status.
7. If the ticket is `error`, `GET /results/{ticket_id}` returns `409 Conflict` with ticket status and error message.
8. If the ticket is expired or unknown, `GET /results/{ticket_id}` returns `404 Not Found`.
9. Invalid `sort_by` values return `400 Bad Request`.
10. Requesting a page beyond `total_pages` returns `400 Bad Request` with a clear out-of-range message.

### 4.4 Download Manifest Requirements

If `ticket_id` is accepted by `/speeches/download`, the cached ticket must store enough metadata to rebuild the existing manifest correctly.

Download precedence decisions:

1. `ticket_id` is mutually exclusive with both body `ids` and query-based filters.
2. If `ticket_id` is combined with either of those inputs, return `400 Bad Request`.
3. If `ticket_id` is provided, resolve speech IDs and manifest metadata from the ticket only.
4. If body `ids` is provided and `ticket_id` is absent, keep current behavior.
5. If neither `ticket_id` nor `ids` is provided, keep the current query-filter behavior.
6. A pending ticket returns `409 Conflict`.
7. An expired or unknown ticket returns `404 Not Found`.
8. The ticket-specific download path should call a dedicated download service API that accepts `speech_ids` and `manifest_meta` directly instead of reconstructing everything from `CommonQueryParams`.
9. Speech ordering for ticket download is the first-occurrence order from the completed cached artifact, using `_ticket_row_id` order and deduplicating `speech_id` values while preserving order.
10. The checksum remains the SHA-256 of sorted unique `speech_id` values so it stays stable and comparable to the current manifest style.

That metadata should include:

1. The normalized filter options used to create the ticket.
2. The speech IDs associated with the cached result.
3. Query parameters relevant to the archive manifest, such as search term and time window.
4. `ticket_id`, `lemmatized`, `words_before`, `words_after`, `cut_off`, `total_hits`, `speech_count`, checksum, and generation timestamp.

Without that, the current manifest logic would lose context because it currently derives filter data from `commons.get_filter_opts(...)` on the active request.

### 4.5 Schema Sketch

```python
class KWICFilterRequest(BaseModel):
  from_year: int | None = None
  to_year: int | None = None
  who: list[str] | None = None
  party_id: list[int] | None = None
  gender_id: list[int] | None = None
  chamber_abbrev: list[str] | None = None
  speech_id: list[str] | None = None

class KWICQueryRequest(BaseModel):
  search: str
  lemmatized: bool = True
  words_before: int = 2
  words_after: int = 2
  cut_off: int = 200000
  filters: KWICFilterRequest = Field(default_factory=KWICFilterRequest)

class KWICTicketAccepted(BaseModel):
    ticket_id: str
    status: Literal["pending"]
    expires_at: datetime

class KWICTicketStatus(BaseModel):
    ticket_id: str
    status: Literal["pending", "ready", "error"]
    total_hits: int | None = None
    error: str | None = None
    expires_at: datetime

class KWICPageResult(BaseModel):
    ticket_id: str
    status: Literal["ready"]
    page: int
    page_size: int
    total_hits: int
    total_pages: int
    expires_at: datetime
    kwic_list: list[KeywordInContextItem]
```

---

## 5. Related Follow-Up Proposal

N-gram paging has been split into a separate follow-up proposal: `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`.

This KWIC proposal does not define the n-gram cache payload, export story, or API contract beyond deferring that work to the follow-up design.

---

## 6. Lifecycle, Resource Limits, and Deployment Notes

| Concern                      | Revised mitigation                                                                                                                                                 |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Ticket guessing**          | Use UUIDv4 ticket IDs.                                                                                                                                             |
| **TTL**                      | Default 10 minutes via `cache.result_ttl_seconds = 600`.                                                                                                           |
| **Cleanup interval**         | Run the sweeper every 60 seconds via `cache.cleanup_interval_seconds = 60`.                                                                                        |
| **Memory retention**         | Do not keep full DataFrames in memory after completion; retain metadata in memory and payload on disk.                                                             |
| **Cache budget**             | Enforce `cache.max_artifact_bytes = 2147483648` (2 GiB) on result artifacts rather than `maxsize=500` tickets.                                                   |
| **Pending-job pressure**     | Cap pending jobs with `cache.max_pending_jobs = 2`; on saturation return `429 Too Many Requests` with `Retry-After`.                                            |
| **Page size**                | Use `page_size=50` by default and enforce `cache.max_page_size = 200`.                                                                                             |
| **Cache root**               | Store artifacts under `cache.root_dir = /tmp/swedeb-kwic-cache`.                                                                                                   |
| **Expired ticket UX**        | Return `404 Ticket not found or expired`; frontend should prompt the user to search again.                                                                         |
| **Artifact write failure**   | Delete partial files, mark the ticket as `error`, and expose a user-safe error message through the status endpoint.                                                |
| **Byte-budget exhaustion**   | Evict expired artifacts first, then oldest ready artifacts; if a new artifact still cannot fit, mark the ticket as `error` using `507` semantics.                |
| **Single-worker assumption** | The MVP explicitly supports one worker and local writable cache storage only. Multi-worker portability requires shared storage and shared metadata.               |
| **Export behavior**          | Keep CSV/XLSX export on the synchronous KWIC flow for the MVP; add a dedicated export contract before moving export to the ticketed path.                         |

---

## 7. Accepted Implementation Decisions

The following decisions are accepted and define the MVP implementation.

### 7.1 Request Normalization

The proposal currently shows `POST /v1/tools/kwic/query` as a JSON-body request, while the existing filter model is query-parameter based.

1. Add a body model such as `KWICQueryRequest` with fields `search`, `lemmatized`, `words_before`, `words_after`, `cut_off`, and nested `filters`.
2. Add a nested `KWICFilterRequest` whose field names match the current filter vocabulary exactly: `from_year`, `to_year`, `who`, `party_id`, `gender_id`, `chamber_abbrev`, and `speech_id`.
3. Keep only query-defining inputs in the submit body. Keep `page`, `page_size`, `sort_by`, and `sort_order` on the results endpoint.
4. Extract filter normalization into a pure helper that both the current dependency-based GET flow and the new POST ticket flow can reuse. Do not make the JSON contract depend directly on the FastAPI `Query(...)` model class.

### 7.2 ResultStore Lifecycle

The proposal requires startup cleanup, a background sweeper, and request-path cleanup, but the application does not yet define a lifecycle hook for that infrastructure.

1. Implement a `ResultStore` class that owns ticket metadata, artifact paths, cleanup, and loading.
2. Initialize it once in a FastAPI lifespan hook and store it in `app.state.result_store`.
3. Expose it via a `get_result_store(request)` dependency rather than another unmanaged module-global singleton.
4. On startup: create the cache root, remove stale artifacts, and start the periodic sweeper task.
5. On shutdown: cancel the sweeper cleanly and remove any temporary partial-write files.

### 7.3 Paging and Sorting Contract

The page endpoint exposes `sort_by` and `sort_order`, but the allowed sort fields are not yet finalized and current sort naming is not fully aligned.

1. Allow `sort_by` only for a small explicit set: `year`, `name`, `party_abbrev`, `gender`, `left_word`, `node_word`, `right_word`, and `speech_name`.
2. Add a hidden `_ticket_row_id` column when the artifact is created and always use it as the final tie-breaker so repeated paging is deterministic.
3. Use `page_size=50` by default and `cache.max_page_size=200` for the MVP.
4. For the MVP, allow each page request to load the cached artifact and sort it in process. Optimize this only if benchmarks show it is necessary.

### 7.4 Download Endpoint Rules

The proposal says `/speeches/download` should accept `ticket_id`, but the endpoint already supports body `ids` and query-based filtering.

1. `ticket_id` is mutually exclusive with both body `ids` and query-based filters. If `ticket_id` is provided together with either, return `400 Bad Request`.
2. If `ticket_id` is provided, the endpoint must resolve speech IDs and manifest metadata from the cached ticket only.
3. If body `ids` is provided and `ticket_id` is absent, keep current behavior.
4. If neither `ticket_id` nor `ids` is provided, keep the current query-filter behavior.
5. A pending ticket returns `409 Conflict` with a clear `Ticket not ready` message.
6. An expired or unknown ticket returns `404 Not Found`.
7. The manifest rebuilt from a ticket should include at least: `ticket_id`, search term, `lemmatized`, `words_before`, `words_after`, `cut_off`, normalized filters, `total_hits`, `speech_count`, checksum, and generation timestamp.
8. “Query-based filters” means only user-supplied selection-bearing filters, not default pagination or sort fields. Detect conflicts with a helper that checks only filter fields that affect speech selection.

### 7.5 Operational Defaults

The proposal names several configuration keys, but it does not yet define starting values or failure behavior.

Use these starting defaults for the MVP:

1. `cache.result_ttl_seconds = 600`
2. `cache.cleanup_interval_seconds = 60`
3. `cache.max_artifact_bytes = 2147483648` (2 GiB)
4. `cache.max_pending_jobs = 2`
5. `cache.root_dir = /tmp/swedeb-kwic-cache`
6. `cache.max_page_size = 200`

Use these failure rules:

1. Queue saturation: reject new submit requests with `429 Too Many Requests` and a `Retry-After` header.
2. Byte-budget exhaustion: evict expired artifacts first, then oldest ready artifacts; if the new artifact still cannot fit, mark the ticket as `error` and surface `507 Insufficient Storage` semantics.
3. Artifact write failure: delete partial files immediately, mark the ticket as `error`, and expose a user-safe error message through the status endpoint.

### 7.6 Deployment Assumption

The MVP assumes local disk artifacts and effectively a single-worker-local-storage model.

1. Accept the single-worker, local-disk assumption for the MVP.
2. Document the ticket workflow as supported only when the API runs with one worker and a local writable cache directory.
3. If multi-worker portability becomes a near-term requirement, do not stretch the local-disk design. Move directly to shared metadata plus shared artifact storage.

### 7.7 Validation Plan

The migration path is defined, but the proposal does not yet specify what must pass before the ticketed path is considered safe.

Implementation should not be considered complete until all of the following pass:

1. For the same search, filters, and `cut_off`, concatenating all ticketed pages in default order produces the same KWIC rows as the current `GET /v1/tools/kwic/{search}` endpoint after the same mapper is applied.
2. Repeated requests for the same ticket, page, and sort settings return stable totals and stable row order.
3. Expired tickets are removed within one cleanup interval, and a restart test shows that stale artifacts from a previous process are removed on startup.
4. Download by `ticket_id` returns the deduplicated `speech_id` set derived from the completed cached KWIC artifact in first-occurrence `_ticket_row_id` order, and produces the expected manifest metadata.
5. Manual benchmark on a representative staging corpus shows:
  - initial query execution is not materially worse than the current synchronous endpoint for the same search,
  - cached page fetch stays under 500 ms at `page_size=50` for the common case,
  - total artifact usage stays within the configured byte budget after eviction.

---

## 8. Migration Path

The existing `GET /v1/tools/kwic/{search}` endpoint should remain unchanged for backward compatibility. The ticketed workflow is additive.

During rollout, both endpoint families should remain live:

1. Existing clients can continue using the synchronous endpoint.
2. New frontend code can opt into the ticket workflow behind a feature flag or explicit store-level switch.
3. Removal or deprecation of the old endpoint should be a separate decision after the new path has been validated in production.

| Phase       | Scope                                                                                                                                            |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| **Phase 1** | Add KWIC ticket registry, disk-backed result artifacts, `POST /kwic/query`, `GET /kwic/status/{ticket_id}`, and `GET /kwic/results/{ticket_id}`. |
| **Phase 2** | Update `kwicDataStore.js` and `kwicDataTable.vue` to submit, poll, then request pages in server-side pagination mode.                            |
| **Phase 3** | Update `/speeches/download` to accept `ticket_id` and build the manifest from cached query metadata plus speech IDs.                             |
| **Phase 4** | Implement the follow-up design in `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md` after the KWIC ticket flow is validated.                 |
| **Phase 5** | If multi-worker deployment becomes necessary, replace local-only ticket storage with shared metadata and shared result storage.                  |


# Assessment

Status at review time: Not implementation-ready.

1. The cached artifact contract is still internally inconsistent. The proposal stores the raw KWICService.get_kwic() DataFrame at PAGED_KWIC_RESULTS_DESIGN.md (line 289), but later requires sorting by speech_name at PAGED_KWIC_RESULTS_DESIGN.md (line 326) and parity with the mapped synchronous endpoint at PAGED_KWIC_RESULTS_DESIGN.md (line 530). speech_name, speech_link, and link are only added in api_swedeb/mappers/kwic.py (line 41). This needs one explicit decision: cache the mapped API frame, or cache raw KWIC plus precomputed derived columns, and define the canonical column set.

2. Download-by-ticket is not wired to the current service contract. The proposal requires ticket-only manifest rebuilding at PAGED_KWIC_RESULTS_DESIGN.md (line 333) and says ticket metadata must include speech IDs at PAGED_KWIC_RESULTS_DESIGN.md (line 345), but TicketMeta itself does not include them at PAGED_KWIC_RESULTS_DESIGN.md (line 199). The current DownloadService.create_stream() (line 209) only accepts CommonQueryParams and recomputes both speech selection and manifest from commons.get_filter_opts(True). The proposal needs an explicit download service API for speech_ids + manifest metadata, plus a defined speech ordering/checksum rule.

3. The app lifecycle insertion point is unresolved. The proposal depends on a FastAPI lifespan-managed ResultStore at PAGED_KWIC_RESULTS_DESIGN.md (line 262), but the active app in main.py (line 10) has no lifespan hook, the test app in tests/conftest.py (line 151) also has none, and there is a separate app assembly in docker/main.py (line 18). This needs a single canonical app factory/lifespan path before implementation starts.

4. The frontend migration omits current export behavior. The proposal says it affects kwicDataStore.js and kwicDataTable.vue at PAGED_KWIC_RESULTS_DESIGN.md (line 6) and phase 2 at PAGED_KWIC_RESULTS_DESIGN.md (line 554), but docs/DESIGN.md (line 294) documents that the frontend CSV/XLSX export path currently depends on holding the full KWIC result, including document_name, client-side. The proposal needs an explicit export story: keep export on the old synchronous flow, fetch all pages, or add a dedicated export endpoint.

5. Endpoint behavior is incomplete for non-happy paths. KWICTicketStatus includes error at PAGED_KWIC_RESULTS_DESIGN.md (line 379), but the page contract at PAGED_KWIC_RESULTS_DESIGN.md (line 386) only defines ready, and the prose only shows pending handling at PAGED_KWIC_RESULTS_DESIGN.md (line 159). It still needs explicit rules for results/{ticket_id} when the ticket is error, for out-of-range pages, and for invalid sort fields. It also needs a defined default order when sort_by is omitted, otherwise the parity requirement at line 530 is not testable.

6. The concurrency model for ResultStore is underspecified. The proposal allows a plain dict/TTL cache at PAGED_KWIC_RESULTS_DESIGN.md (line 214), request-path cleanup at line 222, a background sweeper at line 223, and background job completion via threadpool at line 281. That means multiple threads/tasks will mutate ticket state and byte-budget accounting concurrently. The design needs explicit locking/state-transition rules and a precise definition of what counts toward cache.max_pending_jobs.

7. The validation target for ticket-based download is ambiguous. The proposal says download-by-ticket should match “the equivalent existing download path” at PAGED_KWIC_RESULTS_DESIGN.md (line 533), but there is no current endpoint that downloads “the KWIC result set” as such. The proposal should define the baseline as deduplicated speech_id values derived from the completed KWIC result in a specified stable order.

8. ticket_id conflict handling needs a concrete detection rule. The proposal says ticket_id is mutually exclusive with query-based filters at PAGED_KWIC_RESULTS_DESIGN.md (line 489), but CommonQueryParams (line 50) always carries default sort_by and sort_order values. You need to specify whether “query-based filters” means only user-supplied filter params, or literally any populated query param object, otherwise the endpoint logic is ambiguous.

## Assessment Response

All eight assessment issues are valid.

1. Valid. Resolution: cache the mapped KWIC API frame produced by `kwic_to_api_frame(...)`, not the raw service frame. The canonical artifact columns are `KWIC_API_COLUMNS` plus `_ticket_row_id`.
2. Valid. Resolution: extend ticket metadata to include `speech_ids` and `manifest_meta`, and add a dedicated download service path that accepts `speech_ids` plus manifest data directly.
3. Valid. Resolution: introduce one canonical app factory with lifespan wiring and make runtime, Docker, and tests all construct the app through it.
4. Valid. Resolution: keep CSV/XLSX export on the existing synchronous KWIC path for the MVP. Do not migrate export to the ticketed path until a dedicated export contract exists.
5. Valid. Resolution: define non-happy-path behavior explicitly for `results/{ticket_id}`: `202` for pending, `409` for error, `404` for expired or unknown, `400` for invalid sort fields, and `400` for out-of-range pages. Default order is `_ticket_row_id` ascending.
6. Valid. Resolution: make `ResultStore` the single owner of ticket state behind a process-local lock, define explicit state transitions, and define `max_pending_jobs` as the number of accepted tickets still in `pending` state.
7. Valid. Resolution: define the ticket-download validation baseline as the deduplicated `speech_id` set derived from the completed cached KWIC artifact in stable `_ticket_row_id` order.
8. Valid. Resolution: define ticket conflict detection in terms of user-supplied selection-bearing filters only, ignoring default `sort_by`, `sort_order`, and other non-selection defaults.