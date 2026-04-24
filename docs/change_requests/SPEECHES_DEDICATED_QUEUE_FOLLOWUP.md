# Change Request: Dedicated Speeches Queue Follow-Up

## Status

- Proposed change request
- Scope: Celery queue isolation for speeches ticket execution
- Goal: Revisit a dedicated speeches queue only if later operational evidence shows the default queue is no longer sufficient

## Summary

Keep speeches on the default Celery queue for Phase 1 and Phase 2.

The recommendation is to avoid adding a dedicated speeches queue now. The current priority is correctness, deployability, and simpler operations for the Phase 1 and Phase 2 rollout. A separate speeches queue should be considered later only if staged load testing or production metrics show that mixed default-queue traffic causes unacceptable contention.

## Problem

There is a valid future question about whether speeches jobs should be isolated from other default-queue work.

That is an operational tuning decision, not a correctness prerequisite for the current rollout. If it stays inside the current Phase 1 and Phase 2 scope, it broadens the definition of done and adds extra moving parts before there is evidence that the added complexity is necessary.

## Scope

This change request covers:

- a future decision on whether speeches should move off the default Celery queue
- queue isolation, worker allocation, and routing implications for speeches ticket execution
- operational signals that would justify queue separation

## Non-Goals

This change request does not cover:

- changing the current Phase 1 and Phase 2 recommendation to keep speeches on the default queue
- blocking Phase 1 and Phase 2 deployment on queue redesign
- redesigning Celery routing before load or production evidence supports it

## Current Behavior

The current routing keeps speeches on the default queue.

In [api_swedeb/celery_app.py](../../api_swedeb/celery_app.py), both `api_swedeb.execute_word_trend_speeches_ticket` and `api_swedeb.execute_speeches_ticket` route to the default queue, while KWIC continues to use the separate multiprocessing queue.

This is the recommended state for Phase 1 and Phase 2 because it keeps worker routing simple while the repository finishes rollout-focused validation.

## Proposed Design

Keep speeches on the default queue until there is evidence that queue isolation is needed.

If that evidence appears later, the follow-up work should include:

1. Add a dedicated speeches queue.
   Route `api_swedeb.execute_speeches_ticket` to its own queue in Celery configuration.

2. Add dedicated worker capacity.
   Ensure that one or more workers explicitly consume the speeches queue in deployment.

3. Validate mixed-workload impact.
   Compare queue latency and worker contention before and after the split.

4. Update operations guidance.
   Document queue routing, worker assignment, and failure modes in operations documentation if the split is adopted.

## Tradeoffs And Risks

Keeping speeches on the default queue now has these advantages:

- simpler deployment and worker routing
- fewer operational knobs to maintain
- lower risk of misconfiguration during the Phase 1 and Phase 2 rollout
- better worker utilization when traffic is low or mixed

The tradeoff is weaker workload isolation. If speeches traffic becomes heavy, it can contend with other default-queue work and make queue behavior harder to tune or interpret.

Moving speeches to a dedicated queue later would improve isolation and observability, but it would also add deployment complexity and a new operational dependency on dedicated workers actually consuming that queue.

## Validation And Acceptance Criteria

Treat this follow-up as justified only if at least one of the following becomes true:

- staged load testing shows mixed default-queue traffic causes unacceptable queue latency
- production metrics show speeches jobs dominate default-queue wait time
- speeches jobs need different concurrency or scaling behavior than the rest of the default queue

If the queue split is implemented later, validation should include:

- correct routing of speeches tasks to the dedicated queue
- workers actively consuming that queue in deployment
- no regression in ticket completion, paging, or download behavior
- improved or at least not worse latency under mixed load

## Final Recommendation

Keep speeches on the default queue for the Phase 1 and Phase 2 rollout.

Use this document only as a future optimization track if later load testing or production evidence shows that a dedicated speeches queue is operationally justified.