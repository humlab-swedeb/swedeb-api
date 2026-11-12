---
description: "Use when creating or editing proposal-tree Markdown files in docs/proposals, including naming and locating proposals, phase plans, and task plans. Enforces document-type selection, document naming, required structure, and separation between document types."
applyTo: "docs/proposals/**/*.md"
---

# Proposal Document Structure

Use this for Markdown files under `docs/proposals/`. It keeps proposals, phase plans, task plans, handoffs, and completion notes in separate roles. Detailed style lives in the proposal, phase-plan, task-plan, and writing-style instructions. Proposal section order follows the template at [docs/templates/PROPOSAL_TEMPLATE.md](../../docs/templates/PROPOSAL_TEMPLATE.md).

Treat `docs/proposals/README.md` as the navigation index, not as a proposal or plan. Do not apply the document types, naming rules, or section shapes below to the index, and do not list the index itself.

## Document Type

Classify each file as one primary type before writing. Create separate files when a request needs more than one type unless the user explicitly asks for one combined document.

| Type | Use For | Do Not Include |
|---|---|---|
| Proposal | Deciding or recommending a change | Progress trackers or detailed execution sequencing |
| Phase plan | Sequencing a larger implementation or migration | Task-level checklists |
| Task plan | Breaking one phase into work items and definition of done | Multi-phase strategy |
| Handoff | Recording current state, next actions, risks, references, and open decisions | New decisions unless clearly labeled as recommendations |
| Completion note | Recording completed work | New active scope |

## Document Naming

Name each document from the work it covers and its role, so related files sort together and the source document is identifiable from the name.

| Type | Name | Location |
|---|---|---|
| Proposal | `<TOPIC>.md` | `docs/proposals/` |
| Phase plan | `<TOPIC>_PHASE_PLAN.md` | Beside the proposal |
| Task plan | `<TOPIC>_PHASE_<N>_TASK_PLAN.md` | Beside the phase plan |

- `<TOPIC>` is the source proposal's file name without its extension and names the work, for example `DECLARATIVE_BUSINESS_KEYS`.
- `<N>` is the phase number from the phase plan. Omit `_PHASE_<N>` when the plan has a single unnumbered phase.
- Keep a topic's documents in a folder named `<TOPIC>` when the topic has more than one document; a standalone proposal may sit directly in `docs/proposals/`.
- The status folders used in this repository are `done/` and `future/`; these and grouping folders that hold several topics do not follow the single-topic rule.
- An explicit target from the user or the current conversation takes precedence. Preserve the path of an existing document when updating it, and confirm the path before writing when a supplied target does not follow these names.

## Structures

Use these section orders unless an existing file has a stronger local pattern.

| Type | Required Shape |
|---|---|
| Proposal | Title; Status; Summary; Problem; Scope; Non-Goals; Current Behavior when needed; Proposed Design; Alternatives Considered when useful; Risks And Tradeoffs; Testing And Validation; Acceptance Criteria; Planning Handoff when a phase plan follows; compact Recommended Delivery Order when useful; Open Questions when real; Final Recommendation |
| Phase plan | Title; Summary; Problem; Scope; Current Position; Phase Plan using the phase shape below; Cross-Phase Rules; Validation Strategy; Final Recommendation when useful |
| Task plan | Phase Summary; Repository Findings; Scope; Work Breakdown; Acceptance-Criteria Coverage; Validation And Testing; Deliverables; Progress Tracker; Definition Of Done; Risks And Open Questions when relevant |
| Handoff | Title; Purpose; Current State; Completed Work; Key References; Next Actions; Risks; Open Decisions; Suggested Follow-Up Documents |
| Completion note | Title; Status; Summary; Completed Scope; Validation Performed; Remaining Follow-Up when real |

## Phase Shape

Each phase-plan phase must use this shape:

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

Prefer 3-7 phases. Use parity as an explicit measure when replacing legacy behavior. Include fallback, exception, or cutover phases for migrations when relevant.

## Cross-Document Rules

- Use relative links for repository documents.
- Prefer one clear file per decision or plan.
- When a proposal is created, add or update its row in the proposals index at `docs/proposals/README.md` with the proposal title, status, and a one-line decision summary. Leave unrelated rows unchanged. The index lists decision documents only; do not add phase plans, task plans, handoffs, or completion notes to it.
- Do not duplicate long background sections across related documents.
- Link related proposals, phase plans, task plans, or handoffs near the top.
- Make current state and planned state explicit.
- Treat unknown owners, dates, commands, and rollout details as `TBD` instead of guessing.
- Do not describe planned behavior as shipped behavior.
- Give proposal acceptance criteria stable `P-AC-<N>` IDs.
- Map each phase `PH<N>-AC-<N>` criterion to its source `P-AC-*` criterion and to a validation milestone.
- Map each phase task plan's `PH*-AC-*` criteria to task IDs, validation IDs, and definition-of-done evidence.
- Link a task plan to its source phase plan and phase when known.
- For completion notes, mark work complete only when validation is stated.

## Before Finishing

Check that:

- the document type is clear from the title and first section
- required sections for that document type are present or intentionally omitted
- planned work is not described as completed work
- acceptance criteria are checkable
- acceptance criteria retain their required source and downstream mappings
- open questions are real decisions, not filler
- related phase plans, task plans, or handoff documents are linked when they already exist
- the document name and location follow the Document Naming rule
- a newly created proposal has a row in the proposals index at `docs/proposals/README.md`

`docs/proposals/` provides proposal and migration context, not the source of truth for current runtime behavior. Ignore `docs/archive/` for current implementation decisions.
