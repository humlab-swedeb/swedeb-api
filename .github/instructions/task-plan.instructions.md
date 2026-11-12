---
description: "Use when creating or updating a repository-verified task plan for one ready phase under docs/proposals."
applyTo: "docs/proposals/**/*TASK_PLAN.md"
---
# Phase Task Plans

Create one repository-verified implementation plan for a single phase. A task plan must let another contributor execute and validate the approved work without repeating the initial investigation.

## Before writing

1. Read the source proposal and phase plan. Confirm the selected phase is ready and collect its `PH*-AC-*` criteria, source `P-AC-*` criteria, decisions, dependencies, and validation milestones.
2. Inspect current source, tests, configuration, and documentation to verify affected files, symbols, callers, consumers, contracts, data flows, commands, and test fixtures.
3. Check current worktree changes. Consider them when identifying conflicts; do not overwrite or claim them as part of the planned change.
4. Follow [Change-request document structure](./proposal-document-structure.instructions.md) and applicable repository instructions.
5. Do not use `TBD` for facts that reasonable repository inspection can establish.

If the phase is not ready, mark the plan blocked and name the decision. Do not present it as validated.

## Plan structure

Include the sections that guide implementation without adding empty or repetitive material:

1. Phase summary and readiness
2. Repository findings and evidence
3. Scope and affected components
4. Work breakdown
5. Acceptance-criteria coverage
6. Validation and testing
7. Deliverables
8. Progress tracker
9. Definition of done
10. Risks and open questions, when material

For each task, provide a stable ID such as `T1.1`, a concrete change, exact verified targets, dependencies, constraints, validation IDs, and completion evidence. Mark proposed new files `NEW`.

For each validation, provide a stable ID such as `V-1`, an executable repository command or specific manual method, covered criteria, expected result, and baseline status (`Pass`, `Fail`, or `Not run` with a reason). Name exact test files and relevant scenarios when known.

Map every phase criterion to one or more tasks and validation IDs. Every referenced ID must exist. Include relevant negative, boundary, regression, contract, migration, security, and quality checks without inventing requirements.

## Readiness and validation

- **Validated** — targets and interfaces are verified, no unresolved decision can change the work, and executable validation methods are specified.
- **Draft** — further repository investigation or user confirmation is needed.
- **Blocked** — a missing decision or dependency prevents planning or implementation.

Explain Draft or Blocked status. Do not claim an unrun baseline check passed. A Validated plan has no unresolved placeholder that could change implementation or validation.

## Rules

- Keep the plan scoped to the selected phase; do not add unrelated improvements.
- Distinguish verified facts from assumptions and planned behavior from current behavior.
- Do not invent repository paths, symbols, APIs, commands, tests, owners, or results.
- Order work by actual dependencies. Record unknown dependencies as open questions.
- Keep tasks independently checkable and use direct verbs.
- Before finishing, verify acceptance-criteria coverage, deliverable paths, validation IDs, and relative links.
