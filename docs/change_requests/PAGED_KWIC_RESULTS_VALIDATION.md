# Paged KWIC Results Validation

## Scope

This report starts Phase 6 validation for the paged KWIC workflow implemented in:

- `POST /v1/tools/kwic/query`
- `GET /v1/tools/kwic/status/{ticket_id}`
- `GET /v1/tools/kwic/results/{ticket_id}`
- `POST /v1/tools/speeches/download?ticket_id=...`

Environment for this first pass:

- Local test corpus via `tests/output/config.yml`
- FastAPI `TestClient`
- Sample query: `debatt`
- Query params: `words_before=2`, `words_after=2`, `cut_off=50`, `lemmatized=false`, `from_year=1970`, `to_year=1975`, `gender_id=1`

## Parity Sample

- Synchronous KWIC endpoint returned 50 rows.
- Ticketed KWIC status returned `ready` immediately after submission in the test client path.
- Ticketed result pagination returned the same 50 rows as the synchronous mapped endpoint.
- First row matched exactly across both paths:
  - `speech_id`: `i-d2f469c6229f3acb-3`
  - `speech_name`: `Andra kammaren 1970:029 013`
  - `speech_link`: `https://pdf.swedeb.se/riksdagen-records-pdf/1970/prot-1970--ak--029.pdf#page=15`

Validated outcomes from this sample:

- Paged rows match the synchronous mapped endpoint for the same query.
- Total hit count is stable at 50.
- Default ordering is stable for this sample.
- The existing synchronous KWIC endpoint remains live.

## Download Validation

- The 50 KWIC hits deduplicated to 39 unique `speech_id` values.
- Ticket download returned an archive with 40 entries: 39 speech text files plus `manifest.json`.
- Manifest fields matched the query contract:
  - `search`: `debatt`
  - `lemmatized`: `false`
  - `words_before`: `2`
  - `words_after`: `2`
  - `cut_off`: `50`
  - `filters`: `{"gender_id": [1], "year": [1970, 1975]}`
  - `total_hits`: `50`
  - `speech_count`: `39`
- Manifest checksum matched the expected checksum computed from sorted unique speech ids:
  - `cb3acb13536626b6735c4d5e8518917241b1e2cffbd251a35c422ece1663968b`

## Initial Latency Baseline

Measurements were taken with warmed FastAPI `TestClient` requests against the local test corpus.

| Metric | Samples | Average |
| --- | --- | --- |
| Synchronous KWIC query | `193.60`, `170.04`, `160.65`, `169.77`, `178.04` ms | `174.42 ms` |
| Ticket submit + first page | `197.31`, `167.62`, `172.47`, `169.71`, `173.58` ms | `176.14 ms` |
| Cached page fetch | `4.94`, `4.75`, `4.65`, `4.94`, `4.64`, `4.57`, `4.56`, `4.62`, `4.55`, `4.55` ms | `4.68 ms` |

Interpretation:

- End-to-end ticket submission plus first page retrieval is effectively on par with the current synchronous path for this local sample.
- Cached page retrieval is materially faster than recomputing the query.
- These numbers are local test-corpus baselines, not staging or production benchmarks.

## Reliability Validation

Verified through the current automated backend suite:

- Expiry cleanup: expired tickets and their artifacts are removed by `ResultStore.cleanup_expired()`.
- Startup cleanup: stale `.feather`, `.feather.partial`, and `.tmp` files are removed on `ResultStore.startup()`.
- Corrupt artifact handling: unreadable Feather artifacts are deleted on load and surfaced as `ResultStoreNotFound`.
- Queue saturation: `POST /v1/tools/kwic/query` returns `429` with `Retry-After` when `max_pending_jobs` is exhausted.
- Byte-budget exhaustion: oversized artifacts transition the ticket to `error` and raise `ResultStoreCapacityError` during store completion.
- Artifact-budget behavior: oldest ready artifacts are evicted first when a new artifact needs space inside the configured byte budget.

This validation is currently covered by:

- `tests/api_swedeb/api/services/test_result_store.py`
- `tests/api_swedeb/api/endpoints/test_tool_router.py`
- `tests/integration/test_kwic_ticket_validation.py`

## Frontend Rollout Path

- Keep `GET /v1/tools/kwic/{search}` available throughout rollout.
- Keep the frontend KWIC ticket flow explicitly controlled by `kwicDataStore.useTicketFlow`.
- Keep CSV/XLSX export on the synchronous endpoint for the MVP.
- Keep speech ZIP download on the ticket path only when a completed KWIC ticket exists.
- Defer n-gram pagination to `docs/change_requests/PAGED_NGRAM_RESULTS_DESIGN.md`.

## Remaining Phase 6 Work

- Repeat parity and latency checks on a broader or staging-representative corpus.
- Validate multi-query or larger-corpus behavior on a staging-representative corpus.
