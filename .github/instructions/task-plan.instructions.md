---
name: "Phase Task Plan Instructions"
description: "Use when creating or updating repository-validated implementation plans, phase work breakdowns, implementation checklists, or execution trackers."
applyTo: "docs/proposals/**/*_TASK_PLAN.md"
---


# Copilot Instructions: Phase Task Plans

When asked to plan a development phase, produce a Markdown implementation plan detailed enough for another coding agent to execute.

Unless implementation is explicitly requested, create or update only the requested planning document. Do not modify implementation, test, configuration, or unrelated documentation files.

## Planning Process

Before writing the plan:

1. Extract the goal, scope, constraints, and acceptance criteria.
2. When `graphify-out/graph.json` exists, begin with a scoped `.venv/bin/graphify query "<phase question>"`. Use `path` or `explain` for relationships, then inspect relevant project instructions, code, tests, configuration, and documentation to verify findings.
3. Trace affected callers, consumers, contracts, schemas, and data flows where relevant.
4. Locate existing project commands and similar implementations.
5. Identify dependencies, risks, ambiguities, and behavior that must be preserved.
6. Validate the completed plan using the checklist below.

Treat Graphify as a navigation aid, not the source of truth. If it conflicts with source or tests, plan from the current source and note the discrepancy.

Do not use `TBD` for facts that reasonable repository inspection can establish.

## Output

Return only the Markdown plan unless the user asks for explanation.

Prefer repository-specific detail over generic guidance. Name verified files, symbols, commands, APIs, and tests when applicable, and explain material omissions.

Use one of these readiness states:

* **Validated** — repository targets are verified, no unresolved decision can change the implementation, and the plan is ready for execution.
* **Draft** — more repository investigation or user confirmation is required before implementation can begin.
* **Blocked** — a missing external decision or dependency prevents completing the plan or starting implementation.

Explain why a plan is Draft or Blocked. Use only Validated plans for implementation handoff.
A Validated plan must contain executable validation commands or manual methods and no unresolved placeholders.

## Default Structure

1. Phase Summary
2. Repository Findings
3. Scope
4. Work Breakdown
5. Acceptance-Criteria Coverage
6. Validation And Testing
7. Deliverables
8. Progress Tracker
9. Definition Of Done
10. Risks And Open Questions — when relevant

Include sections that add implementation guidance. Omit a section only when it is genuinely irrelevant; do not add empty or repetitive sections.

## Phase Summary

Include:

* Phase title and goal.
* Plan readiness.
* Constraints and dependencies.
* Source proposal and phase-plan links, plus the phase criterion IDs.
* Acceptance criteria as a numbered checklist using IDs such as `PH1-AC-1`.

Preserve supplied phase criteria and their source proposal mappings. Clarify outcomes when necessary without changing the IDs.

## Repository Findings

Summarize only findings that affect implementation:

Start with **Repository basis:** the branch and commit when available, the planning date, and whether uncommitted changes were considered.

| Evidence                  | Finding          | Planning implication          |
| ------------------------- | ---------------- | ----------------------------- |
| `path/to/file.py::symbol` | Current behavior | Required change or constraint |

Prefer paths and symbols over line numbers. Clearly distinguish verified findings from assumptions.

## Scope

State:

* **In scope**
* **Out of scope**
* Affected components, layers, contracts, data, tests, and documentation

Do not add unrelated improvements.

## Work Breakdown

Create the fewest independently implementable and reviewable work areas, normally 2–6.

For each work area include:

### Area N: Action-oriented title

**Objective:** Observable result of this area.

**Affected code:** Verified existing files and symbols, plus proposed files marked `NEW`.

**Dependencies:** Preceding areas or unresolved decisions.

**Tasks:**

Give every task a stable ID and use this structure:

```markdown
* [ ] `T1.1` **Change:** Concrete implementation result.
  * **Target:** Exact existing file and symbol, or proposed file marked `NEW`.
  * **Current → required:** Existing behavior and required behavior.
  * **Implementation:** Steps, interfaces, data flow, state changes, and error behavior.
  * **Constraints:** Compatibility, preservation, migration, and security requirements when relevant.
  * **Validation:** Validation IDs, specific test files, cases, and expected results, including negative and boundary cases when relevant.
```

