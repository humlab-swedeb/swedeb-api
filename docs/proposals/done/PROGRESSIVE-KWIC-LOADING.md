# Progressive KWIC Loading

## Status

- ~~Proposed feature~~ **Implemented** (Phase 1 ✅, Phase 2 ✅, Phase 3 ✅)
- Scope: backend (result store, ticket service, multiprocess executor, new estimate endpoint) + frontend (KWIC store, table display)
- Goal: give users hit-count estimates before searching, apply threshold-based display limits transparently, and deliver KWIC results incrementally as corpus shards complete — removing the silent hard cut-off for both display and download

---

## Progress

### Phase 1 — Pre-search estimate

**Backend**
- [x] Add `KWICEstimateService` (or extend `KWICService`) with a DTM column-sum method that respects the same metadata filters as `WordTrendsService`
- [x] Add `GET /v1/tools/kwic/estimate` endpoint with query params matching the KWIC search form
- [x] Return `{ "estimated_hits": N, "in_vocabulary": true/false }` schema
- [ ] Add `kwic.estimate` section to `config/config.yml` and `tests/config.yml` if needed
- [x] Add unit test for the estimate method (mocked DTM) — `tests/api_swedeb/api/services/test_estimate_hits.py` (16 tests)
- [x] Add API test for the estimate endpoint — `tests/api_swedeb/api/endpoints/test_kwic_estimate_endpoint.py` (11 tests)

**Frontend**
- [x] Add `fetchEstimate(word, filters)` action to `kwicDataStore.js`
- [x] Debounce estimate call on word input and filter changes (300 ms)
- [x] Display estimate near the search button with colour-coded guidance
- [x] Label estimate as approximate; do not block the search

---

### Phase 2 — Threshold-based display mode

**Config**
- [x] Add `kwic.large_result_threshold` (default: `10000`) to `config/config.yml` and `tests/config.yml`
- [x] Add `kwic.large_result_display_limit` (default: `1000`) to both config files

**Backend**
- [x] Read threshold and display limit via `ConfigValue` in `KWICTicketService`
- [x] Cap `total_pages` in `get_page_result` when `total_hits >= threshold`
- [x] Include `display_limited: true` and `display_limit: N` in the page result response schema
- [x] Verify archive/download endpoint ignores the display cap
- [x] Add tests for the capped and uncapped paths

**Frontend**
- [x] Consume `display_limited` and `display_limit` from the status/page response
- [x] Show a banner: "Sökningen har ~N träffar. Tabellen visar de första M. Ladda ner alla…"
- [x] Surface download CTA prominently alongside the banner
- [x] Remove the silent `cut_off` from `buildKwicTicketPayload`

---

### Phase 3 — Progressive shard delivery

**Backend — Result store**
- [x] Add `PARTIAL` to `TicketStatus` enum
- [x] Add `shards_complete: int = 0` and `shards_total: int = 0` to `TicketMeta` (defaults for Redis backward compat)
- [x] Add `store_shard(ticket_id, shard_index, df)` to `ResultStore`; transition status to `PARTIAL`
- [x] Change artifact layout to per-ticket directory (`{ticket_id}/shard_NNNN.feather`)
- [x] Write shard files atomically (temp file + rename)
- [x] Invalidate `_artifact_cache` entry for the ticket after each `store_shard` call
- [x] Update `load_artifact` to concatenate available shard files in index order during `PARTIAL`
- [x] Write merged artifact at `READY`; delete shard directory immediately after merge
- [x] Update capacity accounting to reserve shard bytes incrementally, not just at `READY`
- [x] Update cleanup to delete the whole per-ticket directory
- [x] Update `artifact_path` callers that assume a single flat file

