# Progressive KWIC Loading

## Status

- Proposed feature
- Scope: backend (result store, ticket service, multiprocess executor, new estimate endpoint) + frontend (KWIC store, table display)
- Goal: give users hit-count estimates before searching, apply threshold-based display limits transparently, and deliver KWIC results incrementally as corpus shards complete — removing the silent hard cut-off for both display and download

---

## Progress

### Phase 1 — Pre-search estimate

**Backend**
- [ ] Add `KWICEstimateService` (or extend `KWICService`) with a DTM column-sum method that respects the same metadata filters as `WordTrendsService`
- [ ] Add `GET /v1/tools/kwic/estimate` endpoint with query params matching the KWIC search form
- [ ] Return `{ "estimated_hits": N, "in_vocabulary": true/false }` schema
- [ ] Add `kwic.estimate` section to `config/config.yml` and `tests/config.yml` if needed
- [ ] Add unit test for the estimate method (mocked DTM)
- [ ] Add API test for the estimate endpoint

**Frontend**
- [ ] Add `fetchEstimate(word, filters)` action to `kwicDataStore.js`
- [ ] Debounce estimate call on word input and filter changes (300 ms)
- [ ] Display estimate near the search button with colour-coded guidance
- [ ] Label estimate as approximate; do not block the search

---

### Phase 2 — Threshold-based display mode

**Config**
- [ ] Add `kwic.large_result_threshold` (default: `10000`) to `config/config.yml` and `tests/config.yml`
- [ ] Add `kwic.large_result_display_limit` (default: `1000`) to both config files

**Backend**
- [ ] Read threshold and display limit via `ConfigValue` in `KWICTicketService`
- [ ] Cap `total_pages` in `get_page_result` when `estimated_hits >= threshold`
- [ ] Include `display_limited: true` and `display_limit: N` in the page result response schema
- [ ] Verify archive/download endpoint ignores the display cap
- [ ] Add tests for the capped and uncapped paths

**Frontend**
- [ ] Consume `display_limited` and `display_limit` from the status/page response
- [ ] Show a banner: "Sökningen har ~N träffar. Tabellen visar de första M. Ladda ner alla…"
- [ ] Surface download CTA prominently alongside the banner
- [ ] Remove the silent `cut_off` fallback path

---

### Phase 3 — Progressive shard delivery

**Backend — Result store**
- [ ] Add `PARTIAL` to `TicketStatus` enum
- [ ] Add `shards_complete: int` and `shards_total: int` to `TicketMeta`
- [ ] Add `store_shard(ticket_id, shard_index, df)` to `ResultStore`
- [ ] Change artifact layout to per-ticket directory (`{ticket_id}/shard_NNNN.feather`)
- [ ] Write shard files atomically (temp file + rename)
- [ ] Update `load_artifact` to concatenate available shards during `PARTIAL`
- [ ] Write `merged.feather` at `READY` for the download path
- [ ] Update cleanup to delete the per-ticket directory

**Backend — Executor**
- [ ] Change `execute_kwic_multiprocess` to call `store_shard` in `as_completed` loop
- [ ] Call `store_ready` after all shards are written
- [ ] Keep single-process path unchanged

**Backend — API**
- [ ] Expose `shards_complete`, `shards_total`, `total_hits` in the status response
- [ ] Add `estimated_hits` to the ticket-accepted response (computed at submit time)
- [ ] Update page response to work correctly during `PARTIAL`
- [ ] Verify download endpoint waits for `READY` before streaming

**Backend — Tests**
- [ ] Test `store_shard` writes atomically and advances `shards_complete`
- [ ] Test `load_artifact` concatenates shards in order during `PARTIAL`
- [ ] Test `store_ready` produces a `merged.feather` consistent with all shards
- [ ] Test executor emits `PARTIAL` before `READY`

**Frontend**
- [ ] Update `waitForTicketReady` poll loop to continue on `partial`
- [ ] Render rows progressively as new pages arrive during `PARTIAL`
- [ ] Show a shard progress bar from `shards_complete / shards_total`
- [ ] Disable column sort controls during `PARTIAL`; re-enable and re-sort at `READY`
- [ ] Remove Phase 2 display-limit banner and config key reads
- [ ] Remove the `cut_off` parameter from request construction

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

`execute_kwic_multiprocess` currently collects all `Future` results with `as_completed` and concatenates at the end. Change it to call `result_store.store_shard(...)` inside the `as_completed` loop as each shard finishes, then call `result_store.store_ready(...)` after all are done.

Single-process execution remains unchanged (one shard = whole corpus, no `PARTIAL` phase). The Phase 2 display limit is retired once Phase 3 ships; the table simply grows as shards arrive.

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
| `merged.feather` write duplicates disk usage briefly | Acceptable; it is removed along with shards at TTL expiry |
| Sort accuracy during `PARTIAL` | Documented UX limitation; sort disabled until `READY` |
| `estimated_hits` is inaccurate for lemmatized queries | Show as "~N expected" not as an exact count; null if word not in vocabulary |
| Single-process path gains no UX benefit | Acceptable; single-process is used only for small / filtered queries where latency is already low |

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
