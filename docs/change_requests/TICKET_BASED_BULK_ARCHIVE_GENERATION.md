# Change Request: Ticket-Based Bulk Archive Generation

## Status

- Proposed change request
- Scope: Backend archive generation for large speech downloads
- Goal: Move expensive archive creation out of synchronous HTTP download requests

## Summary

Generate large speech archives as ticketed background artifacts, then serve the completed file directly.

The current archive endpoints stream and compress speech text during the download request. That works for small and medium exports, but it is a poor fit for hundreds of thousands of speeches. The recommended design is an on-demand archive-generation ticket that writes a reusable artifact, exposes status, and returns the finished file through a lightweight download endpoint.

## Problem

Large archive downloads are CPU-heavy and can take long enough that users see no clear progress before the browser download starts.

The current streaming path also repeats work on every retry. If the request is interrupted, the API has to rebuild the archive from speech IDs and speech text. ZIP and tar-based formats also add per-entry overhead when each speech is stored as a separate file.

This matters most for word-trend speech archives and broad speech-result tickets where the result may contain tens or hundreds of thousands of speeches.

## Scope

This proposal covers:

- ticket-based generation for speech text archives
- word-trend speech archive downloads
- speeches ticket archive downloads
- archive status, failure, expiry, and reuse behavior
- format selection for bulk downloads
- serving completed artifacts without recompressing them per request

## Non-Goals

This proposal does not cover:

- replacing paged table result tickets
- changing word-trend or speeches query semantics
- building a full export-format framework for all endpoints
- adding Excel as a bulk full-text export format
- changing the archived legacy speech lookup backend

## Current Behavior

`GET /v1/tools/word_trend_speeches/archive/{ticket_id}` validates an existing ready result ticket and immediately streams a ZIP archive.

The route delegates to `DownloadService.create_stream_from_speech_ids()`, which resolves speech IDs, retrieves speech text in batches, and compresses the output in the request path.

Recent profiling of the 1970-1975 export showed that `jsonl.gz` is the fastest implemented bulk format, while ZIP and tar.gz spend substantial time in per-entry archive work and compression flushing.

## Proposed Design

Add a separate archive-generation ticket flow for large speech text downloads.

### API Shape

Use an explicit prepare/status/download flow:

```http
POST /v1/tools/word_trend_speeches/archive/{ticket_id}
GET  /v1/tools/word_trend_speeches/archive/status/{archive_ticket_id}
GET  /v1/tools/word_trend_speeches/archive/download/{archive_ticket_id}
```

Apply the same pattern to speeches tickets:

```http
POST /v1/tools/speeches/archive/{ticket_id}
GET  /v1/tools/speeches/archive/status/{archive_ticket_id}
GET  /v1/tools/speeches/archive/download/{archive_ticket_id}
```

The `POST` endpoint should accept a format parameter. The default bulk format should be `jsonl.gz`. ZIP should remain available for compatibility, but it should not be the preferred format for very large exports.

### Backend Behavior

The prepare endpoint should:

1. Validate that the source result ticket exists and is ready.
2. Create an archive ticket with source ticket ID, requested format, speech count, and expiry metadata.
3. Dispatch archive generation to background execution.
4. Return `202 Accepted` with the archive ticket ID.

The archive worker should:

1. Load speech IDs from the source ticket metadata.
2. Stream speech text from `SearchService.get_speeches_text_batch()`.
3. Write the selected archive format to an artifact path.
4. Write a manifest with source ticket ID, format, speech count, checksums, generation time, and source query metadata.
5. Mark the archive ticket ready or failed.

The download endpoint should:

1. Validate that the archive ticket is ready.
2. Serve the completed artifact with `FileResponse` or equivalent file streaming.
3. Avoid recompressing or rebuilding the archive.

### Format Policy

Use `jsonl.gz` as the default bulk archive format because it is line-oriented, streamable, compact, and already implemented.

Keep ZIP as an explicit compatibility format for users who need individual `.txt` files. Consider a warning or soft limit for very large ZIP requests.

