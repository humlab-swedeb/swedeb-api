# Design Diagrams

This document collects architecture and design diagrams for the Swedeb API: sequence diagrams, state diagrams, component diagrams, and other visual documentation of system behavior and structure.

Diagrams here describe the **current or proposed active runtime**. Historical diagrams belong in `docs/archive/`. Proposal-specific diagrams may live in `docs/change_requests/` alongside the relevant proposal and be promoted here once implemented.

---

## KWIC Async Archive Export

**Status**: Implemented. See [docs/change_requests/done/KWIC_ASYNC_ARCHIVE_EXPORT.md](change_requests/done/KWIC_ASYNC_ARCHIVE_EXPORT.md) for the full proposal.

### Sequence: Async archive preparation and retrieval

```mermaid
sequenceDiagram
    title KWIC Async Archive Export

    actor User
    actor OtherUser as Other User (optional)
    participant Frontend as Frontend<br/>(kwicDataStore)
    participant API as API<br/>(tool_router)
    participant BG as BackgroundTask<br/>(KWICArchiveService)
    participant ResultStore as ResultStore<br/>(Feather / disk)
    participant DownloadsAPI as API<br/>(downloads_router)
    participant RetrievalPage as DownloadRetrievalPage<br/>(Vue)

    User->>Frontend: click Export (CSV / JSONL / Excel)
    Frontend->>API: POST /v1/tools/kwic/archive/{ticket_id}?format=xlsx

    API->>ResultStore: validate source ticket is READY
    ResultStore-->>API: KWICTicketMeta

    API->>ResultStore: create_ticket(archive_format=xlsx)
    ResultStore-->>API: archive_ticket_id

    API-->>Frontend: 202 ArchivePrepareResponse<br/>{archive_ticket_id, retrieval_url, expires_at}

    par Background serialization
        activate BG
        BG->>ResultStore: get_full_artifact(source_ticket_id)
        ResultStore-->>BG: KWIC DataFrame
        Note over BG: serialize to xlsx via openpyxl<br/>write to archive artifact path
        BG->>ResultStore: store_archive_ready(archive_ticket_id)
        deactivate BG
    and Frontend polls for status
        Frontend->>Frontend: store archiveRetrievalUrl<br/>show copy-link button

        loop Poll until ready or error
            Frontend->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}
            DownloadsAPI->>ResultStore: require_ticket(archive_ticket_id)
            ResultStore-->>DownloadsAPI: TicketMeta {status}
            DownloadsAPI-->>Frontend: 200 {status: pending | ready | error}
        end
    end

    Frontend-->>User: show Download button (status=ready)
    User->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}/download
    DownloadsAPI->>ResultStore: get artifact path
    ResultStore-->>DownloadsAPI: artifact file
    DownloadsAPI-->>User: 200 xlsx file stream

    Note over User,OtherUser: User copies retrieval_url and shares it
    OtherUser->>RetrievalPage: open retrieval_url in browser
    RetrievalPage->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}
    DownloadsAPI-->>RetrievalPage: 200 {status: ready, expires_at}
    OtherUser->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}/download
    DownloadsAPI-->>OtherUser: 200 xlsx file stream
```

---

## Ticket-Based Bulk Archive Generation (Speeches / Word-Trend Speeches)

**Status**: Implemented. See [docs/change_requests/done/TICKET_BASED_BULK_ARCHIVE_GENERATION.md](change_requests/done/TICKET_BASED_BULK_ARCHIVE_GENERATION.md) for the full proposal.

This flow applies to both:
- `POST /v1/tools/speeches/archive/{ticket_id}`
- `POST /v1/tools/word_trend_speeches/archive/{ticket_id}`

### Sequence: Async bulk archive preparation and retrieval

