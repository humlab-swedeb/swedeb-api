---
description: "Use when editing the root README.md. Keep it a concise project overview, quick-start entry point, and documentation guide."
applyTo: "README.md"
---
# README Instructions

## Purpose and scope

- Use `README.md` to identify the Swedeb API, summarize its main capabilities, and direct readers to authoritative documentation.
- Treat it as an entry point, not the complete development, API, design, or operations manual.
- Preserve its existing organization unless the user requests a broader rewrite.

## Content

- Keep project purpose, key capabilities, supported setup prerequisites, and primary documentation links concise.
- Keep detailed development workflow in `docs/DEVELOPMENT.md`, architecture in `docs/DESIGN.md`, runtime operations in `docs/OPERATIONS.md`, and test guidance in `docs/TESTING.md`.
- Keep endpoint request and response details in the generated FastAPI documentation at `/docs` and `/redoc`.
- Verify commands, versions, deployment details, and configuration references against current project files before changing them.
- Avoid duplicating lengthy instructions that already exist in linked documentation.

## Writing

- Use direct, factual wording. Avoid unsupported claims and marketing language.
- Keep headings plain and scannable; add a table of contents only when it materially helps navigation.
- Do not add project details from related repositories as if they were part of this repository.
