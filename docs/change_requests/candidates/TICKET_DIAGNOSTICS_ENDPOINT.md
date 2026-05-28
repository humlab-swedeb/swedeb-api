# Internal Ticket Diagnostics Endpoint

## Status

- Proposed feature / change request
- Scope: internal backend diagnostics for ticket state, Celery workers, and Redis queue status
- Goal: make intermittent ticket incidents faster to diagnose without manual container exec and Redis CLI steps

## Summary

Add an internal diagnostics endpoint that returns one bounded snapshot of the ticket control plane.

The current diagnostics flow is split across multiple manual steps:

- run a copied helper script in a container to inspect Celery workers and queue depth,
- query Redis directly for `swedeb:ticket-state:stats:pending_jobs`,
- inspect individual ticket payloads if the shared counter is non-zero.

This is workable for ad hoc incident response, but it is slow and easy to miss when the problem is intermittent. The recommended design is to add one internal-only endpoint that combines those signals into one response and reuses the same collection logic as the existing helper script.

## Problem

Intermittent `429 Too many pending ticket jobs` incidents are hard to diagnose while they are happening.

The relevant signals are spread across different mechanisms:

- Celery worker reachability and queue depth are available through the helper script.
- Shared pending-ticket state is stored in Redis.
- Ticket metadata is stored separately from queue state.

By the time an operator has copied the helper script into a container and run the Redis checks manually, the queues may already be empty and the pending counter may already have dropped back to zero.

This increases time to diagnosis and makes it harder to distinguish between:

- real worker or broker backlog,
- stale pending tickets,
- short-lived dispatch failures,
- ordinary load spikes that have already drained.

## Scope

- Add one internal diagnostics endpoint for the async ticket control plane.
- Return a bounded snapshot of shared ticket counters, Celery worker status, and queue depth.
- Include a small sample of pending ticket metadata when pending tickets exist.
- Reuse shared collection logic between the endpoint and the existing diagnostics script.
- Add backend tests for the new collection and endpoint behavior.

## Non-Goals

- Adding a public frontend diagnostics view.
- Returning full dumps of all ticket payloads.
- Building a full observability platform or replacing logs and metrics.
- Redesigning the existing ticket architecture.
- Solving authentication for all future internal endpoints in this change alone.

## Current Behavior

Current incident checks require multiple manual commands in the deployment environment.

Example flow:

1. Copy `scripts/inspect_celery_runtime.py` into a running container.
2. Execute it inside the API or worker container.
3. Query Redis separately for `swedeb:ticket-state:stats:pending_jobs`.
4. Scan and inspect ticket keys manually if the pending count is non-zero.

This is useful, but it has several limitations:

- the helper script is not baked into the current runtime image,
- the workflow is manual and slower than a single HTTP call,
- results are split across multiple tools,
- operators must remember the relevant Redis keys and container names.

## Proposed Design

### Endpoint contract

Add an internal endpoint with a narrow operational purpose, for example:

`GET /internal/diagnostics/tickets`

This endpoint should not be exposed through the normal public tool API surface.

The default response should be cheap, bounded, and sufficient for incident triage.

### Response shape

Return one JSON document with at least:

- `timestamp`
- `hostname` or container identifier
- `pending_jobs`
- `artifact_bytes`
- `max_pending_jobs`
- `cleanup_interval_seconds`
- `ticket_state_prefix`
- queue depths for `celery.default_queue` and `celery.multiprocessing_queue`
- reachable Celery workers
- per-worker active, reserved, and scheduled counts
- a bounded sample of oldest pending tickets, for example up to 5 entries with:
  - `ticket_id`
  - `status`
  - `created_at`
  - `expires_at`
  - optional lightweight query metadata summary

The endpoint should avoid large payloads and should not return every ticket by default.

### Backend behavior

Refactor the current diagnostics collection logic so that both the script and the endpoint use the same underlying helper or service.

Recommended shape:

- a small diagnostics collector under `api_swedeb/api/services/` or `api_swedeb/core/`
- the existing script becomes a thin CLI wrapper around that collector
- the new endpoint calls the same collector and returns the structured result

The collector should:

1. read shared counters from the ticket state store,
2. inspect Celery worker reachability and queue activity,
3. inspect Redis queue depths,
4. list only enough ticket metadata to produce a bounded pending sample,
5. degrade cleanly if one source is unavailable.

### Access model

This endpoint should be internal-only.

Recommended minimum expectations:

- disable it by default outside explicit operational use,
- keep it off the public frontend route surface,
- require either deployment-network isolation or simple admin protection.

The exact protection mechanism can be decided during implementation, but the endpoint should not be treated as anonymous public API.

## Alternatives Considered

### Keep using the helper script and Redis CLI only

This is the current approach.

Rejected as the only solution because it is too manual for short-lived incidents and too easy to perform inconsistently.

### Add more logging instead of an endpoint

Logs help after the fact, but they do not give operators one current combined snapshot of queue, worker, and shared ticket state.

Deferred as complementary, not a replacement.

### Expose a public diagnostics page in the frontend

Rejected because the data is operational and should not be surfaced to normal end users.

## Risks And Tradeoffs

- The endpoint can expose sensitive operational details if it is not gated properly.
- Celery inspect calls can be slower or less reliable than local state reads.
- Listing pending tickets must stay bounded to avoid turning diagnostics into an expensive control-plane scan.
- A richer endpoint is helpful during incidents, but it adds a small amount of maintenance burden.

## Testing And Validation

- Unit-test the diagnostics collector with mocked Celery and Redis responses.
- Test partial-failure behavior when queue inspection or Celery inspect fails.
- Test that the pending ticket sample is bounded and ordered consistently.
- Test that the endpoint is unavailable when diagnostics are disabled.
- Test that the script and endpoint return the same core fields from the shared collector.

## Acceptance Criteria

- Operators can retrieve one combined ticket-control-plane snapshot through an internal endpoint.
- The response includes shared pending-ticket counters, queue depths, and worker status.
- The response includes a bounded sample of pending tickets when pending jobs exist.
- The endpoint degrades cleanly if one dependency is unavailable.
- The existing helper script reuses the same collector logic instead of drifting separately.
- The endpoint is not exposed as anonymous public application functionality.

## Recommended Delivery Order

1. Extract the current script logic into a reusable diagnostics collector.
2. Extend the collector with shared ticket-state counters and bounded pending-ticket sampling.
3. Add the internal endpoint behind a config gate.
4. Add tests for the collector and endpoint.
5. Decide whether the helper script should remain for direct container-side use after the endpoint ships.

## Open Questions

- Should the first version be enabled only in staging, or be available in all environments behind a gate?
- Should the endpoint be excluded from OpenAPI entirely, or included but marked internal?
- What is the smallest acceptable access-control mechanism for the first version?

## Final Recommendation

Add one internal diagnostics endpoint that combines shared ticket-state counters, Celery worker status, Redis queue depth, and a small pending-ticket sample.

Implement it by extracting the current helper script logic into a reusable collector and reusing that collector from both the script and the new endpoint.