**Backend — State store**
- [x] Add `increment_shards_complete(ticket_id)` and `set_shards_total(ticket_id, n)` to `TicketStateStore`
- [x] Add `get_shard_progress(ticket_id)` → `(shards_complete, shards_total)` to `TicketStateStore`
- [x] Ensure `PARTIAL` is counted in `_artifact_bytes_delta` (capacity accounting)
- [x] Add `sync_external_partial(ticket_id)` to `ResultStore` for the API process to sync shard progress from Redis

**Backend — Executor**
- [x] Replace `Pool.map()` with `Pool.imap_unordered()` in `execute_kwic_multiprocess`
- [x] Thread `on_shards_total` / `on_shard_complete` callbacks through executor → `kwic()` → `kwic_with_decode()` → `kwic_service.get_kwic()` → `execute_ticket`
- [x] Call `store_shard` via `on_shard_complete` as each result is yielded
- [x] Call `store_shards_ready` after all shards are written (multiprocess path)
- [x] Keep single-process path unchanged (no `PARTIAL` phase; `store_ready` as before)

**Backend — API**
- [x] Expose `shards_complete`, `shards_total` in `KWICTicketStatus` and `KWICPageResult` schemas
- [x] Add `"partial"` to `KWICTicketStatus.status` literal and `KWICPageResult.status` literal
- [x] Update `_get_celery_page_result` and `_get_page_result_local` to handle `PARTIAL` status
- [x] Call `sync_external_partial` in `_get_celery_status` when ticket is not yet `READY`
- [x] Download endpoint blocks-polls until `READY`; returns HTTP 503 on timeout
- [x] Remove `_display_cap` from `KWICTicketService` (Phase 2 cap retired)
- [x] Add `download_wait_timeout_s` to `config/config.yml` and `tests/config.yml`; remove Phase 2 keys

**Backend — Tests**
- [x] Existing result store and ticket service tests updated for new cache-key tuple format
- [x] Obsolete `_display_cap` tests removed
- [x] `kwic_service` call assertion updated for new `on_shards_total` / `on_shard_complete` params
- [x] Test `store_shard` writes atomically and advances `shards_complete` in both in-memory and Redis state
- [x] Test `load_artifact` concatenates shards in index order during `PARTIAL`
- [x] Test `_artifact_cache` is invalidated after `store_shard`
- [x] Test `store_ready` produces a merged artifact consistent with all shards and deletes shard files
- [x] Test capacity accounting across incremental shard writes
- [x] Test executor emits `PARTIAL` before `READY` (via callback simulation in `test_kwic_ticket_service.py`)

**Frontend**
- [x] Add `shardsComplete`, `shardsTotal`, `isPartial` state to `kwicDataStore.js`
- [x] Update `waitForTicketReady` poll loop to continue on `partial` status; fire `fetchKwicPage` on each partial update
- [x] Update `fetchKwicPage` to sync shard state from page response
- [x] Show a shard progress bar (`q-linear-progress`) in `kwicDataTable.vue` during `PARTIAL`
- [x] Disable column sort changes during `PARTIAL` in `onRequest`
- [x] Add `kwicShardProgress` i18n key to both locales (sv + en-US)
- [x] Remove Phase 2 `display_limited` / `display_limit` from `KWICPageResult` schema and `KWICTicketService`
- [x] Remove `large_result_threshold` and `large_result_display_limit` config keys

---

## Summary

This proposal has three layers, each independently shippable and each building on the previous:

1. **Pre-search estimate** — a cheap DTM-based count shown to the user before they press "Sök", setting expectations without touching the search path.
2. **Threshold-based display mode** — when the estimate exceeds a configured limit, the table shows a bounded sample and prominently surfaces download instead of silently cutting off. Replaces the invisible `cut_off`.
3. **Progressive shard delivery** — results appear in the table as each year-range shard finishes, removing the wait entirely for large queries.

All three share a single new estimate endpoint and the same `estimated_hits` field in the ticket-accepted response.

---

## Problem

KWIC searches for common words or unfiltered queries can return hundreds of thousands of hits. The current options are:

