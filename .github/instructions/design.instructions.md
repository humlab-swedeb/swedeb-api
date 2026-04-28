---
description: "Use for DESIGN.md and other design-focused documentation in swedeb-api, including architecture, system structure, major design decisions, cross-cutting concerns, and technical rationale."
name: "Design Docs"
---
# Design Docs

## Purpose

- Use this instruction when editing `docs/DESIGN.md` or other design-focused documentation.
- Keep `docs/DESIGN.md` focused on how the system is structured, what its major components and boundaries are, how key flows work, and which technical decisions shape the design.
- Write for developers and maintainers who need to understand the architecture and design of the repository.
- Treat the current codebase, repository structure, configuration, architectural decision records, and generated API definitions as the primary source of truth.

## What belongs in `docs/DESIGN.md`

- Design purpose and intended audience
- System scope and boundaries
- High-level architecture and major components
- Key runtime flows and interactions
- Responsibilities and boundaries between modules or subsystems
- External dependencies and integration points
- Data ownership and persistence at a design level
- Cross-cutting concerns such as authentication, authorization, validation, error handling, logging, configuration, security, and performance
- Major technical constraints and assumptions
- Important design decisions and their consequences
- Known tradeoffs, limitations, and technical debt
- Pointers to related development, testing, and operations documentation

## What does not belong in `docs/DESIGN.md`

- Full local setup instructions or contributor workflow
- Production deployment steps, rollback procedures, backup procedures, or incident handling
- Exhaustive endpoint-by-endpoint API reference that should come from generated API docs or code
- Low-level code walkthroughs that are better kept close to the code
- Detailed unit-test patterns, fixture catalogs, or CI pipeline behavior
- Historical material that only matters for archived or replaced designs unless explicitly marked as historical context

Those topics belong in development documentation, operations documentation, testing documentation, generated API documentation, or code-level documentation.

## Scope boundaries

- `docs/DESIGN.md`: architecture, system structure, component responsibilities, key flows, cross-cutting concerns, constraints, and major design decisions
- `docs/DIAGRAMS.md`: visual design diagrams — sequence diagrams, state diagrams, component diagrams, and other structural or behavioral visualizations of the active runtime; historical diagrams belong in `docs/archive/`
- `docs/DEVELOPMENT.md`: contributor workflow, local setup, common commands, and day-to-day development practices
- `docs/TESTING.md`: test strategy, test levels, quality expectations, validation workflow, and repository-specific testing guidance
- `docs/OPERATIONS.md`: runtime environments, deployment, release flow, rollback, recovery, observability, and operational dependencies
- `README.md`: short overview and entry-point links, not the full design guide
- `docs/archive/`: historical reference only; do not treat archived docs as the source of truth for current design

## Writing rules

- Keep the document scoped, concise, and practical.
- Include enough detail for a contributor or maintainer to understand how the system is organized, how its main parts interact, and which design decisions matter when changing the code.
- Prefer concrete repository-specific wording: modules, packages, services, boundaries, data stores, integrations, interfaces, flows, and constraints.
- Prefer short sections, concrete bullets, and focused explanations over long narrative prose.
- Avoid restating implementation detail that is already obvious from the code unless it clarifies an important design boundary, flow, or constraint.
- Distinguish current design from planned or aspirational design.
- Distinguish stable architectural decisions from incidental implementation detail.
- Distinguish design description from design rationale when ADRs or separate decision records exist.
- Describe external interfaces and dependencies at the level needed to understand structure and behavior, not as exhaustive operational or API reference material.
- Every section should answer a real design question related to structure, boundaries, flows, constraints, responsibilities, or technical tradeoffs.
- If a section does not improve understanding of the system's design, shorten it or remove it.
- When part of the design is intentionally not finalized yet, keep the section present and mark it clearly as `TBD` instead of inventing structure or rationale.
- Do not document endpoint request/response details here; link to generated API docs instead.

## Concision and size expectations

- Keep `docs/DESIGN.md` scoped, concise, and useful as the main design overview and entry point.
- Target length: about 1000-2200 words.
- Prefer staying under 3000 words.
- If the document needs to grow beyond that, move detailed subsystem material into focused companion design notes or ADRs and keep `docs/DESIGN.md` as the concise overview and entry point.

## Recommended section shape

- Purpose
- Audience and scope
- System context and boundaries
- High-level architecture
- Components and responsibilities
- Key flows and interactions
- Data and persistence design
- Cross-cutting concerns
- Constraints and assumptions
- Design decisions and tradeoffs
- Known limitations or technical debt
- Related documents

## Sources to trust

- `api_swedeb/`
- `tests/`
- `pyproject.toml`
- `config/`
- `docker/`
- `AGENTS.md`
- `README.md`
- `docs/DEVELOPMENT.md`
- `docs/TESTING.md`
- `docs/OPERATIONS.md`
- Generated OpenAPI schema and FastAPI route definitions

Verify design claims against the current codebase, repository structure, configuration, ADRs, and generated API definitions before documenting them.