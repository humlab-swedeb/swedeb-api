# Change Request: Ticket Download URL Retrieval Page

## Status

- **Ready to implement** — depends on `TICKET_BASED_BULK_ARCHIVE_GENERATION.md`, which is complete on the backend
- Scope: User-facing retrieval URL for generated download artifacts
- Goal: Let users return to a stable link that shows archive/job status and exposes the completed download for a limited time

### Foundation provided by the implemented bulk archive generation

The following infrastructure from `TICKET_BASED_BULK_ARCHIVE_GENERATION.md` is already in place and does not need to be re-implemented here:

| Component                                                                             | Status |
|---------------------------------------------------------------------------------------|--------|
| `BulkArchiveFormat`, `ArchivePrepareResponse`, `ArchiveTicketStatus` schemas          | ✅ Done |
| `TicketMeta` with `source_ticket_id`, `archive_format`, `artifact_path`, `expires_at` | ✅ Done |
| `ResultStore`: archive artifact path, `store_archive_ready()`, TTL, cleanup, capacity | ✅ Done |
| `ArchiveTicketService`: `prepare()`, `execute_archive_task()`, `get_status()`         | ✅ Done |
| Celery task and `dependencies.py` wiring                                              | ✅ Done |
| Tool-specific status and download endpoints (word trend speeches, speeches)           | ✅ Done |
| HTTP error responses without internal stack traces                                    | ✅ Done |
| Artifact access gated on ticket state; 409 for pending, 404 for missing/expired       | ✅ Done |
| UUID-based ticket IDs with sufficient entropy                                         | ✅ Done |

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

## User Experience Design

### UX Principle

The inline polling flow is the primary path — the user stays on the page and the download starts automatically when ready. The retrieval URL is the fallback for tab-close, network loss, or sharing, not an alternative primary flow.

### Flow 1 — Normal: user stays on the page

1. User clicks the download button on a tool page (word trends, speeches, or n-grams).
2. The button immediately changes to a progress indicator with text like _"Preparing archive… (this may take a minute)"_ and a spinner. The button is disabled.
3. The frontend polls the status endpoint every 2 s in the background.
4. A small **"Copy retrieval link"** icon appears next to the spinner. Clicking it copies the retrieval URL to the clipboard with a brief confirmation toast: _"Link copied — you can return to this download later."_
5. When polling reports `ready`, the download starts automatically (browser `<a download>` trigger) and the button resets.
6. If polling reports `error`, the spinner is replaced with an inline error message and a **"Try again"** button.

### Flow 2 — Recovery: user closed the tab or lost the connection

1. User re-opens the retrieval URL (from clipboard, browser history, or a shared link).
2. The frontend route `/download/{archive_ticket_id}` renders one of four states:

| State | What the user sees |
|---|---|
| **Pending** | Spinner + _"Your archive is still being prepared."_ + estimated expiry time + auto-refresh every 5 s |
| **Ready** | Prominent download button + format, speech count if available, expiry countdown (_"Available until HH:MM"_) |
| **Failed** | Error message + _"Please return to the search and start a new download."_ + link back to the tool |
| **Expired** | _"This download link has expired."_ + link back to the tool + guidance to re-run the query |

### Flow 3 — Sharing: researcher sends the link to a colleague

Same rendering as Flow 2. Since ticket IDs are UUID-based, the URL functions as an unguessable bearer token for the TTL window. No login is required. The page must make the expiry time clearly visible.

### Retrieval URL display timing

The retrieval URL and copy button should appear immediately after the `POST 202` response, before the archive is ready. A pending link is valid and can be shared.

### Retrieval page expiry state

The retrieval page returns `200` with a clear expiry message when the ticket is missing or expired, so the user sees a helpful page rather than a browser error. The machine-facing `/archive/download/{id}` endpoint continues to return `404` for missing/expired tickets.

## Key Decisions

The following open questions are resolved. Record any future changes here.

| Question | Decision |
|---|---|
| Who serves the retrieval page? | **Frontend** — Vue/Quasar route `/download/:id` calling the existing JSON status and download endpoints. Consistent with app style; no backend HTML rendering needed. |
| Bearer link vs signed URL vs session-bound? | **Bearer link (UUID token)** — UUID ticket IDs are high-entropy enough to be unguessable. No authentication is enforced on Swedeb today, so session-bound links add complexity without benefit. Signed URLs add dependency complexity; revisit if auth is added. |
| Show retrieval URL before archive is ready? | **Yes** — show and allow copying the retrieval URL immediately after POST 202. A pending link is valid. |
| Auto-refresh interval on retrieval page (pending)? | **5 s** on the standalone retrieval page; **2 s** for inline polling while the user is actively waiting on the tool page. |
| Expired ticket: `404`, `410 Gone`, or `200`? | **`200` with expiry message on the retrieval page**; `404` from the API download endpoint (machine path). The frontend catches 404 on the retrieval route and renders the expired state. |

## Open Questions