1. Apply `cut_off` — users never see the full result set, and the truncation is invisible.
2. Remove `cut_off` — the server blocks for 60+ seconds before returning anything.

Users who want complete data have no good option. Users who get a truncated result often don't know it. The ticket-and-poll architecture is already in place; what is missing is pre-search awareness and shard-level visibility.

---

## Scope

**Phase 1 — Pre-search estimate**
- New `GET /v1/tools/kwic/estimate` endpoint returning a DTM-based hit count for a word + filter combination.
- Frontend: debounced estimate call as the user types or changes filters; display result near the search button with colour-coded guidance.

**Phase 2 — Threshold-based display mode**
- When `estimated_hits` exceeds a configured threshold, the ticket pipeline serves a bounded sample (e.g. first N rows from the first available shard) and prominently surfaces the download path.
- The threshold and sample size are config-driven, not hardcoded.
- The silent `cut_off` parameter is retired; behaviour is now explicit and communicated to the user.

**Phase 3 — Progressive shard delivery**
- Add a `PARTIAL` ticket status that exposes completed shards for paging before the full query finishes.
- Store results per shard rather than as a single artifact file.
- Add `shards_complete` / `shards_total` to the ticket status response for progress display.
- Remove the display limit from Phase 2; the table grows as shards arrive.
- Frontend: adapt the KWIC poll loop to render rows during `PARTIAL`, show a progress indicator, and disable sort controls until `READY`.

---

## Non-Goals

- Sub-shard streaming (CQP is monolithic per shard; row-level streaming is not feasible).
- Progressive loading for n-grams (the DTM path is already fast; no benefit).
- Sorting across partial result sets (sort is applied per shard during `PARTIAL`; global sort activates at `READY`).
- Changing the shard boundary strategy (year-range sharding already implemented in the multiprocess path).

---

## Current Behavior

`KWICTicketService.execute_ticket` calls `kwic_service.get_kwic(...)` which either runs single-process (for small queries) or spawns N worker processes via `execute_kwic_multiprocess`. In both cases results are fully assembled before `result_store.store_ready(...)` is called. The client polls status until `READY`, then fetches pages from a single feather artifact. `cut_off` is passed through to cap the CQP dump before processing. Truncation is silent — the user sees no indication that results were cut.

---

## Proposed Design

### Phase 1: Pre-search estimate endpoint

**New endpoint**

```
GET /v1/tools/kwic/estimate?word=och&lemmatized=false&from_year=1900&party=S&...
```

Response:
```json
{ "estimated_hits": 47000, "in_vocabulary": true }
```

The backend does a single DTM column sum with the same filter opts used by `WordTrendsService`. No CQP query is run. Response time target: < 20 ms. If the word is not in the vocabulary or uses wildcards that cannot be resolved to a single token, `in_vocabulary` is `false` and `estimated_hits` is `null`.

`WordTrendsService` already has access to the filtered DTM via `get_word_trend_results`; the estimate endpoint adds a lightweight method that returns only the total column sum without building time-series data.

**Frontend display**

The KWIC search form makes a debounced estimate call (300 ms delay) whenever the search word or any filter changes. The result appears near the search button:

| Estimated hits | Display |
|---|---|
| `null` / `in_vocabulary: false` | No indicator (word not in DTM, exact count only from CQP) |
| < threshold | "~N träffar förväntade" (neutral) |
| ≥ threshold | "~N träffar — stor träffmängd, nedladdning rekommenderas" (amber) |

The estimate is always labelled as approximate. It does not block the search.

### Phase 2: Threshold-based display mode

A new config key `kwic.large_result_threshold` (default: `10000`) controls when the display mode changes.

When `estimated_hits >= threshold`:

