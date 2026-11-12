---
name: create-change-pr
description: Prepare a scoped feature branch and pull request to dev for Swedeb API changes. Use when the user asks to publish local work through review. Do not use for promotion pull requests or PR reviews.
---

# Create a Change Pull Request

Prepare a feature branch and open a pull request targeting `dev`. The user must have asked to publish the change; this skill does not authorize merging the pull request.

## Before starting

1. Read `git status --short` and identify only the files belonging to the requested change.
2. Read the relevant diff and confirm that unrelated working-tree changes can remain untouched.
3. Confirm the branch and repository workflow. Feature changes target `dev`; environment promotions follow `dev` → `test` → `staging` → `main` and are outside this skill.
4. If the branch base or separation of pending changes is unclear, stop and ask rather than moving or staging unrelated work.

## Workflow

1. Create a feature branch from the appropriate `dev` state without discarding existing work.
2. Stage only the requested files. Never use `git add .` or stage unrelated changes.
3. Run the smallest relevant tests and checks. Run `make tidy` for Python formatting when applicable.
4. Create one Conventional Commit using imperative mood, lowercase description, no trailing period, and a subject under 72 characters. Include `Closes #<issue>` only when the change should close that issue.
5. Push the feature branch and use `gh` to open a pull request against `dev`.
6. Describe the change, rationale, and validation actually performed. Do not claim unrun checks passed.
7. Leave the pull request open for review. Do not merge it, promote branches, or force-push.

## Boundaries

- Follow [.github/instructions/github-workflow.instructions.md](../../../.github/instructions/github-workflow.instructions.md) and any applicable repository instructions.
- Do not commit credentials, `.env` files, or connection strings.
- Do not overwrite, revert, or stage pre-existing unrelated changes.
- Report the branch, commit, pull request URL, and validation performed. If any step fails, report the actual state without claiming success.
