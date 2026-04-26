# Change Request: Ticket Download URL Retrieval Page

## Status

- Proposed feature / change request
- Scope: User-facing retrieval URL for generated download artifacts
- Goal: Let users return to a stable link that shows archive/job status and exposes the completed download for a limited time

## Summary

Add a ticket-based download URL page for long-running generated data exports.

When a user starts a long-running download job, the system should return a URL that can be opened later. The page behind that URL should show one of four states: in progress, ready with a download link, failed with an error message, or expired. This gives users a recoverable workflow for exports that take longer than a normal browser request.

## Problem

Large generated downloads can take long enough that users may navigate away, close a tab, lose network connection, or assume the download failed.

The current download interaction is request-bound. If the browser request fails before the generated file is returned, the user has no stable place to return to. Ticket and Celery infrastructure already support asynchronous work, but users still need a simple retrieval surface for generated artifacts.

## Scope

This proposal covers:

- a user-facing URL for one generated data ticket
- a minimal status page for that URL
- download availability during the ticket TTL window
- clear expired and failed states
- integration with archive/download tickets created by long-running jobs

## Non-Goals

This proposal does not cover:

- changing query execution semantics
- making generated artifacts permanent
- adding account-based download history
- adding collaborative sharing controls
- replacing API status endpoints used by the frontend
- adding byte-level browser download progress

## Proposed Design

When a long-running export is accepted, return both the ticket ID and a retrieval URL.

Example response:

```json
{
  "ticket_id": "archive-ticket-id",
  "status": "pending",
  "expires_at": "2026-04-26T12:00:00Z",
  "retrieval_url": "https://api.example.org/v1/downloads/archive-ticket-id"
}
```

The retrieval URL should resolve to a simple page with four possible states.

### Page States

1. **Task in progress**
   - Show that the export is still being prepared.
   - Show the expiry time if known.
   - Refresh automatically or provide a manual refresh action.

2. **Download ready**
   - Show a download link for the generated artifact.
   - Show metadata such as format, speech count, generated time, and expiry time.
   - Do not regenerate the artifact when the page is opened.

3. **Error**
   - Show a clear error message.
   - Include retry guidance if the original query can be rerun.
   - Avoid exposing internal exception details.

4. **Expired**
   - Show that the ticket or artifact is no longer available.
   - Explain that the export must be started again.

### API Shape

Add a stable retrieval endpoint:

```http
GET /v1/downloads/{download_ticket_id}
```

The endpoint can return an HTML page directly, or it can serve a minimal shell page that calls JSON status endpoints.

Keep machine-oriented endpoints separate:

```http
GET /v1/downloads/{download_ticket_id}/status
GET /v1/downloads/{download_ticket_id}/file
```

The `/file` endpoint should serve the completed artifact only when the ticket is ready.

### Backend Behavior

The retrieval page should read ticket state from the same store used by the archive-generation ticket.

It should not start new work. It should only report state and provide the completed artifact link when available.

The generated artifact should remain available until the ticket expiry time. After expiry, the page should no longer expose the file.

### Frontend Behavior

When a long-running export starts, the frontend should show or copy the retrieval URL.

The user-facing page should be intentionally small. It only needs the four states in this proposal. It should not become a full results page or file manager.

## Security And Access

The ticket ID must be high entropy enough to act as an unguessable bearer token if no user authentication is enforced.

The page should not list other tickets or expose query data beyond the artifact metadata needed for the user to identify the export.

Open questions remain around whether retrieval URLs should be public bearer links, require the same frontend session, or support signed tokens.

## Alternatives Considered

### Only Use API Polling In The Current Page

This works while the user keeps the page open, but it does not solve tab closure, navigation, or retry after connection loss.

### Send The Final File Directly When Ready

This is simple for short jobs, but it keeps the browser workflow tied to one active request or active frontend state.

### Add A Full Download History Page

A history page may be useful later, but it requires user identity, artifact ownership, listing, and privacy decisions. A single-ticket retrieval page gives most of the recovery benefit with less scope.

## Risks And Tradeoffs

A retrieval URL creates a shareable access path to generated data. If the link acts as a bearer token, anyone with the URL can download the file until it expires.

The feature adds another user-facing state surface. Status wording, expiry behavior, and error messages must stay consistent with the ticket API.

If the page is implemented in the API service, the backend serves a small amount of HTML. If it is implemented in the frontend, deployment must route the retrieval URL correctly and the frontend must call the API status endpoints.

## Testing And Validation

Validation should cover:

- pending ticket renders the in-progress state
- ready ticket renders the download link
- ready ticket file endpoint serves the generated artifact
- failed ticket renders a safe error message
- expired or missing ticket renders the expired/not available state
- the retrieval page does not trigger archive regeneration
- the retrieval URL is included in long-running export acceptance responses
- artifact access stops after expiry