- The ticket pipeline runs as normal but the **results endpoint caps the returned page range** to the first `kwic.large_result_display_limit` rows (default: `1000`, config-driven).
- The status response includes `display_limited: true` and `display_limit: 1000`.
- The frontend shows a prominent banner: *"Sökningen har ~47 000 träffar. Tabellen visar de första 1 000. Ladda ner alla träffar via nedladdningsknappen."*
- The download path is unchanged — it returns all rows regardless of the display limit.

This replaces the current silent `cut_off`. The user sees exactly what is happening and has a clear path to the full data set.

**Implementation note**: the display cap is applied in `KWICTicketService.get_page_result` by capping `total_pages` in the response, not by discarding rows from the artifact. The full artifact is always written so the download path is unaffected.

### Phase 3: Progressive shard delivery

#### Ticket status

Add `PARTIAL` to `TicketStatus`:

```python
class TicketStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"   # new: some shards done, more in flight
    READY   = "ready"
    ERROR   = "error"
```

`TicketMeta` gains two new fields:

```python
shards_complete: int = 0
shards_total: int = 0
```

#### Shard artifact layout

Replace the single `{cache_dir}/{ticket_id}.feather` file with a per-ticket directory:

```
{cache_dir}/{ticket_id}/
    shard_0000.feather     ← written atomically when shard 0 finishes
    shard_0001.feather
    ...
    merged.feather         ← written at READY; used for download
```

Each shard file is written atomically (write to a `.tmp` sibling, then `rename`). Page requests scan available shard files in index order without acquiring a lock on the full set.

#### Result store changes

- `store_shard(ticket_id, shard_index, df)` — writes a shard file and advances `shards_complete`; transitions status to `PARTIAL`.
- `store_ready(ticket_id)` — merges shards, writes `merged.feather`, transitions to `READY`.
- `load_artifact(ticket_id)` — during `PARTIAL`, reads and concatenates available shard files; during `READY`, reads `merged.feather`.
- `artifact_path` returns the directory; callers that use it directly need updating.
- Cleanup deletes the whole per-ticket directory.

#### Multiprocess executor changes

`execute_kwic_multiprocess` currently uses `multiprocessing.Pool.map()`, which is fully blocking — no result is returned until every shard finishes. To enable progressive delivery, replace it with `Pool.imap_unordered()`. The shard index is carried inside the worker args tuple (`(shard_index, corpus_opts, opts, year_range, ...)`), so the worker returns `(shard_index, df)` regardless of completion order. `store_shard(ticket_id, shard_index, df)` names each file `shard_NNNN.feather` by that index, and `store_ready` concatenates shard files in index order to produce `merged.feather`, which is identical to the current `Pool.map()` chronological output. Call `result_store.store_shard(ticket_id, shard_index, df)` as each result is yielded, then call `result_store.store_ready(ticket_id)` after all shards are done.

`TICKET_ROW_ID` is assigned on the merged frame only (not per-shard), preserving it as a stable global row ID. Sort controls are disabled during `PARTIAL`; users never see out-of-order rows.

Celery workers run in a separate process with their own `ResultStore` instance. `store_shard` must therefore propagate shard progress to the API process via `TicketStateStore` (Redis) counters, not only to the worker-local in-memory state. The API process reads these counters via a new `sync_external_partial` bridge (see State store changes below).

Single-process execution remains unchanged (one shard = whole corpus, no `PARTIAL` phase). The Phase 2 display limit is retired once Phase 3 ships; the table simply grows as shards arrive.

#### State store changes

Add per-ticket shard counters to `TicketStateStore` (Redis), mirroring the pattern used for `pending_jobs` and `artifact_bytes`:

- `increment_shards_complete(ticket_id)` — called by the worker's `store_shard`; atomically increments a Redis counter keyed to the ticket.
- `get_shard_progress(ticket_id)` → `(shards_complete, shards_total)` — polled by the API process.
- `PARTIAL` must **not** be counted as a pending job in `_pending_delta`; update the method to treat only `PENDING` as pending.

