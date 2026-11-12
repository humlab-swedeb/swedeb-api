---
description: "Use when writing or updating design proposals. Covers style, naming, and Copilot workflow for proposals; structure lives in proposal-document-structure.instructions.md."
applyTo: "docs/proposals/**/*.md"
---
# Proposal Writing Guide

Use this guide when writing or updating design proposals for this repository.

## Style

- Be clear, succinct, and matter-of-fact.
- Write problem-first, not background-first.
- Follow KISS: prefer simple explanations and simple wording.
- Follow DRY in prose: do not restate the same point in multiple sections.
- Use direct, concrete language.
- Keep sentences short.
- Use short sections with clear headings.
- Avoid fluff, hype, repetition, and vague statements.
- Include only relevant detail.
- Every sentence should add information.
- Stop when the decision is clear; do not expand a proposal into general documentation.

## Default Standard

- A proposal should be as short as possible while still being precise.
- Prefer focused documents over broad ones.
- Explain the problem, the recommendation, and the tradeoffs before implementation detail.
- Include enough technical detail to support the decision, not enough to replace the implementation work.
- If a section does not help the reader decide, cut it.

## What A Proposal Should Do

- State the problem precisely.
- Explain why the problem matters now.
- Define scope and non-goals.
- Recommend a concrete path forward.
- Call out tradeoffs, risks, and open questions.
- Make implementation and validation expectations clear enough for follow-up work.
- Give solution-level acceptance criteria stable IDs such as `P-AC-1`.

## What A Proposal Should Not Become

- Do not pad the document with background that does not affect the decision.
- Do not mix multiple unrelated decisions into one proposal.
- Do not hide the recommendation behind neutral brainstorming.
- Do not add sections just because a template has them.
- Do not explain obvious context the intended readers already know.

## Structure

Follow the required proposal shape in [proposal-document-structure.instructions.md](./proposal-document-structure.instructions.md) and the template at [docs/templates/PROPOSAL_TEMPLATE.md](../../docs/templates/PROPOSAL_TEMPLATE.md).

Keep the shape lean: use only the sections that earn their place and stop once the decision is clear. For work that will use a phase plan, add a compact `Planning Handoff` after Acceptance Criteria. State confirmed decisions, constraints and behavior to preserve, expected validation outcomes, and open questions with the phase by which each must be resolved. For major efforts, link to a separate phase plan instead of embedding a full execution document.

## Naming

- Use filenames that describe the actual scope of the proposal.
- Prefer specific names over generic ones.
- Avoid naming a proposal after an implementation detail if the proposal is really about a broader product or workflow change.

## Working With Copilot

- If you want strict adherence, explicitly reference this guide and the proposal template when asking for a new proposal.
- If proposal-writing rules are also captured in repo instructions, you do not need to repeat them every time.
- **Keep proposal work focused.** Inspect the repository only far enough to support a decision about current behavior, feasibility, interfaces, constraints, or migration risk. Do not perform the task-level inventory required for a phase task plan.
- **Label unverified claims.** When repository inspection is not warranted or cannot establish a claim, record it as an assumption or open question instead of presenting it as current behavior.
- **Draft in a single pass.** Do not iterate section by section across multiple turns. Ask the user one clarifying question if needed, then produce the full draft.

## Practical Rule Of Thumb

When in doubt, optimize for:

- high problem-focused precision
- simple wording
- low repetition
- minimal but sufficient structure
- a clear recommendation
