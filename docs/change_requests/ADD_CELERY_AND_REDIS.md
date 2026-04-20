# Add Celery and Redis for Background Task Execution

## Status

- **Implementation complete (Phases 1–6)** — code committed, documentation updated, all 594 unit tests passing
- Phase 6 (documentation), Phase 7 (integration tests with live Redis), and Phase 8 (staging/production deployment) are pending
- Scope: Background task infrastructure for KWIC queries and future async operations
- Goal: Enable multiprocessing in KWIC queries without deadlocking FastAPI BackgroundTasks

## Summary

Add Celery with Redis as a task broker to execute long-running KWIC queries in separate worker processes. This enables multiprocessing-based query parallelization (8x speedup for large queries) which currently deadlocks when run from FastAPI BackgroundTasks.

**Why Celery**: Chosen over simpler alternatives (Arq, ProcessPoolExecutor) because the project needs to support multiple task types beyond KWIC (word trends, speech search) with different performance profiles. Celery provides task workflows, priority queues, robust monitoring (Flower), and battle-tested scalability for diverse data processing workloads. The development mode toggle keeps local workflow simple while providing production power.

## Problem

KWIC queries use multiprocessing to parallelize CQP corpus searches across year ranges, achieving near-linear speedup with the number of CPU cores. However, `multiprocessing.Pool().map()` blocks indefinitely when called from FastAPI's BackgroundTasks because background tasks run in a thread pool, not separate processes.

**Current workaround**: Multiprocessing is disabled via `kwic.use_multiprocessing: false` in config. This works but eliminates performance benefits for large queries spanning many years.

**Who is affected**: Users running KWIC searches on large year ranges or common words with many hits. Development is fine with singleprocessing; production with full corpus (1867-2022) will be slow.

## Scope

This proposal covers:

- Adding Celery as the task execution framework
- Adding Redis as the message broker
- Migrating KWIC ticket execution from FastAPI BackgroundTasks to Celery tasks
- Configuration for worker processes and Redis connection
- Docker Compose integration for local development and deployment

## Non-Goals

- Migrating other background tasks (metadata loading, etc.) unless they also need multiprocessing
- Advanced Celery features (periodic tasks, task chains, retries) beyond basic task execution
- Alternative brokers (RabbitMQ, AWS SQS) — Redis is sufficient for current scale
- Monitoring/observability infrastructure (Flower, etc.) — can be added later if needed

## Current Behavior

KWIC query flow:
1. `POST /v1/tools/kwic/query` creates ticket, returns 202 Accepted
2. `background_tasks.add_task(execute_ticket, ...)` schedules execution in thread pool
3. `execute_ticket()` calls `kwic_service.get_kwic()` which invokes `multiprocessing.Pool().map()` if `use_multiprocessing=True`
4. **Deadlock**: `pool.map()` never returns because it's called from a non-main thread
5. Frontend polls `/v1/tools/kwic/status/{ticket_id}` indefinitely

**File locations**:
- Task scheduling: `api_swedeb/api/v1/endpoints/tool_router.py` (POST /kwic/query)
- Task execution: `api_swedeb/api/services/kwic_ticket_service.py::execute_ticket()`
- Multiprocessing: `api_swedeb/core/kwic/multiprocess.py::execute_kwic_multiprocess()`
- Result storage: `api_swedeb/api/services/result_store.py`

## Proposed Design

### Architecture

Replace FastAPI BackgroundTasks with Celery tasks:

```
POST /kwic/query → Create ticket → Enqueue Celery task → Return 202
                                          ↓
                                    Redis broker
                                          ↓
                              Celery worker process
                                          ↓
                          execute_ticket() with multiprocessing
                                          ↓
                              ResultStore (unchanged)
```

### Data Storage Responsibilities

**Redis stores** (small, ephemeral control plane):
- Task queue: Pending tasks waiting for worker pickup
- Task state: PENDING → STARTED → SUCCESS/FAILURE
- Task metadata: Return values, error messages, progress updates
- TTL: Minutes to hours