Add `sync_external_partial(ticket_id)` to `ResultStore`: reads shard counters from `TicketStateStore` and updates the in-memory `TicketMeta` with the current `shards_complete` / `shards_total` and status `PARTIAL`. Called by the API process on every status or page request when the ticket is not yet `READY`.

#### API changes

`GET /kwic/status/{ticket_id}` response gains:

```json
{
  "status": "partial",
  "shards_complete": 3,
  "shards_total": 8,
  "total_hits": 18400
}
```

`total_hits` during `PARTIAL` reflects rows available so far.

`POST /kwic/query` accepted response gains `estimated_hits` (reused from the estimate endpoint, computed at query-submit time):

```json
{ "ticket_id": "...", "estimated_hits": 47000 }
```

#### Download path

`GET /kwic/download/{ticket_id}` waits for `READY` and streams `merged.feather` with no cut-off. The archive path (`/kwic/archive/{ticket_id}`) is unchanged.

#### Frontend changes (Phase 3)

- Poll loop: continue polling when status is `partial`; stop on `ready` or `error`.
- Render table rows from each page response during `PARTIAL`.
- Show a progress bar from `shards_complete / shards_total`.
- Disable column sort controls during `PARTIAL`; re-enable and re-sort at `READY`.
- Remove Phase 2 display-limit banner once `PARTIAL` is in production.

---

## Alternatives Considered

**Keep cut_off, add a separate no-cut-off download endpoint.** Simpler to implement but creates two divergent code paths and still gives users no feedback while the full query runs.

**Server-sent events / WebSockets.** Avoids client polling but requires infrastructure changes (SSE or WS support) and complicates the Celery path. The existing poll loop already works; reuse it.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Shard file writes race with page reads | Atomic rename before exposing shard; page reader scans only fully written files |
| Celery workers write to different filesystems than the API | Already a constraint on the current path; shard files share the same `cache_dir` as the current artifact |
| `merged.feather` write doubles peak disk usage briefly | Delete shard files immediately after writing `merged.feather`; capacity check accounts for shard bytes incrementally |
| Sort accuracy during `PARTIAL` | Documented UX limitation; sort disabled until `READY` |
| `estimated_hits` is inaccurate for lemmatized queries | Show as "~N expected" not as an exact count; null if word not in vocabulary |
| Single-process path gains no UX benefit | Acceptable; single-process is used only for small / filtered queries where latency is already low |
| `Pool.map()` is fully blocking; no `as_completed` hook | Switch to `Pool.imap_unordered()` with explicit `shard_index` in worker args tuple; shard files named by index so merge is always chronological |
| `_artifact_cache` becomes stale during `PARTIAL` | Invalidate the cache entry for the ticket on every `store_shard` call |
| `PARTIAL` counted as pending job blocks new submissions | `_pending_delta` must treat only `PENDING` as pending; update state-store logic |
| `TicketMeta` new fields break Redis deserialization of old entries | Add `default=0` to `shards_complete` / `shards_total`; handle missing keys in `get_ticket` dict |
| Both local and Celery page-result paths need PARTIAL-awareness | Update `_get_celery_page_result` alongside `_get_page_result_local`; do not leave one path behind |
| `cut_off` still silently truncates CWB output without Phase 3 `cut_off` removal | Explicitly retire `cut_off` from `KWICQueryRequest` and full call chain when Phase 3 ships |

---

## Testing and Validation

- Unit tests: `store_shard` writes correctly; page reads during `PARTIAL` return consistent rows; `store_ready` merges and transitions status.
- Integration test: submit a query known to use multiprocessing; assert `PARTIAL` status appears before `READY`; assert page results accumulate across polls.
- Manual smoke test: search for "och" with no filters; confirm table rows appear within ~10 s and progress bar advances to 100%.
- Regression: existing single-process queries reach `READY` without passing through `PARTIAL`.

---

## Acceptance Criteria

