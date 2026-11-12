---
description: "Use when writing or editing documentation, docstrings, comments, proposals, issue or PR text, and AI coding-agent instructions."
applyTo:
  - "**/*.md"
  - "**/*.py"
---
# Writing Style

Write for the intended technical audience. Preserve accurate terminology, tone, structure, and intent unless a change is needed for clarity or correctness.

## General rules

- Use clear, concrete, behavior-first language.
- Name the action, input, output, side effect, constraint, failure case, or next step.
- Prefer direct wording over vague or overloaded terms.
- Keep sentences and sections focused. Remove repetition, but retain useful qualifications and tradeoffs.
- Preserve existing structure and technical level unless the user requests a rewrite or reorganization.
- Do not add assumptions, requirements, examples, or implementation detail that the evidence does not support.

## Documentation and proposals

- State the document's purpose before details.
- Use numbered steps for procedures and bullets for concise lists.
- State defaults, constraints, tradeoffs, and error cases where they affect the reader.
- Keep paths, identifiers, examples, code blocks, and headings accurate.
- Follow the document-specific scope and structure instructions when present.

## Code comments and docstrings

- Add comments only when they clarify non-obvious behavior or a constraint.
- Start docstrings with what the function, class, or module does.
- Describe observable behavior, inputs, outputs, and side effects; avoid vague summaries.

## PRs and issues

- Describe what changed, why it changed, expected impact, and validation actually performed.
- Avoid generic summaries such as "improved architecture" when the concrete change can be named.
