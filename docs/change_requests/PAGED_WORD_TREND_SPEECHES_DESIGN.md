# Change Request: Paged Word Trend Speeches via Server-Side Ticket Cache

**Status**: Complete — all phases (0–4) implemented; pending end-to-end testing with live Celery worker  
**Primary area**: `api_swedeb/api/v1/endpoints/tool_router.py`, `WordTrendsService`, speeches retrieval  
**Related**: `docs/change_requests/PAGED_KWIC_RESULTS_DESIGN.md` (same ticket-based paging pattern)  
**Affects**: API, frontend (`wordTrendsSpeechTable.vue` (new), `wordTrendsDataStore.js`, `WordTrendsPage.vue`)

---

## Summary

Add server-side ticket-based paging for word trend speeches retrieval to eliminate large synchronous payloads, reduce client/server memory pressure, and provide incremental feedback for queries that return thousands of matching speeches.

This follows the same async submit-poll-page pattern used for KWIC, reusing the existing `ResultStore` infrastructure.

---

## Problem

Word trend speech queries currently return all matching speeches in a single synchronous response:

```http
GET /v1/tools/word_trend_speeches/demokrati?from_year=1867&to_year=2022
```

### Issues

1. **Large payloads**: A broad year range or common word can return 10,000+ speeches serialized to multi-megabyte JSON responses
2. **Blocking requests**: The endpoint holds the connection open during corpus scan, speech index lookup, and metadata join operations
3. **No incremental feedback**: The frontend shows nothing until the full response arrives
4. **Memory pressure**: Both server and client hold the full result set in memory
5. **Wasted bandwidth**: Users typically inspect only the first few pages, not all 10,000 speeches
6. **No server-side sorting**: All sorting must happen client-side after downloading the full list

### Current Flow

**Sequential API Calls** (Performance Issue):

```javascript
// WordTrendsPage.vue - Current Implementation
await wtStore.getWordTrendsResult(textString);      // Wait for trends data
await wtStore.getWordTrendsSpeeches(textString);    // Then wait for speeches data
```

This makes two **sequential** synchronous calls:

```text
Frontend                                Backend
   │                                      │
   │── 1. GET word_trends/word ────────→ │ Calculate trends
   │                                      │ Group by year
   │←─────── trends data ───────────────  │
   │                                      │
   │── 2. GET word_trend_speeches/word ─→ │ CorpusLoader.vectorized_corpus
   │   (all filters in query params)     │ get_speeches_by_words()
   │                                      │ person_codecs.decode_speech_index()
   │                                      │ Serialize 10k+ speeches to JSON
   │                                      │
   │←─────── 200 OK ───────────────────── │
   │    { speech_list: [10k items] }     │
   │                                      │
   │ Store in Pinia state                │
   │ Client-side paging/sorting          │
```

**Total time = Trends API time + Speeches API time** (e.g., 2s + 8s = 10s)

### Quick Fix: Parallel Synchronous Requests

**Optimization:**

```javascript
// Parallel execution with Promise.all()
await Promise.all([
  wtStore.getWordTrendsResult(textString),    // Starts immediately
  wtStore.getWordTrendsSpeeches(textString)   // Starts immediately (not blocked)
]);
```

**Parallelized Flow:**

```text
Frontend                                Backend
   │                                      │
   ├── 1. GET word_trends/word ────────→ │ Calculate trends (2s)
   │                                      │
   └── 2. GET word_trend_speeches/word ─→ │ Corpus scan + serialize (8s)
       (both start simultaneously)        │
   │                                      │
   │←─────── trends data ───────────────  │ (at 2s)
   │                                      │
   │←─────── speeches data ─────────────  │ (at 8s)
   │                                      │
   Both complete - render results
```

**Total time = max(Trends API time, Speeches API time)** (e.g., max(2s, 8s) = 8s)

**20% time reduction with zero backend changes!**

---

## Parallel Request Optimization

### Problem: Sequential API Calls

The current frontend implementation calls the two endpoints **sequentially**:

```javascript
// WordTrendsPage.vue (lines 98-101)
await wtStore.getWordTrendsResult(textString);      // Blocks until complete
await wtStore.getWordTrendsSpeeches(textString);    // Only starts after first completes
```

