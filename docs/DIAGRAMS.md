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

---

## Application Startup and Component Wiring

**Status**: Active runtime.

### Component: service graph built by AppContainer

```mermaid
flowchart TD
    main[main.py] --> create_app

    subgraph create_app["create_app()"]
        direction TB
        cfg[Configure ConfigStore] --> lifespan
        cors[Add CORS middleware]
        routers[Register routers\ntool / deprecated / metadata / downloads]

        subgraph lifespan["lifespan hook (startup)"]
            celery_cfg[Configure Celery\nif celery_enabled]
            container["AppContainer.build()\n→ app.state.container"]
            rs["ResultStore.from_config()\n→ app.state.result_store"]
            celery_cfg --> container --> rs
        end
    end

    subgraph AppContainer["AppContainer (app-scoped)"]
        direction TB
        CL[CorpusLoader]
        MS[MetadataService]
        WTS[WordTrendsService]
        NGS[NGramsService]
        SS[SearchService]
        STS[SpeechesTicketService]
        KS[KWICService]
        KTS[KWICTicketService]
        KAS[KWICArchiveService]
        WTSTS[WordTrendSpeechesTicketService]
        DS[DownloadService]
        ATS[ArchiveTicketService]

        CL --> MS
        CL --> WTS
        CL --> NGS
        CL --> SS
        CL --> STS
        CL --> KS
        CL --> KTS
        CL --> KAS
        CL --> WTSTS
        CL --> DS
        CL --> ATS
    end

    subgraph CorpusLoader["CorpusLoader (lazy)"]
        direction TB
        idx[prebuilt speech_index.feather]
        dtm[VectorizedCorpus DTM]
        repo[SpeechRepository\n→ SpeechStore]
        codecs[PersonCodecs / MetadataCodecs]
    end

    subgraph ResultStore["ResultStore"]
        direction TB
        disk[Disk artifacts\ncache.root_dir/{ticket_id}/]
        tss[TicketStateStore\nRedis optional]
        disk --- tss
    end

    container --> AppContainer
    rs --> ResultStore

    classDef svc fill:#e8f0fb,stroke:#5c8ac8,color:#1a2a4a;
    classDef store fill:#f0fbe8,stroke:#5ca85c,color:#1a3a1a;
    classDef lazy fill:#fff7d6,stroke:#d6a300,color:#2b2b2b;
    class MS,WTS,NGS,SS,STS,KS,KTS,KAS,WTSTS,DS,ATS svc;
    class ResultStore,disk,tss store;
    class idx,dtm,repo,codecs lazy;
```

---

## Ticket Status Lifecycle

**Status**: Active runtime. Applies to all ticket types: KWIC, speeches, word-trend speeches, and archive tickets.

### State: ticket status transitions

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Pending : Submit query\n202 Accepted

    Pending --> Partial : First shard written\n(KWIC multiprocess only)
    Partial --> Ready : All shards merged
    Pending --> Ready : Job completes\n(single-process or speeches)
    Pending --> Error : Job fails
    Partial --> Error : Job fails

    Ready --> Expired : TTL elapsed
    Error --> Expired : TTL elapsed

    note right of Pending
        Artifact not yet available
        Poll GET /status/{id}
        Retry-After header set
    end note

    note right of Partial
        KWIC production mode only
        Shard files written incrementally
        Pages servable from completed shards
        shards_complete / shards_total exposed
    end note

    note right of Ready
        Artifact stored as merged.feather
        Pages and downloads available
        TTL countdown begins
    end note

    note right of Error
        Safe error message stored
        No stack trace exposed
        User may re-run query
    end note

    note right of Expired
        Ticket removed from ResultStore
        GET returns 404
        Artifact deleted from disk
    end note

    classDef pending fill:#fff7d6,stroke:#d6a300,color:#2b2b2b;
    classDef partial fill:#e8f0fb,stroke:#5c8ac8,color:#1a2a4a;
    classDef ready fill:#dff7e8,stroke:#2e9f5b,color:#1d3a29;
    classDef failed fill:#ffe0e0,stroke:#d64545,color:#4a1f1f;
    classDef expired fill:#eeeeee,stroke:#888888,color:#333333;

    class Pending pending;
    class Partial partial;
    class Ready ready;
    class Error failed;
    class Expired expired;
