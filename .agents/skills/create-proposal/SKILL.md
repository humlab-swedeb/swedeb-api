---
name: create-proposal
description: Create or revise a decision-focused software design proposal. Use when the user asks to draft, write, create, or update a proposal. Do not use for phase plans, task plans, implementation checklists, or implementation work.
---

# Create a Proposal

Create or revise one decision-focused proposal for the requested change.

The user's instructions take precedence over this skill. Follow applicable repository and directory-specific instructions according to their defined precedence. If an instruction conflict prevents completion, report it instead of guessing.

## Inputs

Determine from the user's request or current conversation:

- the change or problem the proposal should address
- the repository-relative target document

Infer proposal details when the conversation or verified repository content establishes them.

An explicit target from the user or the current conversation takes precedence. Otherwise, place a new proposal under `docs/proposals/` and name it descriptively, following [Proposal document structure](../../../.github/instructions/proposal-document-structure.instructions.md). If the proposed work cannot be named specifically enough, ask one concise clarifying question.

Preserve the path of an existing proposal when updating it. If a user-supplied target does not follow the convention, confirm the path before writing.

Do not treat labels, examples, or placeholder text as input values.

## References

Before drafting, read:

- [Proposal writing guide](../../../.github/instructions/proposal-writing-guide.instructions.md)
- [Proposal document structure](../../../.github/instructions/proposal-document-structure.instructions.md)
- [Proposal template](../../../docs/templates/PROPOSAL_TEMPLATE.md)
- the repository [AGENTS.md](../../../AGENTS.md)
- [Writing style](../../../.github/instructions/writing-style.instructions.md)

Use the repository instructions and template for project-specific rules if they differ from the skill references.

## Proposal Standard

- Keep the proposal focused on one decision. State the problem first, explain why it matters, and recommend a concrete approach.
- Define scope and non-goals. Explain important alternatives, risks, and tradeoffs without turning the proposal into an implementation plan.
- Keep it as short as possible while giving readers enough detail to decide. Include optional sections only when they help with the decision.
- Distinguish verified current behavior from proposed behavior. Mark unverified claims as assumptions or open questions.
- Make acceptance criteria observable and checkable, using stable IDs such as `P-AC-1`.
- When a phase plan will follow, include a concise Planning Handoff after Acceptance Criteria with confirmed decisions, constraints and behavior to preserve, expected validation outcomes, and open questions with the phase by which each must be resolved.

## Workflow

1. Confirm the request calls for a proposal and identify the decision it must support.
2. Inspect the repository only far enough to verify relevant behavior, feasibility, interfaces, constraints, and migration risks. Do not perform task-level implementation discovery.
3. Select the target path using the naming rule and preserve an existing proposal's path when revising it.
4. Draft the complete proposal using the required structure, omitting optional sections that do not help the decision.
5. Check that claims are labeled as verified facts, assumptions, or open questions; acceptance criteria are checkable; and planned behavior is not described as current behavior.
6. Include a Planning Handoff when later work will require a phase plan.
7. Keep the proposal in `docs/proposals/`. Do not create an index; update an existing index only if one is present and the requested change requires it.

## Limits

- Produce one proposal only.
- Do not create a phase plan, task plan, implementation checklist, or code changes.
- Do not perform a file-by-file implementation inventory.
- Do not invent repository facts, paths, commands, APIs, tests, owners, or dates.
- Use `TBD` only when a required field cannot be meaningfully completed.
- Repository inspection outside the target document must be read-only.
- Modify only the target document unless the user explicitly requests related documentation changes.
- If the target already exists, update it only when the user clearly requested an update. Otherwise, ask before replacing it.

## Output

When editing is authorized and filesystem tools are available:

1. Write the proposal to the target document.
3. Return a concise completion message with the target path.

Otherwise, return the completed proposal Markdown.
