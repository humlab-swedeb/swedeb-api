---
description: "Use for software changes across the repository: targeted investigation, minimal fixes, and evidence-based validation."
applyTo: "**/*"
---
# General Coding Practices

- Start with the smallest targeted search or read that can identify the likely change site.
- Check the worktree before editing. Preserve unrelated changes and integrate existing edits in files that must change.
- Prefer direct, repository-aware fixes over broad cleanup, speculative refactors, or parallel implementations.
- Investigate the root cause when behavior or requirements are uncertain.
- Keep changes narrow, readable, and consistent with nearby patterns.
- Surface errors using the repository's existing conventions. Avoid broad catches, silent fallbacks, and invalid-input returns that hide failure.
- Update documentation that directly describes changed behavior or workflow.
- Run the smallest relevant test or quality check before reporting completion. Use a broader suite when a change crosses layers or boundaries.
- Do not claim a check passed without fresh output. Report checks that failed, were skipped, or were not run.
- Verify the requirement itself, including measurable thresholds and output shape where applicable.