```mermaid
sequenceDiagram
    title Ticket-Based Bulk Archive Generation (Speeches / Word-Trend Speeches)

    actor User
    actor OtherUser as Other User (optional)
    participant Frontend as Frontend<br/>(store)
    participant API as API<br/>(tool_router)
    participant ArchiveSvc as ArchiveTicketService
    participant BG as BackgroundTask / Celery<br/>(execute_archive_task)
    participant SearchSvc as SearchService
    participant ResultStore as ResultStore<br/>(Feather / disk)
    participant DownloadsAPI as API<br/>(downloads_router)
    participant RetrievalPage as DownloadRetrievalPage<br/>(Vue)

    User->>Frontend: click Export (jsonl.gz / zip)
    Frontend->>API: POST /v1/tools/speeches/archive/{ticket_id}?format=jsonl_gz

    API->>ArchiveSvc: prepare(source_ticket_id, archive_format, result_store)
    ArchiveSvc->>ResultStore: validate source ticket is READY
    ResultStore-->>ArchiveSvc: TicketMeta (speech_ids, source query)
    ArchiveSvc->>ResultStore: create_ticket(source_ticket_id, archive_format)
    ResultStore-->>ArchiveSvc: archive_ticket_id
    ArchiveSvc-->>API: ArchivePrepareResponse {archive_ticket_id, expires_at}

    API->>API: compute retrieval_url from Request.base_url
    API-->>Frontend: 202 ArchivePrepareResponse<br/>{archive_ticket_id, retrieval_url, expires_at}

    par Background archive generation
        activate BG
        BG->>ResultStore: load speech_ids from source TicketMeta
        ResultStore-->>BG: speech_ids[]
        BG->>SearchSvc: get_speeches_text_batch(speech_ids)
        SearchSvc-->>BG: speech text stream
        Note over BG: serialize to jsonl.gz or zip<br/>write atomically to archive artifact path
        BG->>ResultStore: store_archive_ready(archive_ticket_id)
        deactivate BG
    and Frontend polls for status
        Frontend->>Frontend: store retrieval_url<br/>show copy-link button

        loop Poll until ready or error
            Frontend->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}
            DownloadsAPI->>ResultStore: require_ticket(archive_ticket_id)
            ResultStore-->>DownloadsAPI: TicketMeta {status}
            DownloadsAPI-->>Frontend: 200 {status: pending | ready | error}
        end
    end

    Frontend-->>User: show Download button (status=ready)
    User->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}/download
    DownloadsAPI->>ResultStore: get artifact path
    ResultStore-->>DownloadsAPI: artifact file
    DownloadsAPI-->>User: 200 jsonl.gz or zip file stream

    Note over User,OtherUser: User copies retrieval_url and shares it
    OtherUser->>RetrievalPage: open retrieval_url in browser
    RetrievalPage->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}
    DownloadsAPI-->>RetrievalPage: 200 {status: ready, expires_at}
    OtherUser->>DownloadsAPI: GET /v1/downloads/{archive_ticket_id}/download
    DownloadsAPI-->>OtherUser: 200 jsonl.gz or zip file stream
```

---

## Download Retrieval Page — Four States

**Status**: Implemented. See [docs/change_requests/done/TICKET_DOWNLOAD_URL_RETRIEVAL_PAGE.md](change_requests/done/TICKET_DOWNLOAD_URL_RETRIEVAL_PAGE.md) for the full proposal.

The Vue frontend route `/download/:archiveTicketId` (`DownloadRetrievalPage.vue`) renders one of four states based on the ticket status returned by `GET /v1/downloads/{archive_ticket_id}`. The inline polling flow (user stays on the tool page) is the primary path; the retrieval page is the fallback for tab-close, network loss, or sharing.

### State: ticket lifecycle and retrieval-page rendering

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Pending : POST archive<br/>202 Accepted

    Pending --> Ready : Background job completed
    Pending --> Failed : Background job failed
    Pending --> Expired : TTL elapsed

    Ready --> Expired : TTL elapsed
    Failed --> Expired : TTL elapsed

    state "Pending" as Pending
    state "Ready" as Ready
    state "Failed" as Failed
    state "Expired / Not found" as Expired

    note right of Pending
        Preparing archive
        Spinner shown
        Auto-refresh every 5 seconds
        Copy-link available immediately
    end note

    note right of Ready
        Download available
        Shows format and expiry time
        GET /v1/downloads/{id}/download
        returns 200 file stream
    end note

    note right of Failed
        Safe user-facing error
        No stack traces
        User can return to search
    end note

    note right of Expired
        Link has expired
        API returns 404
        Page renders expiry message
        User can re-run the query
    end note

    classDef pending fill:#fff7d6,stroke:#d6a300,color:#2b2b2b;
    classDef ready fill:#dff7e8,stroke:#2e9f5b,color:#1d3a29;
    classDef failed fill:#ffe0e0,stroke:#d64545,color:#4a1f1f;
    classDef expired fill:#eeeeee,stroke:#888888,color:#333333;

    class Pending pending;
    class Ready ready;
    class Failed failed;
    class Expired expired;
