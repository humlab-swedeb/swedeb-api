---
description: "Use when creating or editing proposals, phase plans, task plans, handoffs, or completion notes under docs/proposals."
applyTo: "docs/proposals/**/*.md"
---
# Change-Request Document Structure

Use this guide to keep proposals and implementation plans under `docs/proposals/` distinct and traceable. Follow the user's explicit target path and preserve the location of an existing document when updating it.

## Document types

| Type | Purpose | Keep out |
|---|---|---|
| Proposal | Decide or recommend a change | Detailed execution checklists |
| Phase plan | Sequence a larger implementation or migration | File-by-file task instructions |
| Phase task plan | Break one ready phase into verified, executable tasks | Multi-phase strategy |
| Handoff | Record current state, next actions, risks, and open decisions | Unapproved decisions presented as settled |
| Completion note | Record delivered scope and validation | New active scope |

Create only the document type requested. Separate documents when a request needs more than one type unless the user explicitly asks for a combined document.

## Location and naming

- New proposals belong under `docs/proposals/`. Existing `candidates/` and `done/` folders represent current proposal states; use them only when appropriate to the request.
- Keep related phase and task plans near their source proposal. Existing flat-file conventions may be preserved; use a topic folder when it materially improves navigation for multiple related documents.
- Prefer descriptive names consistent with nearby files. Recommended suffixes are `<TOPIC>_PHASE_PLAN.md` and `<TOPIC>_PHASE_<N>_TASK_PLAN.md`.
- An explicit user or conversation target takes precedence. Do not rename or relocate an existing document as an incidental cleanup.

## Structure and traceability

- Use `docs/templates/PROPOSAL_TEMPLATE.md` for proposals. Keep optional sections only when they help the decision.
- Give proposal acceptance criteria stable IDs such as `P-AC-1`.
- Map phase criteria such as `PH1-AC-1` to their source proposal criteria and to validation milestones.
- Map task-plan criteria to concrete task IDs, validation IDs, and completion evidence.
- Link related documents with correct repository-relative links. Do not duplicate long background sections.
- Distinguish current behavior, proposed behavior, and completed work.
- Use `TBD` only for decisions or details that repository evidence and the user cannot establish.

There is no required change-request index. Do not create one unless the user requests it or the repository adds an established index.

## Before finishing

- Confirm the document type, target path, and relevant source proposal or phase.
- Check that acceptance criteria are observable and traceable where applicable.
- Ensure that completed work is supported by stated validation; do not present planned or unrun checks as passed.
- Verify relative links changed or added in the document.

`docs/proposals/` provides proposal and migration context. It is not authoritative for current runtime behavior. Ignore `docs/archive/` for current implementation decisions.