1. `TicketStatus.PARTIAL` is a valid status returned by the status endpoint.
2. Page results are served correctly during `PARTIAL`.
3. `shards_complete` / `shards_total` are present and accurate in status responses.
4. `estimated_hits` is returned in the accepted response for words in the vocabulary.
5. Download waits for `READY` and returns all rows with no cut-off.
6. Frontend progress bar advances as shards complete; sort controls re-enable at `READY`.
7. All existing KWIC tests pass.
8. Shard files and merged artifact are removed at TTL expiry.

---

## Recommended Delivery Order

1. **Phase 1 — Estimate endpoint** (fastest to ship, standalone value)
   - New `GET /v1/tools/kwic/estimate` endpoint backed by DTM column sums.
   - Frontend: debounced estimate display near search button with colour-coded guidance.
   - Zero impact on the ticket pipeline; ships independently.

2. **Phase 2 — Threshold-based display mode** (replaces silent cut_off, safe interim)
   - Add `kwic.large_result_threshold` and `kwic.large_result_display_limit` config keys.
   - Apply page cap in `KWICTicketService.get_page_result` when estimate exceeds threshold.
   - Frontend: display-limit banner + prominent download CTA.
   - No shard infrastructure required; works with the current single-artifact result store.

3. **Phase 3 — Progressive shard delivery** (completes the architecture)
   - `TicketStatus.PARTIAL` + `TicketMeta` shard fields + `store_shard` in `ResultStore`.
   - Shard artifact layout and page reader changes.
   - `execute_kwic_multiprocess` calls `store_shard` per shard.
   - API status and schema changes (`shards_complete`, `shards_total`, `total_hits`).
   - Frontend poll loop during `PARTIAL`, progress bar, sort gating.
   - `merged.feather` + download path validation.
   - Retires the Phase 2 display cap once deployed.

---

## Acceptance Criteria

### Phase 1
- `GET /v1/tools/kwic/estimate?word=X&...` returns `{ "estimated_hits": N, "in_vocabulary": true/false }` within 20 ms for a cached corpus.
- Returns `{ "estimated_hits": null, "in_vocabulary": false }` for words not in the DTM vocabulary.
- Frontend shows an estimate near the search button while the user edits parameters.
- Estimate is labelled as approximate; it does not prevent the search.

### Phase 2
- When `estimated_hits >= kwic.large_result_threshold`, the table shows at most `kwic.large_result_display_limit` rows.
- Status response includes `display_limited: true` and `display_limit: N`.
- A banner explains the limit and points to the download button.
- Archive/download endpoint still returns all rows regardless of the display limit.
- Both threshold and display limit are read from config without a code change.

### Phase 3
- After Phase 3 is deployed, the Phase 2 display cap is retired.
- `PARTIAL` status is returned while at least one shard is still in flight.
- Clients can page through available rows during `PARTIAL`.
- `shards_complete` and `shards_total` are accurate in every status response.
- At `READY`, `merged.feather` is consistent with the concatenation of all shards.
- Shard files are cleaned up when the ticket expires or is explicitly deleted.
- Sort controls are disabled during `PARTIAL` and re-enabled at `READY`.

---

## Final Recommendation

Implement the three phases in order. The backend infrastructure (multiprocess sharding, ticket polling, feather storage) is already in place; each phase extends it incrementally without a separate code path.

Start with Phase 1 (estimate endpoint) to give users immediate visibility into query size. Ship Phase 2 to replace the silent `cut_off` with an explicit, user-facing limit. Then deliver Phase 3 to remove the display limit entirely once the shard model is proven.

---

## Risks and Tradeoffs