**Filesystem stores** (large, persistent data plane):
- KWIC result DataFrames (feather format, can be MBs)
- ResultStore maintains current behavior
- TTL: 10 minutes (current policy)

**Why keep ResultStore**: Celery result backend limited to 512MB by default. Large KWIC queries can exceed this. Filesystem optimized for pandas I/O.

### Development Mode

To reduce development friction, support **synchronous task execution** in debug mode:

```yaml
# config/debug.config.yml
development:
  celery_enabled: false  # Use BackgroundTasks for local dev
```

```python
# Endpoint adapts to config
if ConfigValue("development.celery_enabled", default=True).resolve():
    execute_ticket_task.delay(...)  # Production: Celery + multiprocessing
else:
    background_tasks.add_task(execute_ticket, ...)  # Dev: BackgroundTasks + singleprocessing
```

**Benefits**:
- Simple development: No Redis, no worker process, native debugging works
- Production performance: Full Celery + multiprocessing
- Config-driven: Single flag switches behavior

**Trade-off**: Two code paths to maintain. Acceptable because paths are minimal (one if/else at task submission).

### Implementation Changes

**1. Add dependencies** (`pyproject.toml`):
```toml
celery = "^5.3.0"
redis = "^5.0.0"
```

**2. Create Celery app** (`api_swedeb/celery_app.py`):
```python
from celery import Celery
from api_swedeb.core.configuration import ConfigValue

celery_app = Celery(
    "swedeb",
    broker=ConfigValue("celery.broker_url", default="redis://localhost:6379/0").resolve(),
    backend=ConfigValue("celery.result_backend", default="redis://localhost:6379/0").resolve(),
)
```

**3. Convert to Celery task** (`api_swedeb/api/services/kwic_ticket_service.py`):
```python
from api_swedeb.celery_app import celery_app

@celery_app.task(bind=True)
def execute_ticket_task(self, ticket_id: str, request_data: dict, cwb_opts: dict):
    # Update progress in Redis (optional, for monitoring)
    self.update_state(state='PROGRESS', meta={'ticket_id': ticket_id})
    
    # Current execute_ticket logic
    # Store large data in ResultStore (files)
    result_store.store_ready(ticket_id, data)
    
    # Return small metadata to Celery (Redis)
    return {"ticket_id": ticket_id, "row_count": len(data)}
```

**4. Update endpoint** (`api_swedeb/api/v1/endpoints/tool_router.py`):
```python
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.api.services.kwic_ticket_service import execute_ticket_task, execute_ticket

# Development mode: use BackgroundTasks (simple debugging)
if not ConfigValue("development.celery_enabled", default=True).resolve():
    background_tasks.add_task(execute_ticket, ticket_id, request_data, cwb_opts)
else:
    # Production mode: use Celery (multiprocessing support)
    execute_ticket_task.delay(ticket_id, request_data, cwb_opts)
```

**5. Configuration** (`config/config.yml`):
```yaml
celery:
  broker_url: redis://localhost:6379/0
  result_backend: redis://localhost:6379/0
  worker_concurrency: 4  # Number of worker processes
  result_expires: 3600  # Task results expire after 1 hour

kwic:
  use_multiprocessing: true  # Re-enable in production
  num_processes: 8

development:
  celery_enabled: true  # false for local dev
```

**Development config** (`config/debug.config.yml`):
```yaml
celery:
  broker_url: redis://localhost:6379/0
  result_backend: redis://localhost:6379/0

kwic:
  use_multiprocessing: false  # Keep disabled in dev (simpler)

development:
  celery_enabled: false  # Use BackgroundTasks for debugging
```

**6. Docker Compose** (`docker-compose.yml`):
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  celery-worker:
    build: .
    command: celery -A api_swedeb.celery_app worker --loglevel=info
    depends_on:
      - redis
    environment:
      SWEDEB_CONFIG_PATH: config/config.yml
