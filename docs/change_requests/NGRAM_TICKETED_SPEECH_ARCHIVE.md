# N-Gram Ticketed Speech Archive

## Status

- Proposed feature / change request
- Scope: n-gram backend archive flow, generic archive reuse, and frontend download wiring
- Goal: allow users to request a ticketed download of all speeches related to an n-gram search

## Summary

Add a dedicated async speech-archive download flow for n-gram search results.

The current n-gram feature already uses tickets for query execution and for exporting the n-gram result table. It does not support a ticketed download of the underlying speech texts. The existing speech-archive pipeline can already generate ZIP, JSONL.GZ, and CSV.GZ speech archives, but it only works when the source ticket has `speech_ids`.

The recommended design is to add an n-gram-specific archive prepare endpoint that derives `speech_ids` from the stored n-gram artifact at archive time, creates a normal archive ticket, and then reuses the existing archive generation and retrieval flow.

## Problem

Users can inspect speeches behind an n-gram row in the UI, but they cannot request a bulk download of the related speeches through the same ticketed archive pattern used elsewhere.

This leaves n-grams inconsistent with KWIC and word-trend speeches:

- the n-gram table can be exported asynchronously,
- the underlying speeches cannot,
- there is no shareable retrieval URL for the speech archive,
- there is no copy-link-downlooad-later flow for that archive.

The missing capability is not the archive writer itself. The missing capability is a way to turn an n-gram ticket into a speech-archive source.

## Scope

- Add a backend endpoint to prepare a speech archive from a ready n-gram ticket.
- Derive the archive speech set from the n-gram ticket artifact.
- Reuse the existing archive ticket lifecycle and generic `/v1/downloads/{archive_ticket_id}` endpoints.
- Add frontend store actions for starting the archive, polling status, downloading the artifact, and retaining copied retrieval links.
- Add backend and frontend tests for the new flow.

## Non-Goals

- Changing how n-gram computation works.
- Replacing the existing n-gram table archive endpoint.
- Redesigning row-level speech browsing in the n-gram UI.
- Solving both whole-search and per-row speech archive semantics in one change.

## Current Behavior

The current n-gram query flow is already ticketed. The ticket service stores an artifact with one row per n-gram result. Each row includes:

- `ngram`
- `window_count`
- `documents`

`documents` is stored as a comma-joined list of speech IDs. When page results are read back, that value is expanded into a list for the API response.

The existing archive endpoint for n-grams prepares an archive of the n-gram result table, not of speech texts.

The existing speech-archive pipeline requires the source ticket to already contain `speech_ids`. N-gram tickets do not currently store those IDs in ticket metadata when the query completes.

## Proposed Design

### Product contract

This proposal is for a whole-search speech archive.

The archive should contain the union of all speeches referenced by the ready n-gram ticket, not only the speeches for one selected n-gram row.

### API changes

Add a new endpoint:

`POST /v1/tools/ngrams/speeches/archive/{ticket_id}`

This should:

1. validate that the n-gram source ticket exists and is ready,
2. load the stored n-gram artifact,
3. derive the union of speech IDs from the `documents` column,
4. create an archive ticket with those `speech_ids`,
5. return `ArchivePrepareResponse` with `retrieval_url`,
6. schedule archive generation through the existing archive pipeline.

The existing generic download endpoints remain unchanged:

- `GET /v1/downloads/{archive_ticket_id}`
- `GET /v1/downloads/{archive_ticket_id}/download`
- `POST /v1/downloads/{archive_ticket_id}/copy-link`

### Backend behavior

Add a small n-gram-specific prepare service rather than overloading `ArchiveTicketService` with n-gram artifact parsing logic.

Recommended shape:

- `NGramSpeechesArchiveService.prepare(...)`
- optional helper for extracting ordered speech IDs from the n-gram artifact

The service should:

1. read the source artifact from the result store,
2. scan the `documents` column,
3. split comma-joined IDs,
4. discard empty values,
5. deduplicate while preserving first-seen order,
6. compute manifest metadata for the resulting speech set,
7. create an archive ticket with `speech_ids` populated,
8. delegate archive execution to the existing speech archive machinery.

The archive generation itself should continue to use `TicketedDownloadService` through the existing archive service path.