Consider `jsonl.zst` as a future optimization if adding a Zstandard dependency is acceptable.

### Artifact Storage

Reuse the existing result-store root or add a sibling archive artifact area under the same cache root.

Archive artifacts should have the same operational behavior as result artifacts:

- TTL-based expiry
- cleanup of partial files
- capacity accounting
- atomic replace from partial path to final path
- manifest metadata for audit and debugging

## Alternatives Considered

### Keep Streaming In The Download Request

This is simple and already works, but large downloads hold CPU, disk I/O, and the HTTP connection for the full archive build. Retries repeat the same work.

### Eagerly Generate Archives When Query Tickets Complete

This gives the fastest download later, but it wastes work and storage for users who never download the archive. On-demand archive tickets are a better default.

### Parallel Nested ZIP Archives

Generating several ZIP files in parallel and placing them in a master archive would improve some generation work, but it creates nested archives and poor user experience. A flat parallel ZIP writer would require custom ZIP internals and is not worth the maintenance cost unless flat ZIP becomes a hard requirement.

### Single Text File With Dividers

A merged `txt.gz` file with speech dividers would reduce per-entry archive overhead and remain human-readable. It is less robust for machine processing than JSONL because delimiters need escaping and parsing rules. It can be considered as an optional format after the ticket flow exists.

## Risks And Tradeoffs

This adds a second ticket lifecycle for archive preparation. The API and frontend will need to distinguish result tickets from archive tickets.

Archive artifacts increase cache storage pressure. Capacity limits and expiry must include both result artifacts and generated archives.

On-demand generation means the first download still waits for archive preparation, but the user gets status feedback and retries can reuse the completed file.

ZIP compatibility remains expensive for large exports. The system should make bulk-friendly formats easy to choose.

## Testing And Validation

Validation should cover:

- prepare endpoint returns `202 Accepted` for a ready source ticket
- prepare endpoint rejects missing, pending, expired, or failed source tickets
- archive status moves from pending to ready or error
- completed download returns the generated artifact without rebuilding it
- retries of the same archive ticket reuse the same file
- partial archive files are cleaned up after failures
- archive artifacts expire and free capacity
- `jsonl.gz` output is valid and contains all expected speech IDs
- ZIP compatibility output remains valid for explicit ZIP requests

Performance validation should include:

- cold and warm timing for archive preparation
- time-to-ready for `jsonl.gz` versus ZIP on representative large tickets
- download latency for serving a ready artifact
- cache storage growth under repeated archive generation

## Acceptance Criteria

- Large archive generation no longer happens inside the final download request.
- Users can poll archive preparation status before downloading.
- Ready archive downloads serve a completed artifact directly.
- `jsonl.gz` is available as the default bulk format.
- ZIP remains available as an explicit compatibility format.
- Failed and expired archive tickets return clear client-facing errors.
- Cleanup handles partial and expired archive artifacts.

## Recommended Delivery Order

1. Add archive ticket metadata and artifact storage support.
2. Implement `jsonl.gz` archive generation from an existing ready result ticket.
3. Add prepare, status, and download endpoints for word-trend speech archives.
4. Reuse the same archive flow for speeches ticket archives.
5. Add ZIP as an explicit compatibility format in the ticketed flow.
6. Update frontend download controls to show archive preparation status.
7. Benchmark large-result behavior and document the default format recommendation.

## Open Questions

- Should archive tickets be deduplicated by source ticket ID and format, or should every prepare request create a new archive ticket?
- Should very large ZIP requests be rejected, warned, or allowed with lower priority?
- Should archive generation run on the default Celery queue or a dedicated export queue?
- Should the first implementation support only `jsonl.gz`, then add ZIP after the ticket lifecycle is stable?

## Final Recommendation

Implement on-demand archive tickets and make `jsonl.gz` the default full-text bulk format.

Keep ZIP as a compatibility option, but stop treating synchronous ZIP streaming as the primary path for large speech archive downloads.