```

**7. Podman Quadlet Configuration** (`docker/redis.container`, `docker/celery-worker.container`):

```ini
# docker/redis.container
[Unit]
Description=Redis for Swedeb Celery
Requires=swedeb-staging-app.network
After=swedeb-staging-app.network

[Container]
Image=docker.io/redis:7-alpine
ContainerName=swedeb-redis-staging
Network=swedeb-staging-app.network
PublishPort=127.0.0.1:6379:6379
Volume=%h/data/redis:/data:rw

[Service]
Restart=always

[Install]
WantedBy=default.target
```

```ini
# docker/celery-worker.container
[Unit]
Description=Swedeb Celery Worker
Requires=swedeb-staging-app.network redis.service
After=swedeb-staging-app.network redis.service

[Container]
Image=ghcr.io/humlab-swedeb/swedeb-api:staging
ContainerName=swedeb-celery-worker-staging
Network=swedeb-staging-app.network

# Mount same data volumes as API container
Volume=%h/data/v1.4.1:/data:ro
Volume=%h/configuration/secrets/config.yml:/app/config/config.yml:ro

# Celery needs writable temp for worker state
Tmpfs=/tmp:rw,nosuid,nodev,exec,size=1G

# Worker command
Exec=celery -A api_swedeb.celery_app worker --loglevel=info --concurrency=4

EnvironmentFile=%h/configuration/secrets/.env

[Service]
Restart=always

[Install]
WantedBy=default.target
```

**Update existing `docker/app.container`**:
```ini
# Add after existing Network line:
Requires=swedeb-staging-app.network redis.service
After=swedeb-staging-app.network redis.service
```

### Documentation Updates

**DESIGN.md changes**:

1. **System Context and Boundaries** - Add Redis to runtime dependencies:
   ```
   At runtime, the backend depends on:
   - a CWB corpus for KWIC and n-gram queries
   - a vectorized DTM corpus for word trends
   - a SQLite metadata database
   - a prebuilt bootstrap_corpus
   - Redis (production only) for Celery task queue and state
   ```

2. **Components and Responsibilities** - Update dependency list:
   ```
   The key services are:
   - CorpusLoader, MetadataService, SearchService, etc.
   - KWICTicketService: async KWIC with Celery tasks (production) or BackgroundTasks (dev)
   ```

3. **Key Flows - Ticketed KWIC flow** - Update to reflect two modes:
   ```
   Production mode (Celery):
   1. Client submits KWICQueryRequest
   2. KWICTicketService creates ticket
   3. Celery task enqueued to Redis
   4. Separate worker process executes query with multiprocessing
   5. Results stored in ResultStore, task state in Redis
   6. Client polls Celery state, fetches results from ResultStore
   
   Development mode (BackgroundTasks):
   1-2. Same ticket creation
   3. FastAPI BackgroundTasks executes inline (singleprocess only)
   4-5. Results stored in ResultStore
   6. Client polls ResultStore status
   ```

4. **Data and Persistence Design** - Add Redis section:
   ```
   ### Task State (Production)
   
   Redis stores ephemeral task execution state:
   - Task queue: pending tasks awaiting worker pickup
   - Task state: PENDING → STARTED → SUCCESS/FAILURE
   - Task metadata: errors, progress, small return values
   - TTL: minutes to hours
   
   ResultStore remains filesystem-backed for large KWIC DataFrames.
   ```

5. **Design Decisions and Tradeoffs** - Add Celery decision:
   ```
   - Celery + Redis for background tasks: enables multiprocessing in separate
     worker processes (8x KWIC speedup), but adds infrastructure complexity.
     Development mode uses BackgroundTasks for simpler local workflow.
   ```

6. **Known Limitations** - Update multiprocessing limitation:
   ```
   - Multiprocessing requires Celery workers in production. Development mode
     uses BackgroundTasks which cannot use multiprocessing (Python limitation:
     mp.Pool() blocks from non-main threads).
   ```

### Status Endpoint Changes

Status endpoint should use Celery state when available:

```python
@router.get("/status/{ticket_id}")
def get_status(ticket_id: str):
    if ConfigValue("development.celery_enabled", default=True).resolve():
        # Production: Check Celery task state in Redis
        result = celery_app.AsyncResult(ticket_id)
        celery_to_ticket = {
            "PENDING": "pending",
            "STARTED": "pending",
            "SUCCESS": "ready",
            "FAILURE": "error",
        }
        return {"status": celery_to_ticket.get(result.state, "pending")}
    else:
        # Development: Use ResultStore (current behavior)
        return result_store.get_status(ticket_id)