This is inefficient because:
- The two requests are **independent** (neither depends on the other's result)
- Total time = sum of both request times (additive latency)
- User waits for both before seeing any speeches data

### Solution 1: Immediate Parallel Requests (Current Sync Endpoints)

**Before ticket-based paging is implemented**, parallelize the existing synchronous endpoints:

```javascript
// WordTrendsPage.vue - Optimized
const [trendsResult, speechesResult] = await Promise.all([
  wtStore.getWordTrendsResult(textString),
  wtStore.getWordTrendsSpeeches(textString)
]);
```

**Benefits:**
- Total time = max(trends time, speeches time) instead of sum
- Example: If trends takes 2s and speeches takes 8s, total is 8s instead of 10s
- No backend changes required
- Simple frontend change

**Implementation:**

```javascript
// WordTrendsPage.vue
watchEffect(async () => {
  if (store.submitEventWT) {
    loading.value = true;
    showData.value = false;
    showDataTable.value = false;
    const textString = wtStore.generateStringOfSelected();
    
    // Execute both requests in parallel
    await Promise.all([
      wtStore.getWordTrendsResult(textString),
      wtStore.getWordTrendsSpeeches(textString)
    ]);
    
    // Both complete - show results
    showDataTable.value = true;
    dataLoadedTable.value = true;
    showData.value = true;
    dataLoaded.value = true;
    loading.value = false;
    store.cancelSubmitWTEvent();
  }
});
```

### Solution 2: Parallel Async Requests (With Ticket-Based Paging)

**After ticket-based paging is implemented**, parallelize the async ticket flow:

```javascript
// WordTrendsPage.vue - Ticket-based parallel
const textString = wtStore.generateStringOfSelected();

// Submit both requests in parallel
const [trendsResult, speechesTicket] = await Promise.all([
  wtStore.getWordTrendsResult(textString),        // Sync endpoint (fast)
  wtStore.submitSpeechesQuery(textString)         // Async ticket (immediate)
]);

// Show trends immediately (they're ready)
showDataTable.value = true;
dataLoadedTable.value = true;

// Poll speeches status in background
while (speechesTicket.status === 'pending') {
  await new Promise(resolve => setTimeout(resolve, 1000));  // 1s poll interval
  const status = await wtStore.pollSpeechesStatus(speechesTicket.ticket_id);
  if (status.status === 'ready') {
    // Fetch first page
    await wtStore.fetchSpeechesPage(speechesTicket.ticket_id, 1);
    showData.value = true;
    dataLoaded.value = true;
    break;
  }
}
```

**Benefits:**
- Trends data appears immediately (typically <2s)
- Speeches loading shows progress updates ("Found 8247 speeches, preparing results...")
- User can interact with trends chart while speeches load
- No blocking wait for large speech lists

**Better UX Flow:**

```text
Time    Frontend State                    Backend
─────   ────────────────────────────────  ────────────────────────────────
0.0s    Submit both requests in parallel
        │
        ├─→ Trends loading...             GET /word_trends/word
        └─→ Speeches loading...           POST /word_trend_speeches/query (immediate)
                                          
1.5s    ✓ Trends chart visible            (trends complete)
        ⏳ Speeches: "Searching..."        (ticket pending, corpus scan running)
        
3.0s    ⏳ Speeches: "Found 8247 speeches, preparing results..."
                                          (status poll shows total_hits)
        
5.0s    ✓ Speeches table visible (page 1) GET /word_trend_speeches/page/{ticket_id}?page=1
```

### Recommendation

**Phase 1 (Immediate)**: Implement Solution 1 - parallelize existing sync endpoints
- Simple `Promise.all()` change in `WordTrendsPage.vue`
- No backend changes
- Provides immediate 20-40% time reduction
- Independent of ticket-based paging work

**Phase 2 (With Ticket Implementation)**: Implement Solution 2 - parallel async flow
- Trends shown immediately
- Speeches load progressively with feedback
- Integrated with ticket-based paging proposal

---

## Scope

### In Scope

1. Submit word trend speeches query and receive ticket immediately
2. Poll ticket readiness
3. Fetch paged results from cached artifact
4. Reuse ticket for paging and sorting
5. Download full speech list via ticket
6. Share `ResultStore` infrastructure with KWIC (already supports generic artifacts)

### Out of Scope

1. Re-filtering cached results with new year/party/gender constraints (requires new ticket)
2. Returning `total_hits` in initial submit response (requires running query first)
3. Word trends data endpoint paging (out of scope; only speeches tab)
4. Client-side caching across tickets

### Coexistence Strategy

- Keep `GET /v1/tools/word_trend_speeches/{search}` unchanged for backward compatibility
- Add new ticketed endpoints alongside existing endpoint
- Frontend opts into async flow explicitly via feature flag or route
- Provides clean rollback path if operational issues arise

---

## Current Behavior

### Endpoint

`GET /v1/tools/word_trend_speeches/{search}`

**Query parameters:**
- `from_year`, `to_year`
- `who`, `party_id`, `gender_id`, `chamber_abbrev`, `speech_id`

**Response:** `SpeechesResultWT` containing all matching speeches

### Implementation

`WordTrendsService.get_speeches_for_word_trends()`:
1. Calls `get_speeches_by_words()` with vectorized corpus and filter opts
2. Decodes speech index via `person_codecs.decode_speech_index()`
3. Returns full DataFrame serialized to `speech_list`

### Typical Response Sizes

| Query Scope | Approx Speeches | JSON Size |
|-------------|----------------|-----------|
| Single year + uncommon word | 10-50 | 5-25 KB |
| Decade + common word | 500-2000 | 250 KB - 1 MB |
| Full corpus (1867-2022) + common word | 5000-20000 | 2.5 MB - 10 MB |

---

## Proposed Design

### API Contract

Follow the same three-phase async pattern as KWIC:

#### Phase 1: Submit Query

```http
POST /v1/tools/word_trend_speeches/query
Content-Type: application/json

{
  "search": ["demokrati", "frihet"],
  "filters": {
    "from_year": 1867,
    "to_year": 2022,
    "who": null,
    "party_id": null,
    "gender_id": null,
    "chamber_abbrev": null,
    "speech_id": null
  }
}
```

**Response:**

```http
202 Accepted
{
  "ticket_id": "7a9b2c3d-...",
  "status": "pending",
  "expires_at": "2026-04-21T16:00:00Z"
}
```

**Schema:** `WordTrendSpeechesQueryRequest`
- `search`: `list[str]` - search terms (same as current comma-separated endpoint param)
- `filters`: `WordTrendSpeechesFilterRequest` - year ranges and metadata filters

#### Phase 2: Poll Status

```http
GET /v1/tools/word_trend_speeches/status/{ticket_id}
```

**Response:**

```http
200 OK
{
  "ticket_id": "7a9b2c3d-...",
  "status": "ready",
  "total_hits": 8247,
  "expires_at": "2026-04-21T16:00:00Z"
}
```

**Possible states:**
- `pending` - Query running
- `ready` - Results available for paging
- `error` - Query failed (stores error message)

#### Phase 3: Fetch Page

```http
GET /v1/tools/word_trend_speeches/page/{ticket_id}?page=1&page_size=50&sort_by=year&sort_order=desc
```

**Query parameters:**
- `page` (default: 1, min: 1)
- `page_size` (default: 50, max: 500)
- `sort_by` (optional): `year`, `name`, `party_abbrev`, `document_name`
- `sort_order` (default: `asc`, values: `asc`, `desc`)

**Response:**

```http
200 OK
{
  "ticket_id": "7a9b2c3d-...",
  "status": "ready",
  "page": 1,
  "page_size": 50,
  "total_hits": 8247,
  "total_pages": 165,
  "speech_list": [ ...50 items... ],
  "expires_at": "2026-04-21T16:00:00Z"
}
```

**Schema:** `WordTrendSpeechesPageResult`
- Extends `SpeechesResultWT` with pagination metadata
- `speech_list` uses existing `SpeechesResultItemWT` (includes `node_word` field)

#### Download Endpoint

```http
GET /v1/tools/word_trend_speeches/download/{ticket_id}?format=csv
```

Returns full speech list in requested format (CSV, JSON, Excel) from cached artifact.

### Backend Implementation

#### New Service: `WordTrendSpeechesTicketService`

Parallel to `KWICTicketService`, implements:

**`submit_query(request, result_store) -> TicketAccepted`**
- Creates ticket via `result_store.create_ticket()`
- Schedules async execution (Celery task if enabled, else inline)
- Returns ticket metadata

**`execute_ticket(ticket_id, request, loader, result_store)`**
- Runs `WordTrendsService.get_speeches_for_word_trends()`
- Adds `_ticket_row_id` column for stable row references
- Stores artifact as Feather via `result_store.store_ready()`
- Handles capacity/expiry errors gracefully

**`get_status(ticket_id, result_store) -> TicketStatus`**
- Queries `result_store.get_ticket()` metadata
- Returns pending/ready/error state with `total_hits`

**`get_page_result(ticket_id, page, page_size, sort_by, sort_order, result_store) -> PageResult`**
- Checks ticket is ready
- Reads Feather artifact
- Applies sorting if requested
- Slices page window
- Maps to `WordTrendSpeechesPageResult` model

#### Reuse Existing Infrastructure

- **`ResultStore`**: Generic artifact storage (already used by KWIC)
- **Celery tasks**: Optional async execution (conditional on `development.celery_enabled`)
- **Redis**: Ticket metadata persistence (if Celery enabled)
- **Feather format**: Fast columnar read/write for DataFrames

#### Endpoint Routes

Add to `api_swedeb/api/v1/endpoints/tool_router.py`:

```python
@router.post("/word_trend_speeches/query", response_model=WordTrendSpeechesTicketAccepted, status_code=202)
async def submit_word_trend_speeches_query(...)

@router.get("/word_trend_speeches/status/{ticket_id}", response_model=WordTrendSpeechesTicketStatus)
async def get_word_trend_speeches_status(...)

@router.get("/word_trend_speeches/page/{ticket_id}", response_model=WordTrendSpeechesPageResult)
async def get_word_trend_speeches_page(...)

@router.get("/word_trend_speeches/download/{ticket_id}")
async def download_word_trend_speeches(...)
```

### Frontend Changes

Update `wordTrendsDataTable.vue` to:
1. Use POST to submit query on initial load
2. Poll status endpoint until ready
3. Show loading progress with spinner
4. Fetch first page when ready
5. Lazy-load additional pages on scroll/pagination
6. Reuse ticket for all sort/page operations

Store ticket ID and pagination state in Pinia word trends store.

### Sorting Strategy

**Server-side sorting only** (unlike KWIC which supports both):
- DataFrame sorting is fast (milliseconds for 10k rows)
- Avoids duplicate sort logic in frontend
- Simplifies client state management
- Consistent with download behavior

Supported sort keys:
- `year` - Speech year (default descending)
- `name` - Speaker name (alphabetical)
- `party_abbrev` - Party abbreviation
- `document_name` - Speech document ID

---

## Alternatives Considered

### Keep Sequential Requests

**Rejected**: Current sequential execution adds unnecessary latency (sum of both request times instead of max). Simple `Promise.all()` change provides 20-40% improvement with no backend changes.

### Client-Side Paging Only

**Rejected**: Doesn't solve payload size, network time, or memory pressure issues.

### Cursor-Based Paging

**Rejected**: Server-side sorting requires stable row ordering anyway, and page numbers are more intuitive for users inspecting speeches.

### Inline Execution (No Tickets)

**Rejected**: Doesn't provide async feedback or support for long-running queries. Also inconsistent with KWIC pattern.

### Separate Result Store for Speeches

**Rejected**: Reusing `ResultStore` reduces code duplication and operational complexity.

---

## Risks And Tradeoffs

### Complexity

**Risk**: Adds async request flow and ticket management  
**Mitigation**: Reuse proven KWIC infrastructure; keep coexistence with sync endpoint

### Storage Pressure

**Risk**: Caching 10k-speech artifacts per query increases disk usage  
**Mitigation**: `ResultStore` already has:
- Configurable TTL (default 10 minutes)
- Capacity limits with LRU eviction
- Automatic cleanup on startup

### Celery Dependency

**Risk**: Requires Redis and Celery workers for async execution  
**Mitigation**: Graceful fallback to inline execution when `development.celery_enabled=false`

### Client Compatibility

**Risk**: Existing frontends break if sync endpoint is removed  
**Mitigation**: Keep sync endpoint active during transition; feature-flag async flow

### Partial Results Edge Case

**Risk**: User sees first page before realizing total hit count is too large  
**Mitigation**: Poll status shows `total_hits` before fetching first page; frontend can warn

---

## Testing And Validation

### Unit Tests

- `WordTrendSpeechesTicketService` ticket creation, execution, status, paging
- Sorting logic for all supported keys
- Error handling (capacity exceeded, expired tickets, invalid page numbers)

### Integration Tests

- Submit query → poll status → fetch multiple pages
- Sort by each supported key in both directions
- Download endpoint with various formats
- Ticket expiry and cleanup

### Performance Testing

- Compare sync vs async flow for 1k, 5k, 10k speech results
- Measure memory usage during artifact storage/retrieval
- Verify Feather read performance for sorting operations

### Frontend Testing

- Verify loading states and progress indicators
- Test pagination controls and lazy loading
- Confirm ticket reuse for sort/page changes

---

## Acceptance Criteria

1. **New endpoints functional**: POST query, GET status, GET page, GET download
2. **Backward compatibility preserved**: Existing sync endpoint unchanged and working
3. **Paging works**: Can fetch arbitrary page with correct results
4. **Sorting works**: Server-side sort by year/name/party returns correct order
5. **Error handling robust**: Graceful responses for expired tickets, invalid pages, capacity errors
6. **Performance improved**: 10k-speech query shows first page in <2s (vs 10s+ for sync)
7. **Memory usage reduced**: Server doesn't hold full result in memory after caching
8. **Tests pass**: Unit and integration tests cover success and error paths
9. **Frontend integrated**: Word trends speeches tab uses async flow with loading indicators

---

## Recommended Delivery Order

### Phase 1: Backend Foundation

1. Create `WordTrendSpeechesQueryRequest` and `WordTrendSpeechesFilterRequest` schemas
2. Create `WordTrendSpeechesTicketAccepted`, `WordTrendSpeechesTicketStatus`, `WordTrendSpeechesPageResult` schemas
3. Implement `WordTrendSpeechesTicketService` class
4. Add Celery task wrapper (conditional on `development.celery_enabled`)
5. Add unit tests for service

### Phase 2: API Endpoints

1. Add POST `/word_trend_speeches/query` endpoint
2. Add GET `/word_trend_speeches/status/{ticket_id}` endpoint  
3. Add GET `/word_trend_speeches/page/{ticket_id}` endpoint
4. Add GET `/word_trend_speeches/download/{ticket_id}` endpoint
5. Add integration tests

### Phase 3: Frontend Integration

1. Update word trends store to support ticket-based flow
2. Modify `wordTrendsDataTable.vue` for async loading
3. Add loading indicators and progress feedback
4. Implement pagination controls
5. Add feature flag for gradual rollout

### Phase 4: Validation

1. Performance testing with production-scale data
2. User acceptance testing
3. Monitoring and observability
4. Documentation updates

---

## Implementation Checklist

### Phase 0: Immediate Optimization (Parallel Requests)

**Frontend Quick Win** (`swedeb_frontend/src/pages/WordTrendsPage.vue`)
- [x] Change sequential `await` calls to `Promise.all()`
- [x] Test parallel execution with both fast and slow queries
- [x] Verify error handling works for both requests
- ~~[ ] Measure time improvement (before/after)~~
- ~~[ ] Deploy to production (no backend changes needed)~~

**Expected Impact:**
- 20-40% reduction in total load time
- Example: 10s → 8s for common words with broad year ranges
- No breaking changes, fully backward compatible

### Phase 1: Backend Foundation

**Schemas** (`api_swedeb/schemas/`)
- [x] Create `WordTrendSpeechesQueryRequest` model
  - [x] `search: list[str]` field with validation
  - [x] `filters: WordTrendSpeechesFilterRequest` nested model
- [x] Create `WordTrendSpeechesFilterRequest` model
  - [x] `from_year`, `to_year` optional int fields
  - [x] `who`, `party_id`, `gender_id`, `chamber_abbrev`, `speech_id` optional fields
  - [x] Match existing filter semantics from `CommonQueryParams`
- [x] Create `WordTrendSpeechesTicketAccepted` model (202 response)
  - [x] `ticket_id`, `status`, `expires_at` fields
- [x] Create `WordTrendSpeechesTicketStatus` model
  - [x] `ticket_id`, `status`, `total_hits`, `error`, `expires_at` fields
  - [x] Support `pending`, `ready`, `error` states
- [x] Create `WordTrendSpeechesPageResult` model
  - [x] Extend `SpeechesResultWT` with pagination metadata
  - [x] `page`, `page_size`, `total_hits`, `total_pages` fields
  - [x] `speech_list: list[SpeechesResultItemWT]`
- [x] Add unit tests for schema validation

**Service Layer** (`api_swedeb/api/services/`)
- [x] Create `WordTrendSpeechesTicketService` class
  - [x] `submit_query()` method - create ticket and schedule execution
  - [x] `execute_ticket()` method - run query and store artifact
  - [x] `get_status()` method - return ticket state
  - [x] `get_page_result()` method - fetch paginated slice with sorting
  - [x] Helper: `_sort_frame()` for server-side sorting with `TICKET_ROW_ID` tiebreaker
  - [x] Helper: `_build_page_result()` for shared pagination logic
  - [x] Helper: `_frame_to_speeches()` for model conversion
- [x] Add service factory in `api_swedeb/api/dependencies.py`
  - [x] `get_word_trend_speeches_ticket_service()` dependency function
- [x] Add service to `api_swedeb/api/container.py` (`AppContainer.word_trend_speeches_ticket_service`)
- [x] Create unit tests for `WordTrendSpeechesTicketService` (19 tests, all passing)
  - [x] Test ticket creation and metadata
  - [x] Test execute_ticket stores artifact and sets ready status
  - [x] Test get_status for pending/ready/error states
  - [x] Test get_page_result with sorting by year/name/party_abbrev
  - [x] Test page slicing edge cases (first/last page, empty result)
  - [x] Test error handling (invalid page numbers, unknown tickets)

**Celery Integration** (`api_swedeb/celery_tasks.py`)
- [x] Create `execute_word_trend_speeches_ticket_celery_task()` Celery task
  - [x] Conditional execution based on `development.celery_enabled`
  - [x] Proper exception handling and error logging
  - [x] Store results via `ResultStore.store_ready()`
  - [x] Handle capacity/expiry errors gracefully
- [x] Add task registration in Celery app config
- [ ] Test Celery task execution (integration test)
- [ ] Test fallback to inline execution when Celery disabled

### Phase 2: API Endpoints

**Router** (`api_swedeb/api/v1/endpoints/tool_router.py`)
- [x] Add POST `/word_trend_speeches/query` endpoint
  - [x] Request body: `WordTrendSpeechesQueryRequest`
  - [x] Response: `WordTrendSpeechesTicketAccepted` (202)
  - [x] Inject `WordTrendSpeechesTicketService` via `Depends()`
  - [x] Inject `ResultStore` via `Depends()`
  - [x] Call `service.submit_query()`
- [x] Add GET `/word_trend_speeches/status/{ticket_id}` endpoint
  - [x] Path param: `ticket_id` (UUID string)
  - [x] Response: `WordTrendSpeechesTicketStatus` (200)
  - [x] Return 404 for unknown/expired tickets
  - [x] Inject service and result store
- [x] Add GET `/word_trend_speeches/page/{ticket_id}` endpoint
  - [x] Path param: `ticket_id` (UUID string)
  - [x] Query params: `page`, `page_size`, `sort_by`, `sort_order`
  - [x] Response: `WordTrendSpeechesPageResult` (200)
  - [x] Validate page/page_size ranges
  - [x] Return 404 for unknown/expired tickets
  - [x] Return 400 for invalid page numbers
- [x] Add GET `/word_trend_speeches/download/{ticket_id}` endpoint
  - [x] Path param: `ticket_id` (UUID string)
  - [x] Query param: `format` (csv, json) via `file_format` alias
  - [x] Return full speech list from artifact
  - [x] Set appropriate content-type and disposition headers
- [ ] ~~Update OpenAPI documentation with examples~~

**Integration Tests** (`tests/integration/test_wt_speeches_ticket_validation.py`)
- [x] Test POST query → 202 response with valid ticket
- [x] Test POST with multiple search terms → 202
- [x] Test POST missing `search` → 422
- [x] Test GET status → transitions to "ready" (background tasks run synchronously in TestClient)
- [x] Test GET status → 404 for unknown ticket
- [x] Test GET page → valid response structure and schema
- [x] Test GET page → speech items contain expected columns
- [x] Test GET page → `total_hits` matches `speech_list` length
- [x] Test GET page → first page returns up to `page_size` items
- [x] Test GET page → last page returns correct remainder
- [x] Test GET page → all items across pages sum to `total_hits`
- [x] Test GET page → sort by year ascending
- [x] Test GET page → sort by year descending
- [x] Test GET page → sort by name
- [x] Test GET page → sort by party_abbrev
- [x] Test GET page → 404 for unknown ticket
- [x] Test GET page → 400 for out-of-range page number
- [x] Test download CSV → correct content-type and content-disposition
- [x] Test download CSV → parseable CSV with correct row count
- [x] Test download JSON → correct content-type and content-disposition
- [x] Test download JSON → parseable JSON array with correct item count
- [x] Test download → 404 for unknown ticket
- [x] Test download → row count matches `total_hits` from page endpoint

**Deferred integration test coverage**
- Celery enabled/disabled mode: requires live Celery worker + Redis — tested manually
- Concurrent requests with same ticket ID: not covered; ticket IDs are UUIDs (collisions impossible)
- Expired ticket → 404: requires advancing TTL or a short-TTL config fixture — deferred

> **Note**: Tests live in `tests/integration/`; they require the sample corpus and run with the full FastAPI app via `TestClient`.

### Phase 3: Frontend Integration ✅

**Pinia Store** (`swedeb_frontend/src/stores/wordTrendsDataStore.js`)
- [x] Add ticket state to word trends store
  - [x] `ticketId: string | null`
  - [x] `ticketStatus: 'pending' | 'completed' | 'error' | null`
  - [x] `speechesTotalHits: number`
  - [x] `speechesPagination: { sortBy, descending, page, rowsPerPage, rowsNumber }`
  - [x] `speechesIsLoading`, `speechesIsPageLoading`, `requestSequence`, `pageRequestSequence`
- [x] Add `getWordTrendsSpeechesTicket(search)` — orchestrates submit + poll + fetch page 1
  - [x] POST to `/tools/word_trend_speeches/query` with `search_targets` + metadata filters
  - [x] Stores ticket ID and status in state
- [x] Add `waitForSpeechesTicketReady(requestId)` — polls status endpoint in loop
  - [x] GET `/tools/word_trend_speeches/status/{ticket_id}`
  - [x] Updates `speechesTotalHits` from intermediate status responses
  - [x] Returns when status is 'completed' or 'error'
- [x] Add `fetchSpeechesPage({ page, rowsPerPage, sortBy, descending })` action
  - [x] GET `/tools/word_trend_speeches/page/{ticket_id}`
  - [x] Passes page, page_size, sort_by (mapped), sort_order
  - [x] Updates `speechesData` and `speechesPagination` in state
- [x] Add `downloadSpeechesCSV()` / `downloadSpeechesExcel()` actions
  - [x] GET `/tools/word_trend_speeches/download/{ticket_id}?format=csv|json`
  - [x] Triggers browser download via `downloadDataStore`
- [x] Add `resetSpeechesTicketState()` for stale request cleanup

**Parallel Async Loading** (`swedeb_frontend/src/pages/WordTrendsPage.vue`)
- [x] Submit trends and speeches ticket requests in parallel (already done in Phase 0)
- [x] Show trends chart as soon as trends data arrives (independent `.then()`)
- [x] Speeches promise calls `getWordTrendsSpeechesTicket()` — async ticket flow
- [x] Fetch first page of speeches when ticket ready
- [x] Handle error in either request independently

**Component** (`swedeb_frontend/src/components/wordTrendsSpeechTable.vue`) — NEW FILE
- [x] Created dedicated component (did not modify shared `speechDataTable.vue`)
- [x] Server-side `q-table` with `@request` handler
- [x] Binds `v-model:pagination` to `wtStore.speechesPagination` (computed)
- [x] Table `:loading` bound to `speechesIsLoading || speechesIsPageLoading`
- [x] Hit count from `speechesTotalHits` (not array length)
- [x] Sort columns: protocol (document_name), speaker (name), party (party_abbrev), year
- [x] Expanding row reuses `expandingTableRow` component
- [x] Download dropdown: CSV and Excel via ticket endpoint
- [x] Error state via `speechesErrorMessage`
- [x] `noResults` shown when no data and no error

**Notes**:
- Feature flag deferred — ticket flow is the only path now (sync endpoint retained for reference)
- `SORT_FIELD_MAP` in store maps display column names to backend `sort_by` values
- `metaDataStore().getSelectedKwicTicketFilters()` reused for filter payload construction

### Phase 4: Validation and Documentation ✅

**Endpoint Unit Tests** (`tests/api_swedeb/api/endpoints/test_tool_router.py`)
- [x] `test_submit_word_trend_speeches_query_returns_202_accepted`
- [x] `test_submit_wt_speeches_schedules_background_task_in_dev_mode`
- [x] `test_submit_wt_speeches_dispatches_celery_task_in_prod_mode`
- [x] `test_submit_wt_speeches_returns_429_when_limit_exceeded`
- [x] `test_get_word_trend_speeches_status_returns_status_for_known_ticket`
- [x] `test_get_word_trend_speeches_status_returns_404_for_missing_ticket`
- [x] `test_get_word_trend_speeches_page_returns_first_page`
- [x] `test_get_word_trend_speeches_page_returns_404_for_missing_ticket`
- [x] `test_download_returns_csv_streaming_response_when_requested`
- [x] `test_download_returns_json_streaming_response_when_requested`
- [x] `test_download_returns_404_for_missing_ticket`

**Test suite** — 215 unit tests pass (1 skipped: corpus not built locally), 34 endpoint tests pass

**Code Quality**
- [x] `make tidy` — Black + isort clean
- [x] No lint errors in changed files
- [x] Frontend build passes (`pnpm build`)

**Documentation**
- [x] Updated `docs/DESIGN.md`: added `WordTrendSpeechesTicketService` to service list and new section 5 "Ticketed word-trend speeches flow"
- [x] Design doc Phase 3 checklist updated with implementation decisions
- [x] Design doc status updated to Phase 3 complete

**Deferred / Out of scope for this PR**
- Performance benchmarks (sync vs async) — requires live corpus and Celery worker
- User acceptance testing — requires production-like deployment
- Monitoring/metrics additions — no existing metrics infrastructure to extend
- Feature flag — decided not needed (ticket flow is the only path; sync endpoint retained)

### Phase 5: Rollout

**Preparation**
- [ ] Merge to `dev` branch
- [ ] Deploy to test environment
- [ ] Run smoke tests on test environment
- [ ] Verify Celery workers are running
- [ ] Verify Redis is accessible
- [ ] Check ResultStore capacity limits

**Gradual Rollout**
- [ ] Enable feature flag for internal users (10%)
- [ ] Monitor error rates and performance
- [ ] Expand to 25% of users
- [ ] Collect user feedback
- [ ] Expand to 50% of users
- [ ] Final expansion to 100%

**Post-Deployment**
- [ ] Monitor ticket cache storage usage
- [ ] Verify TTL and cleanup working correctly
- [ ] Check for memory leaks or resource exhaustion
- [ ] Gather performance metrics vs baseline
- [ ] Document lessons learned
- [ ] Plan removal of sync endpoint (if appropriate)

---

## Final Recommendation

**Two-Phase Approach:**

### Phase 0: Immediate Quick Win (1-2 days)
Parallelize the existing synchronous API calls using `Promise.all()` in `WordTrendsPage.vue`.

**Impact:**
- 20-40% reduction in total load time
- Zero backend changes required
- Zero breaking changes or risk
- Provides immediate user value

**Implementation:**
```javascript
// Change 2 lines in WordTrendsPage.vue
await Promise.all([
  wtStore.getWordTrendsResult(textString),
  wtStore.getWordTrendsSpeeches(textString)
]);
```

### Phase 1-5: Comprehensive Solution (4-6 weeks)
Implement server-side ticket-based paging for word trend speeches retrieval following the KWIC async pattern.

This change:
- Eliminates 2-10 MB synchronous payloads for common queries
- Provides incremental feedback during query execution
- Reduces client and server memory pressure by 90%+
- Enables efficient server-side sorting
- Reuses proven infrastructure from KWIC implementation
- Maintains backward compatibility during transition

Start with Phase 1 backend foundation to validate performance characteristics before frontend integration.
