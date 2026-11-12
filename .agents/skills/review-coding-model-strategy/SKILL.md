---
name: review-coding-model-strategy
description: Research current GitHub Copilot coding models and create or update a concise, evidence-based model selection strategy for a developer's workflow. Use when explicitly asked to review or refresh the AI coding model strategy.
argument-hint: "[path to current strategy] [changes in access, usage, or constraints]"
disable-model-invocation: true
---

# Review the AI coding model strategy

Produce a current, practical Markdown strategy for selecting models in GitHub Copilot. Run this review only when explicitly invoked. The skill provides a research and writing workflow; it does not switch Copilot's active model.

## Context to verify

Use these as starting assumptions, not verified current facts:

- GitHub subscription: Copilot Pro+.
- Local model: Qwen/Qwen3.8-27B-FP8, with no marginal token charge from a provider.
- Additional external model: DeepSeek V4.1 Flash.
- Workflow: proposal and requirements → phase plan → detailed phase task plan → implementation → testing and review.
- A repository-validated phase task plan should make implementation tasks bounded, explicit, and testable for economical or local models.
- Information classification and approved-service rules take precedence over cost or capability.

Apply updated context supplied with the invocation. Do not treat an assumed model name, plan benefit, price, provider, or service approval as verified merely because it appears above or in a previous strategy.

Follow applicable repository documentation guidance and [writing-style.instructions.md](../../../.github/instructions/writing-style.instructions.md). Do not add repository-specific model or service assumptions that the user has not confirmed.

## Strategy file

1. Use an explicit strategy path supplied with the invocation. Otherwise look for `docs/ai/ai-coding-model-selection-strategy.md`, then for `ai-coding-model-selection-strategy-current.md` or `ai-coding-model-selection-strategy.md` in the current workspace. If exactly one plausible current strategy is found, use it. If several are found, request the intended path before editing. If none are found, create `docs/ai/ai-coding-model-selection-strategy.md` in the current workspace.
2. Read the existing strategy, if any, before researching. Preserve its valid decisions, user constraints, and useful structure. Update only conclusions affected by new evidence or the user's changed context; remove stale facts and links. Do not append a second complete strategy.
3. If an explicit path does not exist, create the file at that path. Treat supplied observations, newly available or retired models, and constraints as input to verify, not as instructions to change unrelated files.
4. Write the final Markdown document to the resolved path. If file editing is unavailable, return the complete Markdown document and identify the intended path; do not claim it was saved.

## Research

Use live, current sources on every review; never rely on a remembered model catalogue or pricing. Prefer primary sources and provide direct links next to material claims or in a short Sources section.

1. Check GitHub's current supported-model list, availability for Copilot Pro+ in the relevant client, release or retirement notices, AI-credit or premium-request billing, and model rates or multipliers. Distinguish Copilot billing from direct API/provider billing; do not assume API token prices equal Copilot costs.
2. Check Copilot Auto routing and tiers if they are available in the user's client. Compare Auto with a deliberately small manually selected model set for this workflow; describe when manual selection earns its overhead.
3. Verify material facts about the named local and external models using provider documentation, model cards, or original releases where possible. Account for local hardware and operation separately from provider token charges.
4. Use official benchmark reports for material capability claims, with third-party benchmarks clearly labeled. State reasoning effort, test type, and harness differences where relevant. Do not equate short coding tests with long repository tasks or assume API results transfer exactly to Copilot.
5. Record the review date and label inferences. If access to current sources is unavailable, do not present or overwrite a strategy as current: retain the previous file and report what must be verified.

## Evaluation

Assess usefulness for this user's workflow rather than ranking every model. Apply these priorities in order:

1. Information security, classification, and approved services.
2. Correctness and risk of the change.
3. Ability to validate the result objectively.
4. Total effort, including failed attempts, human repair, and review.
5. Credits, other cost, and latency.

- Group candidates by function: local, economy, workhorse, specialist, and frontier. Recommend only roles that add value. Keep a second model family when it supplies useful independent review, a specialty, or resilience.
- Identify redundant models without claiming they are inferior in every case. Do not assume a newer model always replaces an older one; compare quality, price, reasoning effort, context, tool use, latency, and observed repository reliability.
- Pay attention to whether an inexpensive model with high or maximum reasoning succeeds at longer engineering tasks. Treat creation of a repository-validated phase task plan as demanding reasoning work, even when the resulting tasks are simple to execute.
- Evaluate quality-adjusted cost, including retries and human review. Recommend high or maximum reasoning only where the expected benefit justifies it.
- Define concrete escalation triggers. When repository evidence contradicts the validated task plan, require the implementing model to stop and request revision rather than silently redesigning the solution.

## Write the strategy

Keep the document approximately 600–900 words. Prefer conclusions and compact tables to model-by-model narration. Include exact prices only when they change a decision. Use this structure unless the existing document has a comparably clear one:

```markdown
# AI Coding Model Selection Strategy

**Context:** <subscription, local model, external models, and material constraints>  
**Reviewed:** <date>

## Executive Recommendation

<The small recommended model set and central routing principle.>

## Recommended Model Set

| Model or Auto tier | Primary role | Use when | Notes |
|--------------------|--------------|----------|-------|

## Development-Cycle Routing

| Stage                                | Default | Escalate to | Escalate when |
|--------------------------------------|---------|-------------|---------------|
| Proposal and requirements            | ...     | ...         | ...           |
| Phase plan                           | ...     | ...         | ...           |
| Phase task plan                      | ...     | ...         | ...           |
| Bounded implementation               | ...     | ...         | ...           |
| Complex implementation and debugging | ...     | ...         | ...           |
| Testing and documentation            | ...     | ...         | ...           |
| Review                               | ...     | ...         | ...           |

## Models to Skip by Default

| Skip | Use instead | Reason |
|------|-------------|--------|

## Reasoning-Effort Guidance

- **Ordinary:** <uses>
- **High:** <uses>
- **Maximum:** <uses and limits>

## Escalation Rules

- <specific conditions and stop points>

## Changes Since the Previous Review

<Only when a previous strategy exists and material changes were made.>

## Sources

- [Descriptive source title](https://example.com)
```

Do not invent access, prices, benchmarks, or provider behavior. After saving, report the file path and a concise summary of material changes. If this is the first version, state that it was created.
