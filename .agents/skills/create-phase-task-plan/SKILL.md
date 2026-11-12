---
name: create-phase-task-plan
description: Create a repository-verified task plan for one ready phase. Use when the user asks to create or update a phase task plan, work breakdown, implementation checklist, or execution tracker for a single phase. Do not use for proposals, phase plans, or implementation work.
---

# Create a Phase Task Plan

Create one repository-verified task plan for a single ready phase.

The user's instructions take precedence over this skill. Follow applicable repository and directory-specific instructions according to their defined precedence. If an instruction conflict prevents completion, report it instead of guessing.

## Inputs

Determine from the user's request or current conversation:

- the source proposal path
- the source phase plan path
- the selected phase identifier
- the repository-relative target document

Infer details when the conversation or verified repository content establishes them.

An explicit target from the user or the current conversation takes precedence. Otherwise, name and place the task plan according to [Change-request document structure](../../../.github/instructions/proposal-document-structure.instructions.md). If the source proposal path or phase number is unknown, ask one concise clarifying question.

Preserve the path of an existing task plan when updating it. If a user-supplied target does not follow the convention, confirm the path before writing.

Do not treat labels, examples, or placeholder text as input values.

## References

Before writing or revising a task plan, read:

- [Task plan instructions](../../../.github/instructions/task-plan.instructions.md)
- [Change-request document structure](../../../.github/instructions/proposal-document-structure.instructions.md)
- applicable repository instruction files, including `AGENTS.md`

## Workflow

1. Read the source proposal and phase plan. Confirm the selected phase is marked ready and identify its `PH*-AC-*` criteria, source `P-AC-*` criteria, fixed decisions, constraints, dependencies, and validation milestones.
2. If the phase is not ready, produce a Blocked task plan that names the blocking decision. Do not create a Validated plan.
3. Inspect the relevant project instructions, code, tests, configuration, and documentation. Trace affected callers, consumers, contracts, schemas, and data flows.
4. Produce one task plan with repository basis, findings, task IDs, validation IDs, exact targets, planned files marked `NEW`, baseline results, deliverables, and acceptance-criteria coverage.
5. Set readiness to Validated only when the plan has executable validation methods and no unresolved placeholder or decision can change implementation.

## Limits

- Produce one phase task plan only.
- Do not modify implementation, tests, configuration, or unrelated documentation.
- Preserve `PH*-AC-*` and source `P-AC-*` mappings. Map phase criteria to `T*` task IDs and `V*` validation IDs.
- Use verified repository facts. Do not invent files, symbols, commands, APIs, or test names.
- Treat Graphify as a navigation aid, not the source of truth. If it conflicts with source or tests, plan from current source and note the discrepancy.
- Repository inspection outside the target document must be read-only.
- Modify only the target document.
- If the target already exists, update it only when the user clearly requested an update. Otherwise, ask before replacing it.

## Output

When editing is authorized and filesystem tools are available:

1. Write the task plan to the target document.
2. Return a concise completion message with the target path.

Otherwise, return the completed task plan Markdown.
