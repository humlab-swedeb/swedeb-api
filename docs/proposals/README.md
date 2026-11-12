# Proposal Index

This index lists proposal and design decision documents under `docs/proposals/`. It excludes phase plans, task plans, handoffs, validation and execution reports, and implementation artifacts.

The status reflects proposal-tree placement: root-level proposals are **Proposed**, entries in `future/` are **Future**, and entries in `done/` are **Done**. This is a proposal-tracking status, not a claim that implementation is deployed; check each document for implementation status.

## Proposed

| Proposal | Status | Decision summary |
|---|---|---|
| [Download metadata documentation](./DOWNLOAD_METADATA_DOCUMENTATION.md) | Proposed | Keep `manifest.json` as the machine-readable record and add backend-generated human-readable download provenance without wrapping JSONL or CSV exports. |
| [N-Gram Ticketed Speech Archive](./NGRAM_TICKETED_SPEECH_ARCHIVE.md) | Proposed | Add an asynchronous ticketed download for speech texts associated with n-gram search results by reusing the existing speech-archive flow. |
| [Split N-Gram Compute And Display Forms](./N_GRAM_SPLIT_COMPUTE_DISPLAY_FORM.md) | Proposed | Ignore delimiters when counting n-grams while preserving the original surface form for display and downloads. |
| [Speech Archive Generator CLI](./SPEECH_ARCHIVE_GENERATE_SCRIPT.md) | Proposed | Add a CLI for generating filtered, self-contained speech archives using existing search and archive services. |

## Future

| Proposal | Status | Decision summary |
|---|---|---|
| [Multi-Container Scaling After Phase 2](./future/MULTIUSER_PHASE3_MULTI_CONTAINER_SCALING.md) | Future | Defer horizontal multi-container scaling to a separate phase so it does not block Phase 1 and Phase 2 rollout. |
| [Dedicated Speeches Queue Follow-Up](./future/SPEECHES_DEDICATED_QUEUE_FOLLOWUP.md) | Future | Keep speech jobs on the default Celery queue unless operational or load evidence justifies a dedicated queue. |
| [SpeechRepository Prebuilt Index Ownership](./future/SPEECH_REPOSITORY_PREBUILT_INDEX.md) | Future | Consider replacing `SpeechRepository`'s DTM index dependency with the prebuilt speech index for key resolution and metadata. |
| [Internal Ticket Diagnostics Endpoint](./future/TICKET_DIAGNOSTICS_ENDPOINT.md) | Future | Add a bounded internal snapshot of ticket, Celery, and Redis state to reduce manual diagnostic work. |

## Done

| Proposal | Status | Decision summary |
|---|---|---|
| [Add Celery and Redis for Background Task Execution](./done/ADD_CELERY_AND_REDIS.md) | Done | Use Celery and Redis for long-running background ticket execution, beginning with KWIC and supporting future asynchronous workloads. |
| [Create Merged Speech JSON Corpus](./done/IMPROVED_SPEECH_STORAGE.md) | Done | Consolidate per-protocol utterance JSON archives into a merged speech-level corpus for faster retrieval. |
| [KWIC Async Archive Export](./done/KWIC_ASYNC_ARCHIVE_EXPORT.md) | Done | Move large KWIC exports to a background archive job and provide a retrieval URL for the result. |
| [Merged Speech Corpus for Fast Retrieval](./done/MERGED_SPEECH_CORPUS_DESIGN.md) | Done | Use a versioned Feather/Arrow speech-level corpus and lookup indexes to improve retrieval without adding a database service. |
| [Multiuser Usage Assessment](./done/MULTIUSER_USAGE_ASSESSMENT.md) | Done | Harden ticket execution for single- and multi-process deployments before treating it as reliable for multi-user use; defer horizontal scaling. |
| [Non-Blocking Download Feedback](./done/NON_BLOCKING_DOWNLOAD_FEEDBACK.md) | Done | Show progress for long-running downloads without blocking table interaction or allowing duplicate requests. |
| [Paged KWIC Results via Server-Side Result Cache](./done/PAGED_KWIC_RESULTS_DESIGN.md) | Done | Add ticketed KWIC submission, polling, and server-side paging while retaining the synchronous endpoint during rollout. |
| [Paged N-Gram Results Design](./done/PAGED_NGRAM_RESULTS_DESIGN.md) | Done | Cache final aggregated n-gram results by ticket to support page and sort reuse independently of KWIC paging. |
| [Paged Word Trend Speeches](./done/PAGED_WORD_TREND_SPEECHES_DESIGN.md) | Done | Use ticket-backed server paging for word-trend speech results to reduce large synchronous payloads. |
| [Pagewise PDF Viewer](./done/PAGEWISE_PDF_VIEWER_DESIGN.md) | Done | Serve protocol-page PDFs individually so the viewer does not need to load an entire large protocol PDF. |
| [Progressive KWIC Loading](./done/PROGRESSIVE-KWIC-LOADING.md) | Done | Provide hit estimates, transparent result thresholds, and incremental KWIC delivery instead of a silent hard cutoff. |
| [Replace PersonCodecs Decode Paths with Prebuilt Speech Index](./done/REPLACE_PERSON_CODECS_DECODE_WITH_PREBUILT_INDEX.md) | Done | Use prebuilt speech-index joins for decode output while retaining codecs for filter encoding and metadata enumeration. |
| [Sliding-Window Ticket TTL for Active Pagination](./done/SLIDING-WINDOW-TICKET-TTL.md) | Done | Refresh ticket expiration during pagination so active result browsing is not interrupted by a fixed TTL. |
| [Ticket-Based Bulk Archive Generation](./done/TICKET_BASED_BULK_ARCHIVE_GENERATION.md) | Done | Generate large speech exports as background ticket artifacts and serve the completed files directly. |
| [Ticket Download URL Retrieval Page](./done/TICKET_DOWNLOAD_URL_RETRIEVAL_PAGE.md) | Done | Provide a stable ticket URL that shows progress, the completed download, failure, or expiry. |