| Risk | Severity | Notes |
|---|---|---|
| DTM estimate inaccurate for filtered queries | Low | Column sums respect metadata filters; phrase/proximity queries may diverge, but order-of-magnitude accuracy is sufficient for UX guidance |
| Threshold causes confusion if estimate is wrong | Low | Banner labels estimate as approximate; user can still submit and download |
| Shard race condition: page read while shard write in flight | Medium | Mitigated by atomic rename before updating `shards_complete`; no partial reads possible |
| `merged.feather` write doubles disk use briefly | Low | Temporary; shard files deleted after merge |
| Phase 2 display cap needs explicit removal when Phase 3 ships | Low | Remove banner code path and config keys at deployment |
| Config key `kwic.large_result_threshold` absent on older deployments | Low | Default value of `10000` provided; no migration required |
| `Pool.map()` is fully blocking — no `as_completed` to hook into | High | Switch to `imap_unordered()` with `shard_index` in the task args tuple; worker returns `(shard_index, df)`; merge at `READY` concatenates in index order, producing the same chronological result as today |
| Shard progress invisible to API process (cross-process boundary) | High | `TicketStateStore` (Redis) must carry `shards_complete` / `shards_total`; `sync_external_partial` bridges this on every status poll |
| `_artifact_cache` returns stale data after partial writes | Medium | Invalidate cache on every `store_shard`; cache is fast enough that re-reads are not costly |
| `PARTIAL` counted as pending blocks new submissions | Medium | One-line fix to `_pending_delta`; must be done alongside `PARTIAL` introduction |
| Both Celery and local page-result paths need updating | Medium | `_get_celery_page_result` is a parallel code path to `_get_page_result_local`; Phase 3 must handle both |
| Peak disk doubles when shard files + `merged.feather` coexist | Low | Delete shards immediately after merge rather than at TTL expiry |
| `cut_off` still limits CWB output if not explicitly retired | Medium | Remove `cut_off` from `KWICQueryRequest` schema and downstream call chain at Phase 3 deployment |
| Old Redis entries lack `shards_complete` / `shards_total` keys | Low | Default `= 0` in `TicketMeta` dataclass; handle missing keys in state-store deserialization |

---

## Open Questions — Must Resolve Before Implementation Starts

### 1. Executor interface: `imap_unordered` vs `ProcessPoolExecutor` — **Resolved**
Adopt `Pool.imap_unordered()`. The shard index is carried inside the worker args tuple so each worker returns `(shard_index, df)` regardless of completion order. Shard files are named `shard_NNNN.feather` by that index; `store_ready` concatenates them in index order to produce `merged.feather`, which is identical to the current `Pool.map()` chronological output. `TICKET_ROW_ID` is assigned on the merged frame only, not per shard. Out-of-order delivery is invisible to users because sort controls are disabled during `PARTIAL`; ordering is fully restored at `READY`.

### 2. `shard_total` is known at submission time — how is it passed to the worker? — **Resolved**
Write `shards_total` inside `execute_kwic_multiprocess`, immediately after `year_chunks = create_year_chunks(...)` and before the pool starts:

```python
result_store.set_shards_total(ticket_id, len(year_chunks))
```

`execute_kwic_multiprocess` already needs `result_store` and `ticket_id` passed in for Phase 3 (it calls `store_shard` per result), so this requires no additional parameters. Keeping the write here avoids duplicating chunk-computation logic in `execute_ticket` and ensures `shards_total` is set atomically with the pool size decision.

### 3. Cross-process `store_shard` write path — **Resolved**
Adopt the pull model. The Celery worker calls `store_shard`, which writes the shard file to the shared `cache_dir` and increments the Redis shard counter via `TicketStateStore`. The API process never receives a push; it calls `sync_external_partial` on every status or page request when the ticket is not yet `READY`, reading `shards_complete` / `shards_total` from Redis and updating its local `TicketMeta`. This mirrors the existing `sync_external_ready` pattern exactly and requires no new IPC mechanism.

### 4. Artifact-cache invalidation strategy — **Resolved**
Use a version-tagged cache key: `(ticket_id, shards_complete)` instead of plain `ticket_id` for `_artifact_cache`, and `(ticket_id, shards_complete, sort_columns, ascending)` for `_sorted_positions_cache`.

