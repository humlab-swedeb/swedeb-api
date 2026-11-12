---
name: move-proposal
description: Move a Swedeb API proposal or related change-request document within docs/proposals, updating links and any existing index. Use when asked to archive, defer, or group a proposal. Do not use to write, review, or implement one.
---

# Move A Change-Request Document

Move one proposal file or topic folder under `docs/proposals/`, preserve its content, and keep relative links valid.

## Destinations

| User request | Destination |
|---|---|
| `done` | `docs/proposals/done/` |
| `candidate`, `future`, or `onhold` | `docs/proposals/candidates/` |
| `subfolder` | `docs/proposals/<TOPIC>/<TOPIC>.md` for a standalone file |

An explicit source or destination path takes precedence. Preserve the source shape when moving a folder. If both a topic file and folder exist, use the folder only when it is clearly the requested source; otherwise ask.

## Workflow

1. Resolve the exact source and destination and run `git status --short`. Preserve existing changes.
2. Read the source status and links. Search for inbound references to its old path and topic under `docs/`, excluding the source subtree. Check the nearest existing README only if it indexes this document.
3. Move only the requested file or folder. Update relative links inside moved files and inbound references from files that remain in place. Keep `../` depth unchanged in inbound links unless their referring file also moves.
4. Update an existing index only if it has an entry for the moved document. The current `docs/proposals/` tree has no required root index; do not create one as part of a move.
5. If the document has a status section, change it only when requested and supported by verified facts. Do not claim implementation or validation that is not evidenced.
6. Validate relative links in the moved Markdown files with the bundled [relative-link checker](scripts/check_relative_links.sh). Re-run it after any link repair.
7. Confirm the old path is gone and inspect `git status --short --find-renames`.

When a move changes directory depth, recompute outbound relative links from the new file location. Do not alter fragment-only, root-relative, or external links.

## Boundaries

- Move one proposal topic per invocation.
- Change only the moved documents, their affected inbound links, and an existing index entry.
- Do not rewrite proposal content beyond requested status and link updates.
- Do not commit or merge unless the user explicitly asks.
- If the exact source, destination, or status cannot be established, ask rather than guessing.

Report the destination, links updated, and link-check result.
