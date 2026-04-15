# Change Request: Paged KWIC / N-gram Results via Server-Side Result Cache

**Status**: Proposal  
**Area**: `api_swedeb/api/v1/endpoints/tool_router.py`, `KWICService`, `NGramsService`  
**Affects**: API, frontend (`kwicDataStore.js`, `kwicDataTable.vue`, `nGramsTable.vue`, `speechDataTableNgram.vue`)

---

## 1. Current Architecture

### Request/Response Flow

Both KWIC and n-gram results follow the same pattern:

```
Client → GET /v1/tools/kwic/{search}?<all-filters>&cut_off=100000
       ← 200 OK { "kwic_list": [ ...up to 100k items... ] }
```

1. The client issues a single synchronous GET with all filter parameters.
2. `KWICService.get_kwic()` runs a CWB/CQP corpus query, post-processes the result into a Pandas DataFrame, and the mapper serialises the entire list to JSON.
3. The entire result set is returned in one response body.
4. The frontend stores the full list in Pinia state (`kwicData`, `ngramData`) — resident in browser memory.
5. The `<q-table>` renders with **client-side paging** (10/20/50 rows per page); all slicing happens in the browser.

### Performance Implications

| Concern | Detail |
|---|---|
| **Large payloads** | A `cut_off=100000` KWIC result with context fields serialises to ~50–200 MB of JSON depending on hit density and field width. This is transferred on every search. |
| **Blocking server thread** | CWB/CQP is CPU-bound and synchronous. During query execution the FastAPI event loop is blocked for the duration of the corpus scan. |
| **No incremental feedback** | The browser shows nothing until the entire response arrives. Long queries (5–15 s at high `cut_off`) give a poor UX. |
| **Repeated full fetches** | Every filter change re-executes the full corpus query. There is no reuse of a previous matching set even when only the page or sort order changes. |
| **Memory pressure** | The server materialises the full hit list in a Pandas DataFrame before serialising. At 100k hits this can use 500 MB+ of RAM per concurrent user. |
| **Client memory** | The browser holds the entire result array in a reactive Pinia store; large lists can degrade Vue reactivity performance. |

---

## 2. Proposed Solution: Ticket-Based Server-Side Result Cache

### Core Concept

Split the current single call into two phases:

1. **Query phase** – Execute the corpus query and store the result in a short-lived server-side cache, return a `ticket_id` (opaque token) immediately.
2. **Page phase** – Client fetches pages by `ticket_id + page + page_size`.

This decouples corpus execution time from rendering time, enables incremental display, and allows the full dataset to be reused across page/sort/download operations without re-querying.

### API Design

#### Phase 1 — Submit query, obtain ticket

```http
POST /v1/tools/kwic/query
Content-Type: application/json

{
  "search": "demokrati",
  "lemmatized": true,
  "words_before": 5,
  "words_after": 5,
  "cut_off": 200000,
  "filters": { "from_year": 1970, "to_year": 2000, "party_id": [3] }
}
```

```http
200 OK
{
  "ticket_id": "3f2a1b4c-...",
  "total_hits": 4832,
  "expires_at": "2026-04-15T14:35:00Z"
}
```

The server runs the corpus query asynchronously (see §3), stores the result, and returns the ticket. Alternatively the server can accept the request and the client polls for readiness (see async variant below).

#### Phase 2 — Fetch a page

```http
GET /v1/tools/kwic/results/{ticket_id}?page=1&page_size=50&sort_by=year&sort_order=asc
```

```http
200 OK
{
  "ticket_id": "3f2a1b4c-...",
  "page": 1,
  "page_size": 50,
  "total_hits": 4832,
  "total_pages": 97,
  "expires_at": "2026-04-15T14:35:00Z",
  "kwic_list": [ ... 50 items ... ]
}
```

Sorting and filtering within the cached result set is handled server-side by slicing the stored DataFrame — no re-query needed.

#### Full download

```http
POST /v1/tools/speeches/download
?ticket_id=3f2a1b4c-...      ← reuse cached hit list, no speech_id body needed
```

The download endpoint recognises `ticket_id` (mutually exclusive with the `ids` body), retrieves the cached speech IDs, and streams the ZIP as before.

---

## 3. Implementation Approach

### Cache Backend

FastAPI does not bundle a result cache. Two well-established options fit our stack:

#### Option A — `cachetools.TTLCache` (in-process, zero dependencies)

```python
from cachetools import TTLCache
import uuid, threading

_RESULT_CACHE: TTLCache = TTLCache(maxsize=500, ttl=600)  # 10 min TTL, max 500 tickets
_CACHE_LOCK = threading.Lock()

def store_result(df: pd.DataFrame) -> str:
    ticket_id = str(uuid.uuid4())
    with _CACHE_LOCK:
        _RESULT_CACHE[ticket_id] = df
    return ticket_id

def get_result(ticket_id: str) -> pd.DataFrame | None:
    with _CACHE_LOCK:
        return _RESULT_CACHE.get(ticket_id)
```

**Pros**: No infrastructure change; works today; TTL eviction is automatic.  
**Cons**: Cache is not shared across multiple workers/processes. If `uvicorn` is started with `--workers N > 1`, tickets are not portable across worker processes. **Mitigated** by using a single worker behind a reverse proxy (current deployment model) or by pinning the client to a worker via sticky sessions.

#### Option B — Redis (distributed, production-grade)

