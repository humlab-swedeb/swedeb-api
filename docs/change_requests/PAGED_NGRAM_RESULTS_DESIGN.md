# Change Request: Paged N-Gram Results Design

**Status**: Follow-up proposal  
**Scope**: n-gram paging, cache payload, and export behavior after the KWIC ticket workflow  
**Goal**: define a ticket-based n-gram design that fits the current aggregation pipeline without blocking the KWIC MVP

---

## Summary

N-gram paging should be designed separately from KWIC.

The current n-gram pipeline already reduces raw keyword windows into an aggregated result table. That means the cache payload, supported reuse, and validation target differ from KWIC. The recommended MVP is to cache the final aggregated n-gram table for one exact query and support page and sort reuse only. Changing filters or recomputing counts should create a new ticket.

This proposal is a follow-up to `docs/change_requests/PAGED_KWIC_RESULTS_DESIGN.md`.

## Problem

`GET /v1/tools/ngrams/{search}` currently returns the full n-gram result in one response, and the client keeps the full table in memory.

That creates the same broad UX and payload problems as KWIC:

1. the browser waits for the full response before rendering
2. the full result stays resident in client memory
3. page and sort changes reuse client memory instead of server-side paging

But n-grams differ from KWIC in one important way: the backend already collapses raw windows into an aggregated table before the API response is built. After that reduction, the final table no longer supports within-ticket metadata re-filtering or recomputation of counts for a narrower subset.

## Scope

This proposal covers:

1. a ticketed n-gram submit/status/results workflow
2. the canonical cached payload for n-gram results
3. supported and unsupported reuse within one ticket
4. export behavior for paged n-gram results
5. rollout order relative to the KWIC ticket flow

## Non-Goals

This proposal does not cover:

1. re-filtering cached n-gram results by year, party, gender, or other metadata
2. recomputing counts for narrower subsets from an already aggregated cached result
3. changing the underlying n-gram extraction or aggregation algorithm
4. shipping n-gram paging before the KWIC ticket flow is validated

## Current Behavior

The current n-gram pipeline behaves like this:

1. `GET /v1/tools/ngrams/{search}` queries keyword windows from the corpus.
2. The backend transforms windows into n-grams.
3. The result is aggregated into `ngram`, `window_count`, and deduplicated `documents`.
4. The mapper converts that table into the public API shape.
5. The frontend receives the full n-gram result set in one response.

## Proposed Design

### API Contract

Add an additive ticket workflow after the KWIC MVP is proven:

1. `POST /v1/tools/ngrams/query`
2. `GET /v1/tools/ngrams/status/{ticket_id}`
3. `GET /v1/tools/ngrams/results/{ticket_id}`

The submit request should mirror the exact-query inputs from the current n-gram endpoint and use the same filter vocabulary as the existing backend selection logic.

### Canonical Cached Payload

For the MVP, cache the final aggregated n-gram table for the exact query, not the raw keyword windows.

Recommended artifact columns:

1. `ngram`
2. `window_count`
3. `documents`
4. `_ticket_row_id`

`documents` can remain in the current compact backend representation inside the artifact. The page response can convert it to the public API shape.

This is the recommended MVP because:

1. it matches the current backend aggregation boundary
2. it supports exact-query page and sort reuse cleanly
3. it avoids storing the much larger raw window payload

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

N-gram export should be explicit.

Recommended MVP rule:

1. keep any current export flow on the existing synchronous endpoint until a dedicated ticket-based export contract exists
2. do not make the frontend fetch every page just to rebuild export client-side

If server-side export is added later, it should export directly from the cached aggregated n-gram artifact.

> **Deprecation note**: Once this change is implemented and the n-gram flow uses a ticket-based speech export path
> (equivalent to `GET /v1/tools/speeches/archive/{ticket_id}`), the `POST /v1/tools/speeches/download` endpoint
> can be deprecated. At that point no active frontend caller will send speech IDs via POST body; all speech
> retrieval will go through the ticket archive route.

### Persistence and Lifecycle

Reuse the same `ResultStore`, lifespan, cleanup, and byte-budget machinery introduced by the KWIC ticket flow.

N-gram tickets should still be logically separated from KWIC tickets, either by namespace or ticket type, so cleanup, metrics, and validation stay clear.

## Risks And Tradeoffs

1. Caching the final aggregated table keeps the MVP simple, but it makes within-ticket re-filtering impossible.
2. `documents` can still be large for high-frequency n-grams, even after deduplication.
3. Export behavior will regress if it is not handled explicitly during frontend migration.
4. This proposal intentionally defers richer analytical reuse in favor of a smaller, safer MVP.

## Testing And Validation

The n-gram ticket flow should not be considered complete until all of the following pass:

1. concatenating all ticketed pages in default order reproduces the same mapped n-gram rows as the current synchronous endpoint for the same exact query
2. repeated requests for the same ticket and sort settings return stable totals and stable row order
3. expiry and cleanup behave the same way as the KWIC ticket flow
4. if ticket-based export is added, it reproduces the same exported rows as the current synchronous export baseline for the same exact query

## Acceptance Criteria

1. the existing `GET /v1/tools/ngrams/{search}` endpoint remains unchanged
2. the ticketed n-gram flow is additive
3. the cached payload is explicitly defined as the final aggregated table
4. the proposal does not claim support for within-ticket re-filtering or recomputation
5. export behavior is explicitly defined before frontend migration begins

## Recommended Delivery Order

1. finish and validate the KWIC ticket workflow
2. reuse the same `ResultStore` and lifecycle machinery for n-grams
3. add n-gram submit, status, and results endpoints
4. add a dedicated export contract if frontend export should move to the ticketed path

## Final Recommendation

Implement n-gram paging only as a follow-up to the KWIC ticket workflow.

For the MVP, cache the final aggregated n-gram table for exact-query reuse, support page and sort only, and treat any filter change or recomputation need as a new ticket.