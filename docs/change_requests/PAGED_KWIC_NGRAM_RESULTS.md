# Change Request: Paged KWIC Results via Server-Side Result Cache

**Status**: Revised proposal with accepted implementation decisions  
**Primary area**: `api_swedeb/api/v1/endpoints/tool_router.py`, `KWICService`, download flow  
**Follow-up area**: n-gram paging requires a separate payload decision before implementation  
**Affects**: API, frontend (`kwicDataStore.js`, `kwicDataTable.vue`), download flow

---

## 1. Current Architecture

### Request/Response Flow

KWIC and n-gram searches currently follow the same broad request shape:

```text
Client → GET /v1/tools/kwic/{search}?<all-filters>&cut_off=100000
       ← 200 OK { "kwic_list": [ ...up to 100k items... ] }
```

1. The client issues a single synchronous GET with all query filters.
2. `KWICService.get_kwic()` runs the corpus query, materializes the full result as a Pandas DataFrame, and the mapper serializes the entire list to JSON.
3. The frontend stores the full list in Pinia state and applies client-side paging.
4. The user sees nothing until the full response arrives.

For n-grams, the backend also returns the entire response in one call, but the payload is already a reduced aggregation: raw keyword windows are collapsed into `ngram`, `window_count`, and a deduplicated `documents` list before the API response is built.

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
3. Applying the exact same cache payload design to n-grams.

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
    error: str | None = None
```

Suggested storage model:

1. `TTLCache` or a plain dict + eviction logic for `TicketMeta` only.
2. Serialized result artifact per ticket in a temp cache directory, preferably **Feather v2 / Arrow IPC** for the MVP.
3. Explicit cleanup of expired tickets and a global `max_artifact_bytes` budget.

This removes long-lived full-result RAM retention while preserving page reuse.

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

## 5. N-Gram Follow-Up

The original proposal treated n-grams as if they could use the same cache semantics as KWIC. That is too loose.

### Why It Differs

The current n-gram pipeline already reduces raw keyword windows into a grouped table:

1. Raw windows are queried from the corpus.
2. Windows are transformed into n-grams.
3. Counts are aggregated into `window_count`.
4. Document IDs are deduplicated into a flattened `documents` field.

After that reduction, the final API payload is suitable for:

1. Paging the existing table.
2. Sorting the existing table.

It is **not** sufficient for:

1. Re-filtering by metadata inside the cached result.
2. Recomputing counts for a narrower year or party subset.
3. Deriving new aggregations without returning to underlying windows or segments.

### Recommendation

Keep n-grams out of the KWIC MVP and make it a follow-up design decision:

1. **Simple option**: cache only the final aggregated n-gram table, which supports page/sort reuse for one exact query.
2. **Richer option**: cache pre-aggregation window or segment data so the server can re-aggregate later, at materially higher storage cost.

Until that choice is made, this change request should not claim that KWIC and n-grams share the same cache payload strategy.

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
4. Download by `ticket_id` returns the same speech ID set as the equivalent existing download path and produces the expected manifest metadata.
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
| **Phase 4** | Design n-gram paging separately, choosing between final-table caching and pre-aggregation caching.                                               |
| **Phase 5** | If multi-worker deployment becomes necessary, replace local-only ticket storage with shared metadata and shared result storage.                  |