~~Should the `retrieval_url` field be constructed in `ArchiveTicketService.prepare()` or injected by the router from the request base URL?~~ **Resolved**: constructed in the router, which has access to `Request.base_url`. The service sets `expires_at` from the created `TicketMeta` and returns it in the prepare response. The router adds `retrieval_url` via `model_copy()` after calling the service.

## Implementation Checklist

### Backend — API Schema and Endpoints

- [x] Add `retrieval_url` and `expires_at` fields to `ArchivePrepareResponse` in `api_swedeb/schemas/bulk_archive_schema.py` (`expires_at` is already on `ArchiveTicketStatus` but not on the prepare response)
- [x] Machine-facing status endpoint — tool-specific equivalents (`/v1/tools/word_trend_speeches/archive/status/{id}` and `/v1/tools/speeches/archive/status/{id}`) already exist and return `ArchiveTicketStatus` JSON
- [x] Machine-facing download endpoint — tool-specific equivalents (`/v1/tools/word_trend_speeches/archive/download/{id}` and `/v1/tools/speeches/archive/download/{id}`) already exist
- [x] Add `GET /v1/downloads/{download_ticket_id}` endpoint (JSON status; frontend Vue route serves the HTML page)
- [x] Register new download-page endpoint in `downloads_router.py` (new file); registered in `app.py`
- [x] Inject archive service via `Depends()`; `get_archive_ticket_service` is already wired in `dependencies.py`

### Backend — Service and Ticket Logic

- [x] Read ticket state from the existing store without starting new work — `ArchiveTicketService.get_status()` already does this
- [x] Resolve ticket state into four states — `TicketStatus` covers pending, ready, and error; missing/expired tickets return 404 from the download endpoints
- [x] Gate file serving on ticket state and expiry time — already enforced in the download endpoints (409 for pending, 404 for missing/expired)
- [x] Construct `retrieval_url` from base URL and ticket ID when a long-running job is accepted — injected by the router via `Request.base_url`, set on response with `model_copy()`
- [x] Ticket ID entropy — UUID-based ticket IDs already used

### Backend — Configuration and Security

- [x] Decided: bearer link (UUID token) — UUID ticket IDs have sufficient entropy; no auth on Swedeb today; revisit if auth is added
- [x] Artifact access stops at ticket expiry — already enforced by `ResultStore` and download endpoint logic
- [x] Error responses do not expose internal stack traces — already enforced via `HTTPException` pattern throughout
- [x] No new config keys required — existing `result_ttl_seconds` and `max_artifact_bytes` apply

### Frontend Integration

- [x] Decided: retrieval page served by Vue frontend at `/download/:archiveTicketId` under `MainLayout`; calls `GET /v1/downloads/{id}` for status and `GET /v1/downloads/{id}/download` for file
- [x] Show or copy the retrieval URL in frontend download feedback — "Copy retrieval link" button appears while zip download is in progress in both `wordTrendsSpeechTable.vue` and `speechesTable.vue`
- [x] Implement the four-state retrieval page (`src/pages/DownloadRetrievalPage.vue`): pending/spinner, ready/download button, failed/error, expired/message
- [x] Auto-refresh for the pending state — 5 s interval via `setInterval` on mount, cleared on unmount
- [x] i18n keys added in both `sv/index.js` and `en-US/index.js` (`downloadRetrievalPage.*`)

### Testing

- [x] Unit test: pending ticket → status endpoint returns pending (`test_downloads_status_returns_pending_for_new_archive_ticket`)
- [x] Unit test: ready ticket → status endpoint returns ready; artifact served via download endpoint (`test_downloads_status_returns_ready_for_ready_ticket`, `test_downloads_download_returns_artifact_for_ready_ticket`)
- [x] Unit test: failed/error ticket → download endpoint returns 409 (`test_downloads_download_returns_409_for_error_ticket`)
- [x] Unit test: expired or missing ticket → 404 from both status and download endpoints
- [x] Unit test: retrieval page polling does not trigger archive regeneration (`test_downloads_status_does_not_trigger_archive_regeneration`)
- [x] Unit test: acceptance response includes `retrieval_url` and `expires_at` (`test_prepare_wt_archive_includes_retrieval_url_and_expires_at`, `test_prepare_speeches_archive_includes_retrieval_url`)
- [ ] Manual: start a long-running export, copy the URL, close the tab, reopen the URL
- [ ] Manual: refresh the retrieval page while pending
- [ ] Manual: download the artifact from the ready page
- [ ] Manual: verify expired-ticket wording after cleanup runs

### Documentation and Cleanup

- [x] Resolve all open questions and record decisions in this document
- [x] Update `docs/DESIGN.md` if the new endpoints change the active API surface or routing structure
- [x] Update `docs/OPERATIONS.md` if artifact storage, expiry behavior, or cleanup cron configuration changes
- [x] OpenAPI docstrings on all three new endpoints (`GET /v1/downloads/{id}`, `GET /v1/downloads/{id}/download`, updated prepare endpoints)

## Final Recommendation

Add a small single-ticket retrieval page for generated downloads.

Keep it intentionally narrow: one URL, one ticket, four states, and a download link only when the generated artifact is ready and unexpired.
