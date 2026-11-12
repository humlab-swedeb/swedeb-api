---
description: "Use when creating or updating phased implementation plans, delivery sequencing documents, migration phase plans, or other multi-phase execution plans. Covers structure, section priority, phase ordering, cross-phase rules, and validation strategy."
---

# Copilot Instructions: Phase Plans

When asked to create a phase plan, generate a concise Markdown implementation plan that breaks a larger development effort into ordered phases.

A phase plan is broader than a task plan. It explains the path from current state to target end state. It should define the sequence of phases, goals, focus areas, acceptance criteria, cross-phase rules, and validation strategy.

For major efforts, treat the phase plan as a separate document from the proposal or change request by default. The proposal is the decision document. The phase plan is the execution-sequencing document. Only embed a compact delivery-order section inside a proposal when the work is small enough that a separate phase plan would add ceremony without clarity.

Use the proposal as the source of approved decisions and `P-AC-*` criteria. Inspect the repository only far enough to confirm current state and phase boundaries; task plans perform the file-level investigation.

## Output

Return only the Markdown phase plan unless the user asks for explanation.

Prefer lean documents. Avoid turning a phase plan into a proposal, implementation spec, or project-management tracker.

Use this structure by default:

1. Summary
2. Problem
3. Scope
4. Current Position
5. Phase Plan
6. Cross-Phase Rules
7. Validation Strategy
8. Final Recommendation

## Importance And Skip Rules

Use this priority order to avoid bloated plans:

| Section | Priority | Skip / Compress When |
|---|---:|---|
| Summary | Required | Never skip. Keep to 1-3 paragraphs. |
| Problem | Required | Compress if the goal is already obvious. |
| Scope | Required | Never skip. Include in/out boundaries. |
| Current Position | High | Compress if the user did not provide current-state details. |
| Phase Plan | Required | Never skip. This is the core output. |
| Cross-Phase Rules | Medium | Skip for small projects or if rules are obvious. |
| Validation Strategy | High | Compress if validation is not central to the work. |
| Final Recommendation | Low | Skip if the plan already ends clearly. |

Do not add extra sections unless they materially improve the plan.

Default to implementation sequencing, not staffing, scheduling, ownership, or release management, unless the user explicitly asks for those dimensions.

## Phase Plan Requirements

Create ordered phases using this format:

```markdown
### Phase N: <Phase Title>

**Goal**

<one concise goal>

**Focus**

- <focus item>
- <focus item>

**Depends On**

- <prior phase output or required decision>

**Outputs**

- <result available to a later phase>

**Acceptance Criteria**

- `PH1-AC-1` (from `P-AC-1`) <checkable outcome>

**Validation Milestones**

- `VM-1` <validation result and covered phase criteria>

**Task-Plan Handoff**

- <source criteria, fixed decisions, constraints, and blocking questions>

**Readiness**

<Ready for a task plan | Requires a named decision>
```

Each phase should represent a meaningful delivery step, not a vague theme.

Prefer 3-7 phases for most projects. Use fewer phases for small efforts and more only when the work clearly requires it.

## Rules

- Preserve the user's terminology when it appears project-specific.
- Base phases on the current state, target state, and known gaps.
- Make dependencies clear through both ordering and each phase's **Depends On** field.
- Ensure each stated gap is addressed by at least one phase.
- Give each phase acceptance criterion a stable `PH<N>-AC-<N>` ID and map it to its source `P-AC-*` criterion.
- Ensure each phase acceptance criterion is checkable, aligned with the phase goal, and covered by a validation milestone.
- Do not invent shipped functionality, commands, file paths, APIs, or ownership.
- Do not infer owners, dates, PR workflow, commands, file paths, APIs, or test names.
- Establish dependencies from proposal decisions and verified current state. Record unknown dependencies as blocking questions rather than relying on phase order.
- Distinguish proven/current behavior from planned behavior.
- Use `TBD` only where an explicit placeholder is useful.
- Keep acceptance criteria measurable.
- Prefer incremental delivery over large unvalidated rewrites.
- Include fallback, exception, or cutover phases when migration is involved.
- If the plan concerns replacing legacy behavior, use parity as a delivery measure.
- If information is missing but the goal is clear, make only structural assumptions about phase ordering or grouping and state them explicitly.
- Mark a phase as ready for a task plan only when no unresolved question can change that phase's implementation or validation.
- Do not repeat the same point verbatim across Summary, Current Position, phases, and Final Recommendation.

## Scope Guidance

The Scope section should say what the plan covers and what it does not cover.

For proposal-backed work, keep the scope here delivery-oriented. Do not restate the full proposal rationale unless it affects phase boundaries.

Example:

```markdown
This plan covers the backend implementation phases needed to move from the current validated slice to practical feature parity.

It does not include frontend rollout, staffing, or release scheduling.
```

## Current Position Guidance

Summarize current state as bullets.

Include proposal decisions and verified repository facts. Label anything else as an assumption or open question.

Good bullets:

- the new runtime is integrated for one validated slice
- result-set generation is not yet migrated
- the legacy runtime remains authoritative outside supported slices

Avoid unsupported claims.

Keep this section short. Its job is to anchor the phases, not to retell the full history.

## Cross-Phase Rules

Include this section when the work spans migration, parity, refactoring, or architecture replacement.

Use concise rules such as:

- validate one focused slice before grouped promotion
- keep legacy behavior authoritative where parity is not proven
- keep documentation aligned with shipped behavior
- treat unsupported cases as explicit exceptions

Keep rules operational. If a rule does not affect sequencing, validation, or phase boundaries, cut it.

## Validation Strategy

Include layered validation when relevant:

- unit tests for isolated contracts
- focused live or fixture-based comparisons for new slices
- grouped regression for promoted behavior
- legacy comparison tests where parity is required
- type checking and CI where applicable

For each phase, map validation milestones to `PH*-AC-*` criteria and state the expected result. Exact commands, test files, fixtures, and assertions belong in the phase task plan.

Do not invent exact commands. Use placeholders only in phases that are not ready for task planning.

## Style

Use concise, direct language.

Avoid verbose rationale and generic project-management filler.

Treat the phase plan as a maintained working document. Keep it compact enough that it can be updated as phases advance.

Prefer:

```markdown
**Goal**

Reach practical parity for legacy discrete facet content generation.
```

Avoid:

```markdown
**Goal**

Think through and explore how we might eventually support more facets.
```

## Quality Checklist

Before returning the plan, verify that:

- the current state is explicit
- the target state is explicit
- the document stays within its role as a sequencing plan rather than a proposal
- phases are ordered by dependency
- each known gap is covered by at least one phase
- each phase has a goal, focus, and acceptance criteria
- each phase states dependencies, outputs, readiness, and task-plan handoff information
- acceptance criteria have stable IDs, source proposal criteria, and validation milestones
- no phase marked ready has a blocking decision or dependency
- unsupported or deferred work is not hidden
- planned support is not described as already shipped
- the plan is compact enough to be maintained
