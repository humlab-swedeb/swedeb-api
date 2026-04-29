# Change Request: Multi-Container Scaling After Phase 2

## Status

- Proposed change request
- Scope: Multi-container API deployment and horizontal scaling
- Goal: Make replicated API-container deployments safe without blocking Phase 1 and Phase 2 rollout

## Summary

Split multi-container scaling out of `docs/MULTIUSER_USAGE_ASSESSMENT.md` so the current work can stop at Phases 1 and 2.

The recommendation is to treat Phase 3 as a separate follow-up. Phase 1 and Phase 2 should be deployable once single-container and multi-process correctness are validated. Multi-container routing, rolling restarts across replicas, and horizontal load validation should not block that rollout.

## Problem

The original assessment combined two different goals:

- making the current deployment shape safe
- proving that the same design is safe across multiple API containers behind shared infrastructure

Those are related, but they do not need to ship together.

Keeping Phase 3 inside the main implementation plan makes the definition of done broader than necessary. It delays deployment of the Phase 1 and Phase 2 improvements even after the code is already good enough for one-container and multi-process use.

## Scope

This change request covers:

- cross-container ticket submission, polling, paging, and download validation
- correctness under shared Redis and shared artifact storage across multiple API containers
- routing correctness without sticky sessions
- rolling restart behavior across replicated API containers
- staged load testing for multi-container deployments

## Non-Goals

This change request does not cover:

- shared ticket-state implementation already completed in Phase 1
- worker-churn and shared-counter work already completed in Phases 1 and 2
- blocking deployment of the Phase 1 and Phase 2 rollout on multi-container validation
- redesigning the existing Phase 1 and Phase 2 architecture unless multi-container validation proves it necessary
- reconsidering whether speeches should move to their own Celery queue; that future tuning question is tracked separately in `docs/change_requests/SPEECHES_DEDICATED_QUEUE_FOLLOWUP.md`

## Current Behavior

The repository now has the core Phase 1 and partial Phase 2 building blocks in place:

- shared Redis-backed ticket metadata
- shared pending-job and artifact-byte accounting
- non-destructive startup behavior for artifacts
- worker-backed speeches ticket execution in production mode
- bounded frontend polling and retry hints
- focused restart, cross-instance, and worker-churn coverage at the store and service level

What is still missing is deployment-level proof that the same behavior remains correct when traffic is routed across multiple API containers or replicas.

## Proposed Design

Treat Phase 3 as a separate deployment-validation track that starts after Phase 2 is deployable.

Recommended work items:

1. Add multi-container correctness tests.
   Submit a ticket through API instance A and poll, page, and download through API instance B.

2. Validate routing without stickiness.
   Confirm that correctness does not depend on the load balancer sending a user back to the same API container.

3. Validate rolling restarts.
   Restart one API container at a time while tickets are pending and ready, and verify that user-visible ticket state remains valid.

4. Run staged horizontal load tests.
   Exercise mixed ticket creation, polling, paging, and download traffic across multiple API containers.

5. Only widen the architecture if validation exposes a real gap.
   The default expectation should be that the current shared-state design is sufficient until proven otherwise.

## Risks And Tradeoffs

Deferring Phase 3 reduces scope and lets the repository ship the already-implemented Phases 1 and 2 sooner.

The tradeoff is that Phase 1 and Phase 2 completion should not be described as proof that replicated API-container deployments are safe. That claim still needs deployment-level validation.

If multi-container validation exposes gaps, the follow-up may require operational or architectural adjustments that are not visible in the current store-level and service-level tests.

## Testing And Validation

Validation for this change request should include:

- multi-container ticket submit and poll tests
- multi-container page and download tests
- no-sticky-session routing tests
- rolling restart tests during active ticket traffic
- staged load tests against the replicated deployment topology

## Acceptance Criteria

- Ticket submission on one API container can be polled, paged, and downloaded from another.
- No sticky-session requirement is needed for ticket correctness.
- Rolling restarts do not invalidate pending or ready tickets.
- Shared limits and artifact behavior remain correct across replicated API containers.
- Staged multi-container load tests complete with acceptable latency and error rate.

## Final Recommendation

Keep `docs/MULTIUSER_USAGE_ASSESSMENT.md` scoped to Phases 1 and 2.

Treat multi-container horizontal scaling as a separate follow-up change request. Deploy Phase 1 and Phase 2 when their own validation is complete, then use this document to drive the later Phase 3 rollout.