### Data and manifest behavior

The source n-gram ticket should not be changed to eagerly store the full union of `speech_ids` during query execution.

Instead, derive the speech set only when the user asks for a speech archive.

This keeps normal n-gram tickets smaller and avoids paying archive-related cost for searches that will never be downloaded as speeches.

Manifest metadata for the derived archive should include at least:

- `source_ticket_id`
- `archive_format`
- `speech_count`
- checksum of the resolved speech set
- source query metadata

### Frontend behavior

Add a dedicated n-gram speech archive action to `src/stores/nGramDataStore.js`.

That action should:

1. call the new prepare endpoint,
2. store the returned `archive_ticket_id` and `retrieval_url`,
3. poll the generic downloads status endpoint,
4. download the archive from the generic download endpoint,
5. call `/copy-link` after a successful link copy action.

This should follow the same retrieval-link pattern already used for other async archives.

## Alternatives Considered

### Store all speech IDs on every n-gram ticket

This would let the existing archive service work unchanged, but it pushes archive-specific cost into every n-gram query. Large n-gram searches could produce a large union of speech IDs even when the user never downloads speeches.

Rejected because it increases ticket size and work on the hot path.

### Extend `ArchiveTicketService` to parse n-gram artifacts directly

This is possible, but it mixes source-type-specific extraction logic into a generic archive service that currently assumes `speech_ids` already exist.

Rejected because it weakens separation of concerns.

### Add a per-row speech archive instead of a whole-search archive

This may still be useful later, but it is a different product behavior. The current request is about all speeches related to the search.

Deferred.

## Risks And Tradeoffs

- Large n-gram searches may resolve to a large union of speeches. Archive generation time and disk usage may be significant.
- Parsing the `documents` column at archive time adds one extra pass over the stored artifact.
- Whole-search semantics may surprise users if they expected row-scoped downloads. The UI label must be explicit.
- Ordering must be defined and stable. First-seen order is simple and deterministic if artifact ordering is stable.

## Testing And Validation

- Unit-test speech ID extraction from `documents`.
- Test deduplication and first-seen order preservation.
- Test prepare failure for missing, pending, and error-state source tickets.
- Test empty-result behavior when the source ticket has no speech IDs to archive.
- Test successful archive creation and generic download flow.
- Test copied-link retention for the prepared archive ticket.
- Add frontend tests for the new store action and retrieval-link behavior if coverage exists there.

## Acceptance Criteria

- A ready n-gram ticket can be converted into a speech archive through a dedicated prepare endpoint.
- The resulting archive uses the existing generic downloads flow.
- The archive contains the union of all speeches referenced by the n-gram ticket.
- Duplicate speech IDs are removed deterministically.
- The frontend can start the archive, poll status, download the result, and retain copied retrieval links.
- Existing n-gram table export behavior is unchanged.

## Open Questions

- Should the first version support only whole-search archives, or should row-scoped speech archives be added at the same time? Answer: only whole-search for now
- What should happen when the derived speech set is empty: `409`, `422`, or an empty archive artifact? Answer: 422
- Should the checksum use first-seen order or sorted order? Answer: whatever is fastest

## Final Recommendation

Implement a dedicated n-gram speech-archive prepare flow that derives `speech_ids` from the ready n-gram artifact at archive time, then reuses the existing archive ticket and download pipeline.

This keeps the query path lean, matches the current architecture, and avoids mixing n-gram-specific parsing into the generic archive service.

## Progress Checklist

- [ ] Confirm the product contract is whole-search archive, not row-scoped archive
- [ ] Add `NGramSpeechesArchiveService`
- [ ] Add backend helper to extract ordered unique speech IDs from n-gram `documents`
- [ ] Add `POST /v1/tools/ngrams/speeches/archive/{ticket_id}`
- [ ] Reuse existing archive ticket creation and execution flow
- [ ] Return `retrieval_url` from the prepare response
- [ ] Wire frontend n-gram speech archive action in `src/stores/nGramDataStore.js`
- [ ] Add copy-link retention call for the new archive flow
- [ ] Add backend tests for prepare, extraction, archive generation, and empty-source behavior
- [ ] Add frontend validation for archive start, poll, and download flow