Manual validation should include:

- start a long-running export, copy the retrieval URL, close the original page, and reopen the URL later
- refresh the retrieval page while the task is pending
- download the artifact from the ready page
- verify expired-ticket wording after cleanup

## Acceptance Criteria

- Long-running export responses include a retrieval URL.
- The retrieval URL has a stable page for a single download ticket.
- The page shows exactly these user states: in progress, ready with download link, error, expired.
- Ready downloads use the generated artifact and do not rebuild it.
- Expired tickets no longer expose artifact download links.
- Error pages do not expose internal stack traces or implementation details.

## Recommended Delivery Order

1. Add retrieval URL fields to long-running export acceptance responses.
2. Add JSON status and file endpoints for download tickets.
3. Add the minimal retrieval page with the four states.
4. Integrate the retrieval URL into frontend download feedback.
5. Validate behavior across pending, ready, error, and expired tickets.

## Open Questions

- Should the retrieval page be served by FastAPI or by the frontend application?
- Should retrieval URLs be bearer links, signed URLs, or session-bound links?
- Should users be able to copy the URL before the task is ready?
- Should the page auto-refresh while pending, and at what interval?
- Should expired tickets return `404`, `410 Gone`, or a `200` HTML page explaining expiry?

## Implementation Checklist

### Backend — API Schema and Endpoints

- [ ] Add `retrieval_url` and `expires_at` fields to the archive-job acceptance response schema (`api_swedeb/schemas/`)
- [ ] Add `GET /v1/downloads/{download_ticket_id}/status` endpoint returning ticket state as JSON
- [ ] Add `GET /v1/downloads/{download_ticket_id}/file` endpoint serving the artifact only when the ticket is ready
- [ ] Add `GET /v1/downloads/{download_ticket_id}` endpoint (HTML page or shell page depending on deployment decision)
- [ ] Register new endpoints in the appropriate router (`tool_router.py` or a new `downloads_router.py`)
- [ ] Inject download service via `Depends()`; do not add corpus-level facade methods

### Backend — Service and Ticket Logic

- [ ] Create or extend a `DownloadService` that reads ticket state from the existing store without starting new work
- [ ] Resolve the ticket state into one of four states: `pending`, `ready`, `failed`, `expired`
- [ ] Gate file serving on ticket state and expiry time; return `404` or `410` after expiry
- [ ] Construct `retrieval_url` from base URL and ticket ID when a long-running job is accepted
- [ ] Ensure ticket ID entropy is sufficient to act as an unguessable bearer token

### Backend — Configuration and Security

- [ ] Decide and document bearer-link vs. signed-URL vs. session-bound access strategy (resolve open question)
- [ ] Ensure artifact access stops at ticket expiry with no bypass path
- [ ] Confirm error responses do not expose internal stack traces or exception details
- [ ] Add the new endpoints to `tests/config.yml` and `config/config.yml` if config-driven

### Frontend Integration

- [ ] Decide whether the retrieval page is served by FastAPI or by the Vue frontend (resolve open question)
- [ ] Show or copy the retrieval URL in frontend download feedback when a long-running export starts
- [ ] Implement the four-state retrieval page: in progress, ready with download link, failed, expired
- [ ] Add auto-refresh or manual refresh for the pending state (resolve interval open question)
- [ ] Add i18n keys in both `sv` and `en-US` for all four state messages

### Testing

- [ ] Unit test: pending ticket → in-progress state rendered
- [ ] Unit test: ready ticket → download link rendered; artifact served by `/file`
- [ ] Unit test: failed ticket → safe error message; no stack trace
- [ ] Unit test: expired or missing ticket → expired/unavailable state; no file access
- [ ] Unit test: retrieval page does not trigger archive regeneration
- [ ] Unit test: acceptance response includes `retrieval_url` and `expires_at`
- [ ] Manual: start a long-running export, copy the URL, close the tab, reopen the URL
- [ ] Manual: refresh the retrieval page while pending
- [ ] Manual: download the artifact from the ready page
- [ ] Manual: verify expired-ticket wording after cleanup runs

### Documentation and Cleanup

- [ ] Resolve all open questions and record decisions in this document
- [ ] Update `docs/DESIGN.md` if the new endpoints change the active API surface or routing structure
- [ ] Update `docs/OPERATIONS.md` if artifact storage, expiry behavior, or cleanup cron configuration changes
- [ ] Update OpenAPI schema comments/docstrings so `/docs` reflects the new endpoints

## Final Recommendation

Add a small single-ticket retrieval page for generated downloads.

Keep it intentionally narrow: one URL, one ticket, four states, and a download link only when the generated artifact is ready and unexpired.