Effect:
- Within a poll cycle where `shards_complete` has not changed, the cached DataFrame is returned with no re-read.
- When a new shard arrives and `shards_complete` increments, the next poll uses a new key, triggers exactly one shard-concat read, and caches the result until the next shard completes.
- Old versioned keys are evicted naturally by the LRU — no explicit invalidation call is needed during `PARTIAL`.
- At `READY`, `shards_complete == shards_total` stabilises to a fixed value, so the merged artifact is cached under a stable key, identical to today's behaviour.

This approach is also robust to increasing `kwic.num_processes` (= shard count) for better perceived progress: more shards means the progress bar has more steps and the first result appears sooner, but cache churn stays proportional to the number of shards that complete — one re-read per shard, not one per poll. Raising `kwic.num_processes` from 8 (≈20-year chunks) to 16 (≈10-year chunks) is therefore a straightforward UX improvement with no cache penalty.

### 5. Capacity accounting during incremental shard writes — **Resolved**
Adopt option (a): pre-reserve capacity upfront. When `execute_kwic_multiprocess` calls `set_shards_total`, also reserve an estimated byte budget for the ticket by setting `ticket.artifact_bytes` to a conservative upfront estimate (e.g. `cut_off × estimated_bytes_per_row`, capped at `max_artifact_bytes`). This reservation is checked against `_artifact_bytes_locked()` immediately — if it would exceed store capacity, fail fast with `ResultStoreCapacityError` before any worker process starts. Individual `store_shard` calls do not re-check capacity; they trust the upfront reservation. At `store_ready`, `ticket.artifact_bytes` is updated to the actual `merged.feather` size, releasing any over-reservation.

This is simpler to implement than per-shard checking and keeps the failure mode consistent with the current `store_ready` path. The trade-off is that the reservation may be pessimistic for filtered queries, but the store already uses eviction to reclaim space so brief over-reservation is acceptable.

### 6. `cut_off` retirement scope and timing — **Resolved**
(a) `KWICQueryRequest.cut_off` is deprecated and ignored at Phase 3 deployment — the field stays in the schema for backward compatibility but is not passed through to the CWB layer. Mark it with a deprecation note in the schema docstring/field description. (b) The deprecated legacy endpoint retains its own hardcoded `cut_off` default (200 000) and is not changed or removed as part of Phase 3. Removal of both the deprecated field and the legacy endpoint is deferred to a future cleanup task.

### 7. Download endpoint behavior during `PARTIAL` — **Resolved**
The download endpoint polls `result_store.require_ticket(ticket_id)` in a tight sleep loop until status reaches `READY` (or `ERROR`), then streams `merged.feather`. A configurable timeout (e.g. `kwic.download_wait_timeout_s`, default 300 s) terminates the wait with a 503 if the ticket does not reach `READY` in time. This keeps the endpoint simple (no SSE or callback mechanism) and consistent with the existing synchronous streaming path. The frontend should disable the download button and show a spinner while status is `PARTIAL`, surfacing it only once the poll loop confirms `READY`.

### 8. Frontend: how many rows to show per poll during `PARTIAL`? — **Resolved**
The currently displayed page is stable — a new shard completing does not re-fetch or replace the rows already shown. The frontend holds its current `page` value across polls; only `total_hits` and `total_pages` are updated from each status response. The user can navigate to higher page numbers as they become available. If the user is on page 2 when shard 5 lands, they stay on page 2; the paginator simply gains more pages. This means the backend must serve any valid page number against the concatenated shard data at the time of the request, not just page 1.

### 9. Phase 2 retirement deployment coordination — **Resolved**
Phase 2 config keys (`kwic.large_result_threshold`, `kwic.large_result_display_limit`) and the frontend `kwicDisplayCapNote` i18n key are removed atomically in the same deployment as Phase 3. This is not left as follow-up debt.