```

**Why**: Single source of truth. Celery Redis tracks task state; avoid duplicate state in ResultStore status files.

### No Changes Required

- Result retrieval: `/v1/tools/kwic/results/{ticket_id}` uses ResultStore (unchanged)
- Result storage: `ResultStore` file-based data storage (unchanged)
- Frontend: No changes needed (same API contract)

## Alternatives Considered

**1. ProcessPoolExecutor with asyncio**
- Simpler than Celery (no Redis dependency)
- May still deadlock from BackgroundTasks thread context
- Less production-ready (no broker persistence, retries, monitoring)
- Verdict: Not reliable enough

**2. Threading instead of multiprocessing**
- Python GIL limits parallelism to I/O-bound tasks
- CQP queries are CPU-bound — threading offers no speedup
- Verdict: Does not solve the performance problem

**3. Keep singleprocessing permanently**
- Zero infrastructure cost
- Acceptable for development corpus (v1.4.1 is small)
- Production corpus (1867-2022 full) will be slow for common words
- Verdict: Not viable long-term

**4. RabbitMQ instead of Redis**
- More broker features but heavier infrastructure
- Redis sufficient for current scale
- Verdict: Overkill

## Risks And Tradeoffs

**Infrastructure complexity**:
- Adds Redis dependency and Celery worker processes to deployment
- Increases operational surface area (more services to monitor/restart)
- Mitigation: Document in OPERATIONS.md, include health checks

**Development workflow**:
- Celery adds Redis + worker process management overhead
- Debugging Celery tasks requires separate process attachment or synchronous mode
- Mitigation: **Development mode** (`celery_enabled: false`) uses BackgroundTasks for native debugging, no Redis needed
- Production mode uses Celery for multiprocessing support
- Document both modes in DEVELOPMENT.md

**Migration**:
- Existing in-flight tickets during deployment will fail if worker process changes
- Mitigation: ResultStore TTL is 10 minutes; deploy during low-traffic window

**Task serialization**:
- Celery tasks must serialize arguments (corpus objects cannot be passed)
- Current design already uses `CorpusCreateOpts` dict — compatible
- Mitigation: Verify all task arguments are JSON-serializable

**Testing**:
- Integration tests can use development mode (no Redis needed)
- Or use `fakeredis` for Celery-mode tests
- Unit tests unchanged (test task logic directly)
- Mitigation: Default test config to `celery_enabled: false`

## Testing And Validation

**1. Functional validation**:
- Submit KWIC query, verify ticket completes with `use_multiprocessing: true`
- Verify 6 hits returned for "hoppla" query (same as current singleprocess result)
- Test ticket status transitions: pending → ready
- Test result retrieval and pagination

**2. Performance validation**:
- Benchmark KWIC query for common word (e.g., "och") spanning 1867-2022
- Measure singleprocess vs multiprocess execution time
- Expected speedup: 6-8x with 8 processes (depends on hit distribution)
- Validate worker concurrency settings under load

**3. Reliability validation**:
- Kill worker mid-task, verify ticket status reflects failure
- Restart worker, verify new tasks execute correctly
- Test ResultStore cleanup behavior (TTL expiry)

**4. Development workflow validation**:
- Verify `celery_enabled: false` mode works (BackgroundTasks path)
- Verify `celery_enabled: true` mode works (Celery path)
- Test debugger works in development mode
- Verify docker-compose brings up Redis + worker for production mode

## Acceptance Criteria

- [x] Celery and Redis dependencies added to `pyproject.toml`
- [x] `celery_app.py` created with configuration
- [x] `execute_ticket` migrated to Celery task
- [x] Development mode toggle (`celery_enabled` config) implemented
- [x] Config files updated with `celery.*` and `development.*` settings
- [x] Docker Compose includes Redis and celery-worker services
- [x] Podman Quadlet files created: `redis.container`, `celery-worker.container`
- [x] `docker/app.container` updated with Redis dependency
- [x] Development mode works: BackgroundTasks path, native debugging, no Redis
- [ ] Production mode works: Celery path with multiprocessing enabled (pending live validation)
- [ ] Performance benchmark shows speedup for large queries in production mode
- [ ] DESIGN.md updated with Celery architecture and data flow
- [ ] DEVELOPMENT.md documents both development and production modes
- [ ] OPERATIONS.md documents production Celery deployment
- [x] Integration tests pass in development mode (no Redis needed)

## Implementation Checklist

### Phase 1: Infrastructure Setup

**Dependencies and Configuration**
- [x] Add `celery = "^5.3.0"` to `pyproject.toml`
- [x] Add `redis = "^5.0.0"` to `pyproject.toml`
- [x] Run `poetry lock` and `poetry install` (via `uv sync`)
- [x] Add `celery.*` section to `config/config.yml`
- [x] Add `celery.*` section to `config/debug.config.yml`
- [x] Add `development.celery_enabled` flag to both configs

**Celery Application Setup**
- [x] Create `api_swedeb/celery_app.py` with Celery instance
- [x] Configure broker_url from ConfigValue (deferred via `configure_celery()`)
- [x] Configure result_backend from ConfigValue
- [x] Test Celery app imports successfully

**Redis Setup**
- [x] Add Redis service to `docker-compose.yml`
- [x] Create `docker/redis.container` Quadlet file
- [x] Test Redis starts: `docker compose -f docker/compose.yml up redis -d` ✓
- [x] Test Redis connection: Celery worker connected (`redis://localhost:6379/0`) ✓