**Completion evidence:** State the observable condition that proves the area is complete.

Order areas according to implementation dependencies.

## Acceptance-Criteria Coverage

Map every acceptance criterion to implementation and validation:

| Criterion | Task IDs     | Validation IDs | Expected evidence |
| --------- | ------------ | -------------- | ----------------- |
| `PH1-AC-1` | `T1.1`, `T1.2` | `V-1`       | Observable result |

No acceptance criterion may remain unmapped, and every referenced task and validation ID must exist.

## Validation And Testing

Give every validation check a stable ID such as `V-1`. Use verified repository commands or executable manual methods:

| ID    | Check and target | Command or method    | Covers            | Expected result | Baseline |
| ----- | ---------------- | -------------------- | ----------------- | --------------- | -------- |
| `V-1` | Focused tests    | Exact command or manual method | `PH1-AC-1` | Tests pass | Pass, Fail, or Not run: reason |
| `V-2` | Regression tests | Exact command or manual method | Existing behavior | No regressions | Pass, Fail, or Not run: reason |

Include relevant:

* Unit, component, integration, and contract tests.
* Negative, boundary, and regression cases.
* Type checking, linting, and formatting.
* Migration and data-integrity checks.
* Security and authorization checks.
* Documentation or generated-artifact checks.

For every planned test, name the exact existing or `NEW` test file, scenario, fixtures or input data, and expected assertions.
Run relevant baseline checks during planning when safe and proportionate. Record Pass, Fail, or Not run with any existing failures
or reason for not running; do not present a planned check as a current pass.

## Deliverables

List every file or generated artifact to create or update. Use exact paths, mark new targets `NEW`, and link each deliverable to
its producing task IDs.

| Deliverable | Target | Task IDs | Completion evidence |
| ----------- | ------ | -------- | ------------------- |
| Code change | `path/to/file.py::symbol` | `T1.1` | Observable result |

## Progress Tracker

| Area   | Status      | Dependencies | Notes |
| ------ | ----------- | ------------ | ----- |
| Area 1 | Not started | None         |       |

Use: Not started, In progress, Blocked, or Done.

## Definition Of Done

Include a phase-specific checklist confirming that:

* [ ] Every acceptance criterion has implementation and validation evidence.
* [ ] All work areas and deliverables are complete.
* [ ] Required tests and quality checks pass.
* [ ] Behavior identified for preservation has been regression-tested.
* [ ] Contracts, migrations, documentation, and generated artifacts are synchronized where applicable.
* [ ] Deviations and follow-up work are documented.
* [ ] No unresolved question affects implementation, correctness, or validation.

## Risks And Open Questions

Include only concrete risks and unresolved decisions that could block or materially change implementation.

For an open question, state why it matters, what depends on it, and the recommended resolution when evidence supports one.

## Rules

* Do not invent repository facts.
* Inspect before using placeholders.
* Mark files to be created explicitly.
* Record necessary assumptions and how they will be verified.
* Prefer established project conventions.
* Make tasks concrete and independently checkable.
* Use direct verbs such as implement, update, remove, migrate, test, and validate.
* Avoid vague tasks such as “look into,” “handle,” or “address.”
* Avoid verbatim narrative duplication; use task and validation IDs for required cross-references.
* Create a Validated task plan only for a phase marked ready in its phase plan.
* For implementation handoff, instruct the agent to stop and report evidence if verified repository state conflicts with the plan.
  Do not invent a replacement design or broaden scope.
* Keep simple plans short; add detail only when complexity requires it.

## Final Plan Validation

Before returning the plan, confirm that:

* Referenced existing files, symbols, commands, and tests were verified.
* Proposed changes match repository architecture and conventions.
* Affected callers, consumers, and contracts were considered.
* Every acceptance criterion maps to work and validation.
* Source proposal and phase criteria remain traceable through task and validation IDs.
* Tasks are ordered by their actual dependencies.
* Risks and assumptions are explicit.
* Another coding agent could begin without repeating the initial investigation.

If any check fails, correct the plan or mark it Draft or Blocked.