```

---

## Production vs Development Execution Mode

**Status**: Active runtime. Controlled by `development.celery_enabled` in `config.yml`.

### Flowchart: ticket execution path selection

```mermaid
flowchart TD
    submit[POST /query\nsubmit request] --> create[Create ticket\nResultStore → PENDING]
    create --> check{celery_enabled?}

    check -- true --> celery[send_task to Celery\nqueue: multiprocessing or default]
    check -- false --> bg[BackgroundTasks.add_task\nin-process, no Redis]

    celery --> worker[Celery worker process\npool=solo + multiprocessing.Pool]
    bg --> inline[Runs in FastAPI process\nsingle-threaded, debugger-friendly]

    worker --> shards{KWIC with\nmultiprocessing?}
    shards -- yes --> partial[Write shards → PARTIAL\nmerge when done → READY]
    shards -- no --> ready1[Write artifact → READY]

    inline --> ready2[Write artifact → READY]

    partial --> done[Ticket READY\nArtifact in ResultStore]
    ready1 --> done
    ready2 --> done

    classDef prod fill:#e8f0fb,stroke:#5c8ac8,color:#1a2a4a;
    classDef dev fill:#fff7d6,stroke:#d6a300,color:#2b2b2b;
    classDef common fill:#f5f5f5,stroke:#888888,color:#333333;

    class celery,worker,shards,partial,ready1 prod;
    class bg,inline,ready2 dev;
    class submit,create,check,done common;
```

---

## Synchronous Word Trends Flow

**Status**: Active runtime. The word-trends chart request is synchronous because DTM aggregation is fast (cached corpus, no CQP).

### Sequence: word trends chart

```mermaid
sequenceDiagram
    title Synchronous Word Trends

    actor User
    participant Frontend as Frontend<br/>(wordTrendsStore)
    participant API as API<br/>(tool_router)
    participant WTS as WordTrendsService
    participant DTM as VectorizedCorpus<br/>(DTM, in-memory)

    User->>Frontend: enter search terms + filters, click Sök
    Frontend->>API: GET /v1/tools/word_trends/{search}?from_year=…&party_id=…&normalize=false

    API->>WTS: get_word_trend_results(terms, filter_opts, normalize)
    WTS->>DTM: filter corpus by party / gender / chamber / year
    DTM-->>WTS: filtered document slice
    WTS->>DTM: sum token counts per year for each term
    DTM-->>WTS: yearly count DataFrame

    WTS-->>API: DataFrame (year × term counts)
    API->>API: word_trends_to_api_model(df)
    API-->>Frontend: 200 WordTrendsResult {words: [{word, data: [{year, count}]}]}

    Frontend-->>User: render frequency chart

    Note over Frontend,API: In parallel, frontend also POSTs\n/word_trend_speeches/query\nfor the speeches tab (ticketed)
```

---

## Ticketed Speeches Flow

**Status**: Active runtime. Used by the ANFÖRANDEN tool.

### Sequence: speeches query, paging, and download

```mermaid
sequenceDiagram
    title Ticketed Speeches Flow

    actor User
    participant Frontend as Frontend<br/>(speechesStore)
    participant API as API<br/>(tool_router)
    participant STS as SpeechesTicketService
    participant Worker as Celery / BackgroundTasks
    participant SS as SearchService
    participant ResultStore as ResultStore<br/>(disk)

    User->>Frontend: set filters, click Sök
    Frontend->>API: POST /v1/tools/speeches/query {filters}

    API->>STS: submit_query(selections, result_store)
    STS->>ResultStore: create_ticket() → ticket_id (PENDING)
    STS-->>API: SpeechesTicketAccepted {ticket_id}

    API->>Worker: dispatch execute_speeches_ticket(ticket_id, selections)
    API-->>Frontend: 202 {ticket_id}

    activate Worker
    Worker->>SS: get_speeches(filter_opts)
    SS-->>Worker: speech DataFrame
    Worker->>ResultStore: store_ready(ticket_id, df) → READY
    deactivate Worker

    loop Poll until ready
        Frontend->>API: GET /v1/tools/speeches/status/{ticket_id}
        API-->>Frontend: {status: pending | ready}
    end

    Frontend->>API: GET /v1/tools/speeches/page/{ticket_id}?page=1&page_size=25
    API->>ResultStore: load_artifact + slice page
    ResultStore-->>API: page DataFrame
    API-->>Frontend: 200 SpeechesPageResult {rows, total_hits, page}
    Frontend-->>User: render speech table

    opt Download speeches ZIP
        User->>Frontend: click Ladda ner
        Frontend->>API: POST /v1/tools/speeches/archive/{ticket_id}?format=zip
        API-->>Frontend: 202 {archive_ticket_id, retrieval_url, expires_at}
        Note over Frontend,API: archive preparation follows bulk archive flow
    end