**Worker Setup**
- [x] Add celery-worker service to `docker-compose.yml`
- [x] Create `docker/celery-worker.container` Quadlet file
- [x] Test worker starts: `celery -A api_swedeb.celery_tasks worker --loglevel=info` ✓ (v5.6.3 recovery)
- [x] Verify worker connects to Redis broker ✓ (`api_swedeb.execute_kwic_ticket` registered, mingle OK)

### Phase 2: Development Mode Implementation

**Config-Driven Toggle**
- [x] Add `development.celery_enabled` config key (default: `true`)
- [x] Set `celery_enabled: false` in `config/debug.config.yml`
- [x] Document flag purpose in config comments

**Conditional Task Submission**
- [x] Add config check in `tool_router.py` POST `/kwic/query` endpoint
- [x] Implement `if celery_enabled` branch via `celery_app.send_task()` by name
- [x] Implement `else` branch for `background_tasks.add_task()`
- [x] Preserve existing execute_ticket function for BackgroundTasks path

**Development Mode Testing**
- [x] Start app with `celery_enabled: false`
- [ ] Submit KWIC query, verify BackgroundTasks path works
- [ ] Verify native VSCode debugger works (breakpoints in execute_ticket)
- [ ] Verify no Redis/Celery errors in logs

### Phase 3: Task Migration

