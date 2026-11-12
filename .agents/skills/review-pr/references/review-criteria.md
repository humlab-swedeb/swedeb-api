# PR review criteria

Apply severity to **observed impact**, not the amount of code changed.

| Severity | Definition |
|---|---|
| P0 | Critical/blocking defect with immediate severe consequences, such as exploitable security exposure or irreversible data loss in normal use. |
| P1 | High-confidence serious bug, breach, or regression affecting an important workflow. |
| P2 | Concrete correctness, compatibility, performance, or test-coverage gap with moderate impact. |
| P3 | Minor but actionable problem worth flagging, not merely a style preference. |

Check, as relevant:

- **Correctness:** invalid states, boundary cases, error handling, unexpected side effects, backwards compatibility.
- **Data:** transactions, migration safety, schema constraints, idempotency, consistency, deletion/rollback behavior.
- **Security:** authentication, authorization, injection, exposed secrets, unsafe logging, sensitive data handling.
- **Concurrency:** locking, race conditions, multi-worker/multi-request behavior.
- **Performance:** concrete N+1 patterns, repeated expensive work, unbounded operations.
- **Tests:** missing coverage of a newly introduced failure path, misleading assertions, flaky or ineffective tests.
- **Specifications:** violations of relevant accepted requirements, phase plans, or repository conventions with material impact.

Before reporting each finding, answer:

1. Is the problematic behavior reachable given the surrounding implementation?
2. Does another safeguard already prevent it?
3. What realistic input or state triggers the issue?
4. Which changed line best anchors the finding?
5. Can the author act on the concise recommendation?

Omit or label uncertainty when evidence is insufficient. Never quote secrets or credential values.
