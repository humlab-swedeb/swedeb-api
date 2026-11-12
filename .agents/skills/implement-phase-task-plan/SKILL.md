---
name: implement-phase-task-plan
description: Implement a validated phase task plan or selected T* tasks without redesigning or broadening scope. Use when asked to execute, implement, or continue phase tasks and record their validation evidence. Do not use for creating proposals, phase plans, or task plans.
---

# Implement a Phase Task Plan

Implement one validated phase task plan, or selected tasks within it, using the plan as the approved implementation specification.

The user's instructions take precedence over this skill. Follow applicable repository and directory-specific instructions according to their defined precedence. If a conflict prevents completion, report it rather than guessing.

## Inputs

Determine from the user's request or current conversation:

- the repository-relative task plan document
- whether to execute the full plan or specific `T*` task IDs

Infer details only when established by the conversation or verified repository content. Do not treat examples or placeholders as input values.

An explicit target from the user or the current conversation takes precedence. Otherwise, locate the task plan near its phase plan according to [Change-request document structure](../../../.github/instructions/proposal-document-structure.instructions.md). If the task plan path or phase is unknown, or more than one candidate matches, ask one concise clarifying question.

## References

Before implementing, read:

- [Task plan instructions](../../../.github/instructions/task-plan.instructions.md)
- [Change-request document structure](../../../.github/instructions/proposal-document-structure.instructions.md)
- [Coding practices](../../../.github/instructions/coding-practices.instructions.md)
- the task plan and its linked proposal and phase plan
- applicable repository instruction files, including `AGENTS.md`

## Preconditions

1. Confirm the selected phase is marked ready in its phase plan.
2. Confirm the task plan is marked **Validated**, with no unresolved placeholder or blocking decision affecting the requested work.
3. Identify the selected `T*` tasks, their dependencies, deliverables, applicable `V*` checks, and `PH*-AC-*` / `P-AC-*` mappings. For selected tasks, confirm that prerequisite tasks are complete or within the authorized scope.
4. Verify that repository files, symbols, interfaces, dependencies, and expected behavior still match the plan's verified basis.
5. Inspect the working tree. Preserve pre-existing changes; if overlapping edits cannot be safely separated from planned changes, stop and report the conflict.

If a precondition fails, do not edit implementation files. Report the concrete mismatch and affected path, symbol, task, or criterion ID. Do not silently change the plan to make it pass.

## Workflow

1. Execute authorized `T*` tasks in dependency order. Change only the plan's named deliverables, preserving approved contracts, compatibility, migration rules, security requirements, and scope limits.
2. Make routine low-level coding choices consistent with the plan and repository conventions. Escalate any decision that would change approved behavior, architecture, interfaces, dependencies, acceptance criteria, or scope; do not redesign the solution.
3. Run the applicable `V*` checks for completed tasks. Before claiming full-phase completion, run all required phase validation checks. Record commands, outcomes, and evidence; distinguish baseline failures from failures introduced by the implementation.
4. Correct implementation-caused failures within the authorized scope, then revalidate. Report unrelated or pre-existing failures without expanding scope. Never mark failed, skipped, or unexecuted checks as passed.
5. Update the task plan's progress tracker, validation evidence, checklist, status, and deliverables after work has been verified. Preserve planned task definitions, `P-AC-*` / `PH*-AC-*` mappings, validation requirements, and design decisions.
6. Record which acceptance criteria have supporting implementation and validation evidence. Do not infer criterion satisfaction merely from completed code edits.
7. If material repository discrepancies or blocking design decisions arise, stop affected work and report them. Preserve completed work and its evidence; leave unfinished tasks explicitly incomplete.

## Limits

- Do not modify implementation, tests, configuration, or unrelated documentation outside the task plan's named deliverables. The task plan may be updated only for execution status and evidence.
- Do not overwrite, discard, stage, commit, or revert pre-existing changes unless explicitly authorized.
- Do not broaden scope, redesign the solution, or add unrelated improvements.
- Do not mark tasks, validation checks, or acceptance criteria complete without fresh supporting evidence.
- Do not invent repository facts, paths, symbols, commands, APIs, tests, or results.

## Output

Return a concise implementation report covering:

- completed, incomplete, and blocked `T*` task IDs
- changed deliverables
- applicable `V*` results, including baseline differences and unrun checks
- `PH*-AC-*` criteria supported by evidence and criteria not yet demonstrated
- remaining work or blocking discrepancies

For partial execution, report only the requested work and its dependencies; do not imply that the whole phase is complete. If execution stops, report the blocker and preserved progress.