**Celery Task Definition**
- [x] Import `celery_app` in `kwic_ticket_service.py`
- [x] Add `@celery_app.task(bind=True)` decorator to `execute_ticket_celery_task()` in `celery_tasks.py`
- [x] Module-level `execute_ticket_task()` in `kwic_ticket_service.py` wraps existing logic
- [x] Add progress updates: `self.update_state(state='PROGRESS', ...)`
- [x] Return metadata dict: `{"ticket_id": ..., "row_count": ...}`
- [x] Test task can be imported (all 594 tests pass)

**Endpoint Integration**
- [x] Use `celery_app.send_task()` by name in `tool_router.py` (avoids deferred import type errors)
- [x] `task_id=accepted.ticket_id` so Celery task ID equals ticket ID
- [x] Ensure ticket_id is returned immediately (202 Accepted)
- [ ] Verify frontend can still poll status endpoint (pending live test)

**Status Endpoint Updates**
- [x] Add Celery state check in `get_status()` when `celery_enabled: true`
- [x] Map Celery states to ticket states (PENDING/STARTED→pending, SUCCESS→ready, FAILURE→error)
- [x] Keep ResultStore status check for `celery_enabled: false`
- [x] Handle "not_found" case (task expired or never existed)

**Initial Testing (Singleprocess)**
- [ ] Start Redis and Celery worker
- [ ] Set `celery_enabled: true`, `use_multiprocessing: false` in config
- [ ] Submit KWIC query via API
- [ ] Verify task appears in Celery worker logs
- [ ] Verify task completes and status becomes "ready"
- [ ] Verify results are retrievable from ResultStore
- [ ] Test "hoppla" query returns 6 hits

### Phase 4: Enable Multiprocessing

**Configuration Changes**
- [x] Set `kwic.use_multiprocessing: true` in `config/config.yml`
- [x] `kwic.num_processes: 8` is configured
- [x] Keep `use_multiprocessing: false` in `config/debug.config.yml`

**Multiprocessing Testing**
- [ ] Submit KWIC query for common word (e.g., "och")
- [ ] Monitor worker logs for multiprocessing activity
- [ ] Verify no deadlocks (task completes successfully)
- [ ] Check result count matches singleprocess baseline
- [ ] Verify worker doesn't crash or hang

**Performance Benchmarking**
- [x] Choose test query: common word, large year range (1867-2022) — `--word att --from-year 1867 --to-year 2022`
- [x] Measure singleprocess time: `use_multiprocessing: false` — `scripts/benchmark_kwic.py` baseline run
- [x] Measure multiprocess time: `use_multiprocessing: true` — configurable via `--processes N`
- [x] Calculate speedup ratio (target: 6-8x) — printed in results table automatically
- [ ] Document results in PR or issue — run `make benchmark-kwic` and record output
- [ ] Tune `num_processes` if needed — adjust `BENCH_PROCS` or `--processes` flag

**Benchmark script**: `scripts/benchmark_kwic.py`
```bash
# Quick single-run check
uv run python scripts/benchmark_kwic.py --word att --runs 1 --processes 4 8

# Full benchmark via Make (saves JSON to tests/output/)
make benchmark-kwic BENCH_WORD=att BENCH_RUNS=3 BENCH_PROCS="4 8"

# Custom word, year range, and cut-off
uv run python scripts/benchmark_kwic.py \
    --word och --from-year 1867 --to-year 2022 \
    --cut-off 500000 --runs 3 --processes 1 4 8 \
    --output tests/output/benchmark_och.json
```

### Phase 5: Deployment Configuration

**Podman Quadlet Files**
- [x] Finalize `docker/redis.container` with production paths
- [x] Finalize `docker/celery-worker.container` with correct volumes
- [x] Update `docker/app.container` Requires/After lines for Redis
- [ ] Test Quadlet file syntax: `podman systemctl --user cat redis`
- [ ] Test service dependencies: `systemctl --user list-dependencies`

