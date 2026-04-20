---
description: "Use for DEVELOPMENT.md and other developer-facing documentation in swedeb-api, including local setup, contributor workflow, development practices, code quality checks, and day-to-day implementation guidance."
name: "Development Docs"
---
# Development Docs

## Purpose

- Use this instruction when editing `docs/DEVELOPMENT.md` or other developer-facing documentation.
- Keep `docs/DEVELOPMENT.md` focused on how contributors set up, understand, modify, validate, and extend the codebase during day-to-day development.
- Write for developers working on the repository, not for operators of deployed environments.
- Treat the current repository structure, configuration, scripts, tool definitions, and documented development conventions as the primary source of truth.

## What belongs in `docs/DEVELOPMENT.md`

- Development purpose and intended audience
- Prerequisites and required tools
- Local setup and bootstrap steps
- Local configuration needed for development
- Project structure and code organization
- Common development commands
- Coding conventions and repository-specific practices
- Linting, formatting, type-checking, and other code quality checks
- Local validation workflow before commit or pull request
- Database or migration workflow, if relevant to development
- Debugging and troubleshooting guidance for common development issues
- Pointers to related design, testing, and operations documentation

## What does not belong in `docs/DEVELOPMENT.md`

- Full production deployment or release procedures
- Runtime operations, rollback, backup, or incident procedures
- High-level architecture rationale that belongs in design documentation
- Endpoint-by-endpoint API reference that should come from code or generated API docs
- Exhaustive unit-test theory or detailed test-case catalogs
- General Git or Python tutorials unrelated to repository-specific workflow

Those topics belong in operations documentation, design/architecture documentation, testing documentation, generated API documentation, or code-level documentation.

## Scope boundaries

- `docs/DEVELOPMENT.md`: contributor workflow, local setup, repository conventions, common commands, and day-to-day development practices
- `docs/OPERATIONS.md`: runtime environments, deployment, release flow, verification, rollback, recovery, and operational dependencies
- `docs/DESIGN.md`: architecture, major design decisions, system structure, and rationale
- `docs/TESTING.md`: test strategy, test levels, quality goals, and repository-specific testing guidance
- `README.md`: short project overview and entry-point links, not the full developer guide
- `docs/archive/`: historical reference only; do not treat archived docs as the source of truth for current development practice

## Writing rules

- Keep the document scoped, concise, and practical.
- Include enough detail for a contributor to set up the project, run it locally, validate changes, and follow expected repository practices without unnecessary background reading.
- Prefer concrete repository-specific wording: commands, scripts, file paths, config files, tools, and validation steps.
- Prefer short sections, concrete bullets, and explicit procedures over long narrative prose.
- Avoid repeating information already defined in scripts, config, workflow files, or tool configuration when a short explanation plus a reference is enough.
- Distinguish one-time setup from day-to-day development workflow.
- Distinguish local development configuration from runtime or deployment configuration.
- Distinguish developer validation steps from CI pipeline behavior.
- Keep repository-specific conventions explicit when they differ from generic Python or FastAPI practice.
- Include commands only when they are part of the supported development workflow.
- Every section should answer a real developer question related to setup, editing, validating, debugging, or contributing.
- If a section does not support developer action, shorten it or remove it.
- When a process is intentionally not defined yet, keep the section present and mark it clearly as `TBD` instead of inventing process.

## Concision and size expectations

- Keep `docs/DEVELOPMENT.md` scoped, concise, and useful as the main developer guide and entry point for day-to-day contribution.
- Target length: about 800-1800 words.
- Prefer staying under 2500 words.
- If the document needs to grow beyond that, move detailed or specialized guidance into focused companion documents and keep `docs/DEVELOPMENT.md` as the concise overview and entry point.

## Recommended section shape

- Purpose
- Audience and scope
- Prerequisites
- Local setup
- Local configuration
- Project structure
- Common development commands
- Code quality checks
- Development workflow
- Database and migration workflow
- Debugging and troubleshooting
- Related documents

## Sources to trust

- `README.md`
- `pyproject.toml`
- `requirements*.txt`
- `.python-version`
- `.github/workflows/`
- `.github/scripts/`
- `Makefile`
- `docker/`
- `config/`
- `AGENTS.md`
- `docs/DESIGN.md`
- `docs/TESTING.md` TBD
- `docs/OPERATIONS.md`

Verify development claims against current scripts, config, tool definitions, and repository structure before documenting them.