Store the serialised DataFrame (Parquet bytes or Arrow IPC) under the ticket key with Redis `EXPIRE`.

```python
import redis, io, uuid
r = redis.Redis.from_url(os.environ["REDIS_URL"])

def store_result(df: pd.DataFrame) -> str:
    ticket_id = str(uuid.uuid4())
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    r.setex(ticket_id, 600, buf.getvalue())  # 10 min TTL
    return ticket_id
```

**Pros**: Multi-worker safe; survives process restart (configurable); can inspect/monitor live cache.  
**Cons**: Requires a Redis instance in `docker-compose`; adds a dependency.

**Recommendation**: Start with Option A (`cachetools`) for the current single-worker deployment. Add a `CACHE_BACKEND` config key (`memory` | `redis`) to allow migration to Option B without API changes when horizontal scaling is needed.

### Async Query Execution

CWB queries are CPU-bound. To avoid blocking the event loop:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

_EXECUTOR = ProcessPoolExecutor(max_workers=2)

@router.post("/kwic/query", response_model=KWICTicket)
async def submit_kwic_query(request: KWICQueryRequest, ...):
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(_EXECUTOR, kwic_service.get_kwic, ...)
    ticket_id = result_cache.store(df)
    return KWICTicket(ticket_id=ticket_id, total_hits=len(df), ...)
```

Alternatively, use `BackgroundTasks` or a job queue (e.g. `arq` or `celery`) and have the client poll `GET /v1/tools/kwic/status/{ticket_id}` for `{ "status": "pending" | "ready" | "error" }`. This enables a progress indicator in the UI.

### Server-Side Paging Endpoint

```python
@router.get("/kwic/results/{ticket_id}", response_model=KWICPageResult)
async def get_kwic_page(
    ticket_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("year"),
    sort_order: str = Query("asc"),
):
    df = result_cache.get(ticket_id)
    if df is None:
        raise HTTPException(status_code=404, detail="Ticket not found or expired")
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=(sort_order == "asc"))
    offset = (page - 1) * page_size
    page_df = df.iloc[offset : offset + page_size]
    return kwic_page_to_api_model(page_df, ticket_id, page, page_size, total=len(df))
```

### New Schemas

```python
class KWICTicket(BaseModel):
    ticket_id: str
    total_hits: int
    expires_at: datetime

class KWICPageResult(BaseModel):
    ticket_id: str
    page: int
    page_size: int
    total_hits: int
    total_pages: int
    expires_at: datetime
    kwic_list: list[KeywordInContextItem]
```

---

## 4. Frontend Changes

`kwicDataStore.js` becomes a two-call flow:

```javascript
async submitKwicQuery(search) {
  // Phase 1: submit, get ticket
  const response = await api.post(`/tools/kwic/query`, { search, ...params });
  this.ticket = response.data;           // { ticket_id, total_hits, expires_at }
  this.totalHits = response.data.total_hits;
  await this.fetchPage(1);
},

async fetchPage(page) {
  const response = await api.get(`/tools/kwic/results/${this.ticket.ticket_id}`, {
    params: { page, page_size: this.pageSize, sort_by: this.sortBy }
  });
  this.kwicData = response.data.kwic_list;
  this.currentPage = page;
},
```

The `<q-table>` switches from `rows` prop (full array) to server-side pagination mode (`@request` event triggers `fetchPage`). `total_hits` drives the Quasar pagination total.

For the ZIP download, pass `ticket_id` instead of a body of IDs:

```javascript
async downloadKWICAsSpeeches() {
  const path = `tools/speeches/download?ticket_id=${this.ticket.ticket_id}`;
  const response = await api.post(path, null, { responseType: "blob" });
  downloadDataStore().setupDownload("tal.zip", new Blob([response.data]));
}
```

---

## 5. Ticket Lifecycle & Security

| Concern | Mitigation |
|---|---|
| **Ticket guessing** | UUIDs (v4) are cryptographically random — 122 bits of entropy; not guessable. |
| **TTL** | 10 minutes default, configurable via `ConfigValue("cache.result_ttl_seconds")`. Eviction is automatic with `cachetools.TTLCache` / Redis `EXPIRE`. |
| **Cache size** | `maxsize=500` in-process (≈ 500 concurrent live tickets). Each KWIC DataFrame at 100k rows ≈ 50–100 MB; budget accordingly. Redis has no per-process memory limit. |
| **Ticket ownership** | For MVP: stateless — any client with the `ticket_id` can page it. Future: bind ticket to session/JWT claim if auth is added. |
| **Expired ticket UX** | Return HTTP 404 `"Ticket not found or expired"`. Frontend shows "Session expired — please search again." |

---

## 6. Migration Path

The existing `/kwic/{search}` GET endpoint should remain unchanged and undeprecated for backward compatibility. The ticket endpoints are additive.

| Phase | Scope |
|---|---|
| **Phase 1** | Add `POST /kwic/query`, `GET /kwic/results/{ticket_id}` with in-process cache. No frontend changes — validate backend only. |
| **Phase 2** | Update `kwicDataStore.js` + `kwicDataTable.vue` to use ticket flow. Switch `<q-table>` to server-side pagination. |
| **Phase 3** | Apply same pattern to n-grams (`/ngrams/query`, `/ngrams/results/{ticket_id}`). |
| **Phase 4** | Update `speeches/download` to accept `ticket_id` parameter. |
| **Phase 5** | Evaluate Redis if multi-worker deployment is needed. |