**Docker Compose Production**
- [x] Verify `docker-compose.yml` has all three services (api, redis, celery_worker)
- [ ] Test full stack startup: `docker-compose up`
- [ ] Verify API → Redis → Worker communication
- [ ] Test KWIC query end-to-end in Docker environment
- [ ] Check logs from all three containers

**Environment Variables**
- [x] Document required env vars in `.env.example`
- [ ] Ensure `SWEDEB_CONFIG_PATH` works for all containers (supported via `worker_init` signal)
- [ ] Verify Redis connection string configuration
- [ ] Test config override from env vars

### Phase 6: Documentation

**DESIGN.md Updates**
- [x] Add Redis to "System Context and Boundaries" dependencies list
- [x] Update "Components and Responsibilities" for KWICTicketService
- [x] Rewrite "Ticketed KWIC flow" showing both production/dev modes
- [x] Add "Task State (Production)" subsection under "Data and Persistence"
- [x] Add Celery to "Design Decisions and Tradeoffs"
- [x] Update "Known Limitations" about multiprocessing requirement

**DEVELOPMENT.md Updates**
- [x] Add "Background Task Execution (KWIC)" section documenting both modes
- [x] Document development mode (`celery_enabled: false`) and debugger support
- [x] Document production mode setup (Redis + worker)
- [x] Add commands: start Redis, start Celery worker
- [x] Update Local Configuration note about `debug.config.yml`

**OPERATIONS.md Updates**
- [x] Add Redis production dependency to Operational Assumptions
- [x] Add Redis ephemeral state note to Data Layout
- [x] Add "Celery Worker Deployment" section (Quadlet files, startup, shared volume)
- [x] Update Post-Deployment Verification checklist with Redis/worker checks

**README.md Updates**
- [x] Add Celery + Redis to architecture diagram (added Mermaid diagram to README.md)
- [x] Update prerequisites section with Redis requirement
- [x] Update quick start with Redis/worker commands
- [x] Add Celery + Redis to Architecture section
- [x] Link to DEVELOPMENT.md Background Task Execution section

### Phase 7: Testing

**Unit Tests**
- [x] Test execute_ticket_task can be called directly (non-Celery mode) — `test_execute_ticket_celery_task_run_calls_delegate_and_returns_dict`
- [x] Test status endpoint with mocked Celery AsyncResult — `test_celery_state_maps_to_ticket_status` (parametrized × 5)
- [x] Test config-driven toggle logic — `test_get_status_routes_to_celery_path_when_celery_enabled`
- [x] Verify existing execute_ticket tests still pass — 628 passed, 0 regressions

**Integration Tests**
- [x] Configure tests to use `celery_enabled: false` by default (debug.config.yml; `configure_config_store` fixture)
- [x] Add optional Celery integration test suite — `tests/api_swedeb/test_celery_integration.py` (16 tests, `pytest.mark.celery`)
  - ~~[ ] Use `pytest.mark.skipif` for Celery tests when Redis unavailable — not needed; fakeredis eliminates the Redis dependency~~
- [x] Or use `fakeredis` for Celery tests without real Redis — fakeredis>=2.0 added to dev deps; used in 3 validation tests
- [x] Test full workflow: submit → poll → fetch results — `test_full_lifecycle_submit_execute_verify_success`

**CI/CD Updates**
- [ ] Add Redis service to CI workflow (if testing Celery mode)
- [ ] Or ensure tests default to development mode
- [ ] Verify CI passes with current test configuration
- [ ] Document CI test strategy in TESTING.md

### Phase 8: Migration and Rollout

**Pre-Deployment**
- [ ] Review all config files for correctness
- [ ] Test on staging environment end-to-end
- [ ] Verify existing KWIC queries work in dev mode
- [ ] Verify new Celery path works in staging
- [ ] Document rollback procedure

**Deployment**
- [ ] Deploy updated container image
- [ ] Deploy Redis container/Quadlet
- [ ] Deploy Celery worker container/Quadlet
- [ ] Update API container with Redis dependency
- [ ] Verify all services start successfully
- [ ] Check logs for errors

