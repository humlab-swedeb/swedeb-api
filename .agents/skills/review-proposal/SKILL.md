---
name: review-proposal
description: Independently review an existing software design proposal for problem fit, architectural correctness, feasibility, simplicity, risks, acceptance criteria, and readiness for phase planning. Use when asked to review, critique, or assess a proposal before approval or after revision. Do not use to write or revise proposals, create plans, or implement changes.
---

# Review a Proposal

Critically assess one existing proposal as a decision document. Challenge its recommended design when warranted; do not merely check template compliance.

The user's instructions take precedence over this skill. Follow applicable repository and directory-specific instructions according to their defined precedence. Report conflicts that prevent a reliable review.

## Inputs

Determine from the user's request or current conversation:

- the proposal document to review
- any specific review focus or earlier findings to reassess

Infer the proposal path only from the conversation or verified repository content. If multiple plausible proposals remain, ask one concise clarifying question.

## References

Before reviewing, read:

- the complete proposal
- [Proposal writing guide](../../../.github/instructions/proposal-writing-guide.instructions.md)
- [Proposal document structure](../../../.github/instructions/proposal-document-structure.instructions.md)
- [Proposal template](../../../docs/templates/PROPOSAL_TEMPLATE.md)
- [Writing style](../../../.github/instructions/writing-style.instructions.md)
- applicable repository instruction files, including `AGENTS.md`

Use writing references to assess structure and clarity, not to discourage independent architectural criticism.

## Workflow

1. Identify the problem, proposed decision, scope, non-goals, constraints, assumptions, and expected outcomes.
2. Inspect repository code and documentation only as needed to verify consequential claims about current behavior, interfaces, feasibility, security, data integrity, compatibility, and migration. Do not perform a task-level implementation inventory.
3. Assess whether the design addresses the underlying problem, fits existing architecture, and avoids unnecessary complexity. Challenge alternatives and tradeoffs where a materially better choice may exist.
4. Check that `P-AC-*` criteria are stable, observable, testable, and cover important proposed outcomes; assess the validation strategy.
5. When phase planning will follow, assess whether the Planning Handoff preserves fixed decisions, contracts, invariants, validation expectations, and blocking open questions. Do not demand task-level implementation details.
6. Separate verified defects from plausible risks and unresolved questions. Prioritize material, actionable findings; do not manufacture findings or repeat the same issue.
7. Assess readiness for human design approval and subsequent phase planning. A review is advice, not approval.

For a re-review, evaluate whether earlier material findings were resolved and identify any new issues; do not assume prior reviewers were correct. When several reviews are supplied, compare their evidence rather than treating agreement as proof.

## Limits

- Review only; do not modify proposal files, repository state, or other artifacts.
- Do not invoke proposal-writing or implementation workflows as part of the review.
- Do not create a phase plan, task plan, implementation checklist, or code changes.
- Do not invent repository facts, paths, commands, APIs, test results, or requirements.
- Do not infer approval from an absence of findings; the developer retains decision authority.
- Avoid cosmetic feedback unless unclear writing affects the decision.

## Output

Return a concise review containing:

1. **Overall assessment** — design strengths, principal concerns, and confidence limits.
2. **Findings** — ordered by Critical / High / Medium / Low. For each: location, issue and impact, concrete recommendation, and confidence (High / Medium / Low). Cite repository evidence or state what remains unverified.
3. **Planning readiness** — `Ready`, `Ready with minor revisions`, `Revision required`, `Decision required`, or `Inconclusive`, with a brief justification.

If there are no actionable findings, state that explicitly. Suggest only the smallest set of changes needed to improve the decision; leave proposal revision to `create-proposal` after the developer selects findings to address.