```

---

## Progressive KWIC Loading

**Status**: Implemented (all three phases). See [docs/change_requests/done/PROGRESSIVE-KWIC-LOADING.md](change_requests/done/PROGRESSIVE-KWIC-LOADING.md) for the full proposal.

Three layered capabilities shipped together:
- **Phase 1** — Pre-search estimate via `GET /v1/tools/kwic/estimate` (DTM column sum, < 20 ms)
- **Phase 2** — Threshold-based display mode with explicit banner (retired by Phase 3)
- **Phase 3** — Progressive shard delivery: `PARTIAL` status, per-shard artifact storage, progress bar in the frontend

The diagrams below cover Phase 1 (estimate) and Phase 3 (progressive delivery). Phase 2 was a transitional state and is not diagrammed separately.

### Sequence: Pre-search estimate

```mermaid
sequenceDiagram
    title KWIC Pre-Search Estimate

    actor User
    participant Frontend as Frontend<br/>(kwicDataStore)
    participant API as API<br/>(tool_router)
    participant WTS as WordTrendsService<br/>(estimate_hits)

    User->>Frontend: type word / change filter (debounce 300 ms)
    Frontend->>API: GET /v1/tools/kwic/estimate?word=X&from_year=…
    API->>WTS: estimate_hits(word, filter_opts)
    Note over WTS: DTM column sum with filter applied\n< 20 ms, no CQP query
    WTS-->>API: count (int | None)
    API-->>Frontend: 200 {estimated_hits: N, in_vocabulary: true|false}

    alt in_vocabulary: false
        Frontend-->>User: no indicator shown
    else estimated_hits < threshold
        Frontend-->>User: "~N träffar förväntade" (neutral)
    else estimated_hits ≥ threshold
        Frontend-->>User: "~N träffar — stor träffmängd,\nnedladdning rekommenderas" (amber)
    end

    Note over Frontend: estimate does not block the search
```

### Sequence: Progressive KWIC shard delivery (production mode)

```mermaid
sequenceDiagram
    title Progressive KWIC Loading — Shard Delivery (Production Mode)

    actor User
    participant Frontend as Frontend<br/>(kwicDataStore)
    participant API as API<br/>(tool_router / KWICTicketService)
    participant Celery as Celery Worker<br/>(multiprocessing queue)
    participant Pool as Pool.imap_unordered<br/>(year-range shards)
    participant ResultStore as ResultStore<br/>(disk + TicketStateStore)

    User->>Frontend: click Sök (search)
    Frontend->>API: POST /v1/tools/kwic/query {word, filters}
    API->>ResultStore: create_ticket() → ticket_id (PENDING)
    API->>Celery: send_task(execute_kwic_ticket, ticket_id)
    API-->>Frontend: 202 {ticket_id, estimated_hits}

    activate Celery
    Celery->>Pool: Pool.imap_unordered(shards)
    Celery->>ResultStore: set_shards_total(ticket_id, N)

    loop As each shard completes (unordered)
        Pool-->>Celery: (shard_index, shard_df)
        Celery->>ResultStore: store_shard(ticket_id, shard_index, df)\nwrites {ticket_id}/shard_NNNN.feather atomically
        ResultStore->>ResultStore: ticket status → PARTIAL\nincrement shards_complete via TicketStateStore (Redis)
    end

    loop Frontend polls (every 2 s)
        Frontend->>API: GET /v1/tools/kwic/status/{ticket_id}
        API->>ResultStore: sync_external_partial(ticket_id)\nreads shards_complete / shards_total from Redis
        ResultStore-->>API: {status: partial, shards_complete: K, shards_total: N}
        API-->>Frontend: 200 {status: partial, shards_complete: K, shards_total: N}
        Frontend->>API: GET /v1/tools/kwic/page/{ticket_id}?page=1
        API->>ResultStore: load_artifact → concat shard_0000..shard_K-1.feather
        ResultStore-->>API: partial DataFrame
        API-->>Frontend: page rows
        Frontend-->>User: render rows + shard progress bar (K/N)
        Note over Frontend: sort controls disabled during PARTIAL
    end

    Celery->>ResultStore: store_shards_ready(ticket_id)\nmerge → {ticket_id}/merged.feather\ndelete shard files\nstatus → READY
    deactivate Celery

    Frontend->>API: GET /v1/tools/kwic/status/{ticket_id}
    API-->>Frontend: 200 {status: ready, shards_complete: N, shards_total: N}
    Frontend-->>User: full result rendered\nsort controls re-enabled
```