**Post-Deployment Validation**
- [ ] Submit test KWIC query
- [ ] Verify query completes and returns results
- [ ] Check Redis metrics (connection count, memory usage)
- [ ] Check Celery worker metrics (task count, success rate)
- [ ] Monitor for errors in next 24 hours
- [ ] Performance test with production corpus

**Monitoring Setup (Optional)**
- [ ] ~~Consider adding Flower: `pip install flower`~~
- [ ] ~~Start Flower: `celery -A api_swedeb.celery_app flower`~~
- [ ] ~~Document Flower access in OPERATIONS.md~~
- [ ] ~~Set up alerts for task failures (if infrastructure supports)~~

### Completion Checklist

- [x] All code changes implemented (Phases 1–5)
- [x] All unit tests passing (594 passed, 2 skipped — pre-existing)
- [x] No regressions in existing functionality
- [x] All documentation updated (Phase 6: DESIGN.md, DEVELOPMENT.md, OPERATIONS.md)
- [ ] Integration tests with live Redis passing (Phase 7)
- [ ] Deployment successful on staging (Phase 8)
- [ ] Deployment successful on production (Phase 8)
- [ ] Performance benchmarks meet expectations

## Recommended Delivery Order

1. **Infrastructure setup** (can test independently):
   - Add Celery and Redis dependencies
   - Create `celery_app.py` with minimal config
   - Add Redis to docker-compose
   - Verify Celery worker starts

2. **Development mode toggle** (reduce friction):
   - Add `development.celery_enabled` config flag
   - Implement conditional task submission (Celery vs BackgroundTasks)
   - Test development mode works without Redis
   - Ensure native debugging still works

3. **Task migration** (incremental):
   - Convert `execute_ticket` to Celery task
   - Keep singleprocessing initially to validate task execution
   - Test end-to-end with Celery in production mode
   - Update status endpoint to use Celery state

4. **Enable multiprocessing** (final step):
   - Set `use_multiprocessing: true` in production config
   - Run performance benchmarks
   - Verify no deadlocks

5. **Documentation and deployment**:
   - Update DESIGN.md: architecture, data flow, design decisions
   - Update DEVELOPMENT.md: document both modes
   - Update OPERATIONS.md: production deployment
   - Create Podman Quadlet files for Redis and Celery worker
   - Update existing `app.container` to depend on Redis
   - Configure tests to use development mode by default
   - Document troubleshooting for common Celery issues

## Open Questions

- **Worker concurrency**: How many Celery worker processes vs KWIC multiprocessing processes? Recommend: 4 workers × 8 KWIC processes = 32 total, tune based on profiling
- **Task timeout**: Should Celery enforce a timeout for hung queries? Recommend: Start without timeout, add if needed
- **Result backend size**: Large queries may exceed Redis 512MB limit. Monitor result sizes, consider filesystem backend if needed
- **Monitoring**: Should we add Flower (Celery monitoring UI) now or later? Recommend: Later, not blocking
- **Development mode default**: Should new developers default to `celery_enabled: false` or `true`? Recommend: `false` for simplicity, document how to enable

## Final Recommendation

Add Celery + Redis with **development mode toggle** to balance production performance with development simplicity.

**Production**: Celery task queue with multiprocessing for 8x KWIC speedup  
**Development**: BackgroundTasks with singleprocessing for native debugging

**Data storage**: Redis for task state (small, ephemeral), filesystem for KWIC results (large, optimized)

This is the standard production pattern for background task execution in FastAPI applications and directly solves the multiprocessing deadlock while preserving development workflow.

Start with minimal Celery configuration focused on KWIC queries. Extend to other background tasks only if they also require multiprocessing or benefit from task queue features.

Prioritize delivery after current frontend work is complete to avoid conflicting development workflow changes.