```

---

## Ticketed Word-Trend Speeches Flow

**Status**: Active runtime. Runs in parallel with the synchronous word-trends chart request so the speeches tab resolves asynchronously while the chart appears immediately.

### Sequence: word-trend speeches query and paging

```mermaid
sequenceDiagram
    title Ticketed Word-Trend Speeches Flow

    actor User
    participant Frontend as Frontend<br/>(wordTrendsStore)
    participant API as API<br/>(tool_router)
    participant WTSTS as WordTrendSpeechesTicketService
    participant Worker as Celery / BackgroundTasks
    participant WTS as WordTrendsService
    participant SS as SearchService
    participant ResultStore as ResultStore<br/>(disk)

    User->>Frontend: enter terms + filters, click Sök
    Frontend->>API: POST /v1/tools/word_trend_speeches/query {terms, filters}

    API->>WTSTS: submit_query(request, result_store)
    WTSTS->>ResultStore: create_ticket() → ticket_id (PENDING)
    WTSTS-->>API: WordTrendSpeechesTicketAccepted {ticket_id}

    API->>Worker: dispatch execute_word_trend_speeches_ticket
    API-->>Frontend: 202 {ticket_id}

    Note over Frontend,API: Separately, chart request fires in parallel:\nGET /v1/tools/word_trends/{search} → 200 immediately

    activate Worker
    Worker->>WTS: resolve matching speech IDs for terms + filters
    WTS-->>Worker: speech_ids[]
    Worker->>SS: get_speeches(speech_ids)
    SS-->>Worker: enriched speech DataFrame
    Worker->>ResultStore: store_ready(ticket_id, df) → READY
    deactivate Worker

    loop Poll until ready
        Frontend->>API: GET /v1/tools/word_trend_speeches/status/{ticket_id}
        API-->>Frontend: {status: pending | ready}
    end

    Frontend->>API: GET /v1/tools/word_trend_speeches/page/{ticket_id}?page=1
    API->>ResultStore: load_artifact + slice page
    ResultStore-->>API: page rows
    API-->>Frontend: 200 WordTrendSpeechesPageResult
    Frontend-->>User: render speeches tab
```

---

## N-grams Flow

**Status**: Active runtime. Uses the CWB/CQP path (distinct from the DTM path used by word trends and the estimate endpoint).

### Sequence: n-gram query

```mermaid
sequenceDiagram
    title N-grams Flow (CWB / CQP)

    actor User
    participant Frontend as Frontend<br/>(nGramDataStore)
    participant API as API<br/>(tool_router)
    participant NGS as NGramsService
    participant Mapper as mappers
    participant CWB as CWB Corpus<br/>(ccc / CQP)

    User->>Frontend: enter search term + width + mode + filters, click Sök
    Frontend->>API: GET /v1/tools/ngrams/{search}?width=3&mode=sliding&from_year=…

    API->>API: get_cwb_corpus() → ccc.Corpus instance
    API->>NGS: get_ngrams(search_term, commons, corpus, width, mode)

    NGS->>Mapper: query_params_to_CQP_opts(commons, word_targets)
    Mapper-->>NGS: CQP opts list

    NGS->>CWB: execute CQP query via ccc
    Note over CWB: Full-text index query\nno DTM involved
    CWB-->>NGS: concordance / frequency data

    NGS->>NGS: compute n-gram frequencies\napply threshold filter
    NGS-->>API: NGramResult schema

    API-->>Frontend: 200 {ngrams: [{ngram, count}]}
    Frontend-->>User: render n-gram table
```

---

## Metadata Bootstrap and Filter Hydration

**Status**: Active runtime. Metadata is fetched once at frontend startup to populate filter dropdowns.

### Sequence: app boot metadata hydration

```mermaid
sequenceDiagram
    title Frontend Metadata Bootstrap

    actor User
    participant App as App.vue / boot
    participant MetaStore as metaDataStore<br/>(Pinia)
    participant API as API<br/>(metadata_router)
    participant MetaSvc as MetadataService
    participant Codecs as PersonCodecs<br/>(SQLite-backed)

    User->>App: open application in browser
    App->>MetaStore: initialize()

    par Parallel metadata fetches
        MetaStore->>API: GET /v1/metadata/parties
        MetaStore->>API: GET /v1/metadata/genders
        MetaStore->>API: GET /v1/metadata/chambers
        MetaStore->>API: GET /v1/metadata/office_types
        MetaStore->>API: GET /v1/metadata/start_year
        MetaStore->>API: GET /v1/metadata/end_year
    end

    API->>MetaSvc: get_parties() / get_genders() / …
    MetaSvc->>Codecs: read codec tables
    Codecs-->>MetaSvc: decoded lookup DataFrames
    MetaSvc-->>API: Pydantic response models
    API-->>MetaStore: 200 metadata lists

    MetaStore->>MetaStore: populate options\n(party[], gender[], chamber[])\nset default year range

    MetaStore-->>App: filters ready
    App-->>User: render tool pages with populated filter dropdowns

    Note over MetaStore: Speaker search is lazy:\nGET /v1/metadata/speakers?{query}\nfired on demand from filter input
```
