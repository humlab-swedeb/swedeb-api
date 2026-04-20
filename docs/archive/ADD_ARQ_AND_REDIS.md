# Add Arq and Redis for Background Task Execution

## Status

- Proposed feature / change request (alternative to Celery approach)
- Scope: Background task infrastructure for KWIC queries and future async operations
- Goal: Enable multiprocessing in KWIC queries without deadlocking FastAPI BackgroundTasks

## Summary

Add Arq with Redis as a lightweight async task queue to execute long-running KWIC queries in separate worker processes. Arq is simpler than Celery, async-native (built on asyncio), and integrates naturally with FastAPI. This enables multiprocessing-based query parallelization (8x speedup) which currently deadlocks when run from FastAPI BackgroundTasks.

## Problem

KWIC queries use multiprocessing to parallelize CQP corpus searches across year ranges, achieving near-linear speedup with the number of CPU cores. However, `multiprocessing.Pool().map()` blocks indefinitely when called from FastAPI's BackgroundTasks because background tasks run in a thread pool, not separate processes.

**Current workaround**: Multiprocessing is disabled via `kwic.use_multiprocessing: false` in config. This works but eliminates performance benefits for large queries spanning many years.

**Who is affected**: Users running KWIC searches on large year ranges or common words with many hits. Development is fine with singleprocessing; production with full corpus (1867-2022) will be slow.

## Scope

This proposal covers:

- Adding Arq as the task execution framework (async-native, lightweight alternative to Celery)
- Adding Redis as the message broker
- Migrating KWIC ticket execution from FastAPI BackgroundTasks to Arq tasks
- Configuration for worker processes and Redis connection
- Docker Compose integration for local development and deployment

## Non-Goals

- Migrating other background tasks unless they also need multiprocessing
- Advanced task features (periodic tasks, complex workflows) — Arq is intentionally minimal
- Alternative brokers (RabbitMQ, AWS SQS) — Arq only supports Redis
- Monitoring/observability infrastructure — Arq has basic monitoring, Celery Flower won't work

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

Replace FastAPI BackgroundTasks with Arq tasks:

```
POST /kwic/query → Create ticket → Enqueue Arq task → Return 202
                                          ↓
                                    Redis broker
                                          ↓
                              Arq worker process
                                          ↓
                          execute_ticket() with multiprocessing
                                          ↓
                              ResultStore (unchanged)
```

### Arq vs Celery Key Differences

| Aspect | Arq | Celery |
|--------|-----|--------|
| Design | Async-native (asyncio) | Sync with async bolt-on |
| Dependencies | Minimal (Redis only) | Many (kombu, billiard, etc.) |
| Configuration | Simple dict/class | Complex config system |
| Monitoring | Basic (built-in) | Rich (Flower, events) |
| Maturity | Newer, smaller ecosystem | Battle-tested, huge ecosystem |
| FastAPI fit | Excellent (same async model) | Good (but sync-based) |
| Learning curve | Low | High |

### Data Storage Responsibilities

**Redis stores** (small, ephemeral control plane):
- Task queue: Pending tasks waiting for worker pickup
- Task state: queued → in_progress → complete/failed
- Task metadata: Return values, error messages
- TTL: Configurable (default 1 hour)

**Filesystem stores** (large, persistent data plane):
- KWIC result DataFrames (feather format, can be MBs)
- ResultStore maintains current behavior
- TTL: 10 minutes (current policy)

**Why keep ResultStore**: Redis result storage is optional in Arq. Large KWIC queries (MBs) better suited to filesystem than serialized in Redis.

### Development Mode

To reduce development friction, support **synchronous task execution** in debug mode:

```yaml
# config/debug.config.yml
development:
  arq_enabled: false  # Use BackgroundTasks for local dev
```

```python
# Endpoint adapts to config
if ConfigValue("development.arq_enabled", default=True).resolve():
    await arq.enqueue_job("execute_ticket", ticket_id, request_data, cwb_opts)  # Production
else:
    background_tasks.add_task(execute_ticket, ...)  # Dev: BackgroundTasks + singleprocessing
```

**Benefits**:
- Simple development: No Redis, no worker process, native debugging works
- Production performance: Full Arq + multiprocessing
- Config-driven: Single flag switches behavior

**Trade-off**: Two code paths to maintain. Acceptable because paths are minimal (one if/else at task submission).

### Implementation Changes

**1. Add dependencies** (`pyproject.toml`):
```toml
arq = "^0.25.0"
redis = "^5.0.0"
```

**2. Create Arq worker setup** (`api_swedeb/arq_worker.py`):
```python
from arq import create_pool
from arq.connections import RedisSettings
from api_swedeb.core.configuration import ConfigValue

async def execute_ticket_task(ctx, ticket_id: str, request_data: dict, cwb_opts: dict):
    """
    Arq task for KWIC query execution.
    Runs in separate process - multiprocessing works.
    """
    from api_swedeb.api.services.kwic_ticket_service import execute_ticket
    
    # Execute in worker process (multiprocessing safe)
    execute_ticket(ticket_id, request_data, cwb_opts)
    
    return {"ticket_id": ticket_id, "status": "complete"}

class WorkerSettings:
    functions = [execute_ticket_task]
    redis_settings = RedisSettings(
        host=ConfigValue("arq.redis_host", default="localhost").resolve(),
        port=ConfigValue("arq.redis_port", default=6379).resolve(),
    )
    max_jobs = 4  # Concurrent tasks
    job_timeout = 600  # 10 minutes
```

**3. Create Arq pool for enqueueing** (`api_swedeb/arq_app.py`):
```python
from arq import create_pool
from arq.connections import RedisSettings
from api_swedeb.core.configuration import ConfigValue

async def get_arq_pool():
    """Get Arq Redis pool for enqueueing jobs."""
    settings = RedisSettings(
        host=ConfigValue("arq.redis_host", default="localhost").resolve(),
        port=ConfigValue("arq.redis_port", default=6379).resolve(),
    )
    return await create_pool(settings)
```

**4. Update endpoint** (`api_swedeb/api/v1/endpoints/tool_router.py`):
```python
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.arq_app import get_arq_pool

# Development mode: use BackgroundTasks (simple debugging)
if not ConfigValue("development.arq_enabled", default=True).resolve():
    background_tasks.add_task(execute_ticket, ticket_id, request_data, cwb_opts)
else:
    # Production mode: use Arq (multiprocessing support)
    arq_pool = await get_arq_pool()
    await arq_pool.enqueue_job("execute_ticket_task", ticket_id, request_data, cwb_opts)
```

**5. Configuration** (`config/config.yml`):
```yaml
arq:
  redis_host: localhost
  redis_port: 6379
  max_jobs: 4  # Worker concurrent tasks
  job_timeout: 600  # 10 minutes

kwic:
  use_multiprocessing: true  # Re-enable in production
  num_processes: 8

development:
  arq_enabled: true  # false for local dev
```

**Development config** (`config/debug.config.yml`):
```yaml
arq:
  redis_host: localhost
  redis_port: 6379

kwic:
  use_multiprocessing: false  # Keep disabled in dev (simpler)

development:
  arq_enabled: false  # Use BackgroundTasks for debugging
```

**6. Docker Compose** (`docker-compose.yml`):
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  arq-worker:
    build: .
    command: arq api_swedeb.arq_worker.WorkerSettings
    depends_on:
      - redis
    environment:
      SWEDEB_CONFIG_PATH: config/config.yml
```

**7. Podman Quadlet Configuration** (`docker/redis.container`, `docker/arq-worker.container`):

```ini
# docker/redis.container
[Unit]
Description=Redis for Swedeb Arq
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
# docker/arq-worker.container
[Unit]
Description=Swedeb Arq Worker
Requires=swedeb-staging-app.network redis.service
After=swedeb-staging-app.network redis.service

[Container]
Image=ghcr.io/humlab-swedeb/swedeb-api:staging
ContainerName=swedeb-arq-worker-staging
Network=swedeb-staging-app.network

# Mount same data volumes as API container
Volume=%h/data/v1.4.1:/data:ro
Volume=%h/configuration/secrets/config.yml:/app/config/config.yml:ro

# Arq needs writable temp for worker state
Tmpfs=/tmp:rw,nosuid,nodev,exec,size=1G

# Worker command
Exec=arq api_swedeb.arq_worker.WorkerSettings

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
   - Redis (production only) for Arq task queue and state
   ```

2. **Components and Responsibilities** - Update dependency list:
   ```
   The key services are:
   - CorpusLoader, MetadataService, SearchService, etc.
   - KWICTicketService: async KWIC with Arq tasks (production) or BackgroundTasks (dev)
   ```

3. **Key Flows - Ticketed KWIC flow** - Update to reflect two modes:
   ```
   Production mode (Arq):
   1. Client submits KWICQueryRequest
   2. KWICTicketService creates ticket
   3. Arq task enqueued to Redis (async)
   4. Separate worker process executes query with multiprocessing
   5. Results stored in ResultStore, basic job info in Redis
   6. Client polls ResultStore status, fetches results
   
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
   - Task state: queued → in_progress → complete/failed
   - Task metadata: small return values, errors
   - TTL: configurable (default 1 hour)
   
   ResultStore remains filesystem-backed for large KWIC DataFrames.
   Arq's async-native design fits naturally with FastAPI's async model.
   ```

5. **Design Decisions and Tradeoffs** - Add Arq decision:
   ```
   - Arq + Redis for background tasks: async-native task queue that fits
     FastAPI's async model. Simpler than Celery with fewer dependencies.
     Enables multiprocessing in separate worker processes (8x KWIC speedup).
     Development mode uses BackgroundTasks for simpler local workflow.
   ```

6. **Known Limitations** - Update multiprocessing limitation:
   ```
   - Multiprocessing requires Arq workers in production. Development mode
     uses BackgroundTasks which cannot use multiprocessing (Python limitation:
     mp.Pool() blocks from non-main threads).
   ```

### Status Endpoint Changes

Status endpoint can check Arq job state:

```python
from arq.jobs import Job

@router.get("/status/{ticket_id}")
async def get_status(ticket_id: str, arq_pool = Depends(get_arq_pool)):
    if ConfigValue("development.arq_enabled", default=True).resolve():
        # Production: Check Arq job state in Redis
        job = Job(ticket_id, arq_pool)
        info = await job.info()
        
        arq_to_ticket = {
            "queued": "pending",
            "in_progress": "pending",
            "complete": "ready",
            "not_found": "pending",  # May be too old or ResultStore only
        }
        
        if info and info.success is False:
            return {"status": "error"}
        
        status = arq_to_ticket.get(info.job_status if info else "not_found", "pending")
        return {"status": status}
    else:
        # Development: Use ResultStore (current behavior)
        return result_store.get_status(ticket_id)
```

### No Changes Required

- Result retrieval: `/v1/tools/kwic/results/{ticket_id}` uses ResultStore (unchanged)
- Result storage: `ResultStore` file-based data storage (unchanged)
- Frontend: No changes needed (same API contract)

## Alternatives Considered

**1. Celery + Redis** (more mature)
- More features: task chains, workflows, extensive monitoring
- Larger ecosystem: Flower, many integrations
- Heavier: More dependencies, complex configuration
- Sync-based: Less natural fit with FastAPI async
- Verdict: More powerful but heavier than needed

**2. ProcessPoolExecutor with asyncio**
- Simpler than both Arq and Celery
- No external dependencies (stdlib only)
- May still deadlock from BackgroundTasks thread context
- No task persistence, retries, or monitoring
- Verdict: Not reliable enough for production

**3. Threading instead of multiprocessing**
- Python GIL limits parallelism to I/O-bound tasks
- CQP queries are CPU-bound — threading offers no speedup
- Verdict: Does not solve the performance problem

**4. Keep singleprocessing permanently**
- Zero infrastructure cost
- Acceptable for development corpus
- Production corpus (1867-2022 full) will be slow for common words
- Verdict: Not viable long-term

## Risks And Tradeoffs

**Infrastructure complexity**:
- Adds Redis dependency and Arq worker process to deployment
- Simpler than Celery (fewer moving parts) but still adds operational surface
- Mitigation: Document in OPERATIONS.md, include health checks

**Development workflow**:
- Celery adds Redis + worker overhead locally
- Arq worker simpler to run than Celery
- Mitigation: Development mode (`arq_enabled: false`) eliminates infrastructure

**Arq maturity**:
- Smaller ecosystem than Celery
- Fewer monitoring tools (no Flower equivalent)
- Less battle-tested in large production systems
- Mitigation: Arq is well-designed, actively maintained, used in production by many companies

**Async requirement**:
- Arq requires async/await throughout task code
- Current `execute_ticket()` is sync
- Mitigation: Can wrap sync code in `asyncio.to_thread()` or run sync functions directly

**Migration**:
- Existing in-flight tickets during deployment will fail if worker process changes
- Mitigation: ResultStore TTL is 10 minutes; deploy during low-traffic window

**Testing**:
- Integration tests need Redis or mocking
- Mitigation: Default test config to `arq_enabled: false`

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
- Verify docker-compose brings up all services
- Verify local development with `arq api_swedeb.arq_worker.WorkerSettings` command
- Test development mode works without Redis (`arq_enabled: false`)

## Acceptance Criteria

- [ ] Arq and Redis dependencies added to `pyproject.toml`
- [ ] `arq_worker.py` created with WorkerSettings
- [ ] `arq_app.py` created for pool management
- [ ] `execute_ticket` wrapped as Arq task
- [ ] Development mode toggle (`arq_enabled` config) implemented
- [ ] Config files updated with `arq.*` and `development.*` settings
- [ ] Docker Compose includes Redis and arq-worker services
- [ ] Podman Quadlet files created: `redis.container`, `arq-worker.container`
- [ ] `docker/app.container` updated with Redis dependency
- [ ] Development mode works: BackgroundTasks path, native debugging, no Redis
- [ ] Production mode works: Arq path with multiprocessing enabled
- [ ] Performance benchmark shows speedup for large queries in production mode
- [ ] DESIGN.md updated with Arq architecture and data flow
- [ ] DEVELOPMENT.md documents both development and production modes
- [ ] OPERATIONS.md documents production Arq deployment
- [ ] Integration tests pass in development mode (no Redis needed)

## Recommended Delivery Order

1. **Infrastructure setup** (can test independently):
   - Add Arq and Redis dependencies
   - Create `arq_worker.py` with minimal WorkerSettings
   - Add Redis to docker-compose
   - Verify Arq worker starts with `arq api_swedeb.arq_worker.WorkerSettings`

2. **Development mode toggle** (reduce friction):
   - Add `development.arq_enabled` config flag
   - Implement conditional task submission (Arq vs BackgroundTasks)
   - Test development mode works without Redis
   - Ensure native debugging still works

3. **Task migration** (incremental):
   - Wrap `execute_ticket` as Arq async task
   - Create `arq_app.py` for pool management
   - Keep singleprocessing initially to validate task execution
   - Test end-to-end with Arq in production mode

4. **Enable multiprocessing** (final step):
   - Set `use_multiprocessing: true` in production config
   - Run performance benchmarks
   - Verify no deadlocks

5. **Documentation and deployment**:
   - Update DESIGN.md: architecture, data flow, design decisions
   - Update DEVELOPMENT.md: document both modes
   - Update OPERATIONS.md: production deployment
   - Create Podman Quadlet files for Redis and Arq worker
   - Update existing `app.container` to depend on Redis
   - Configure tests to use development mode by default
   - Document troubleshooting for common Arq issues

## Open Questions

- **Worker concurrency**: How many Arq max_jobs vs KWIC multiprocessing processes? Recommend: 4 workers × 8 KWIC processes = 32 total, tune based on profiling
- **Job timeout**: Should Arq enforce timeout for hung queries? Recommend: 600 seconds (10 min) initially
- **Async refactoring**: Should we refactor execute_ticket to be fully async? Recommend: Wrap sync code initially, refactor later if needed
- **Monitoring**: How to monitor Arq workers without Flower? Recommend: Use Arq's built-in health check endpoint + logs
- **Development mode default**: Should new developers default to `arq_enabled: false` or `true`? Recommend: `false` for simplicity

## Final Recommendation

Add Arq + Redis with **development mode toggle** to balance production performance with development simplicity.

**Production**: Arq task queue with multiprocessing for 8x KWIC speedup  
**Development**: BackgroundTasks with singleprocessing for native debugging

**Data storage**: Redis for task state (small, ephemeral), filesystem for KWIC results (large, optimized)

**Why Arq over Celery**:
- **Simpler**: Fewer dependencies, minimal configuration, easier to understand
- **Async-native**: Perfect fit for FastAPI's async model
- **Lightweight**: Smaller footprint, faster startup
- **Sufficient**: Meets all requirements without Celery's complexity
- **Trade-off**: Smaller ecosystem, fewer monitoring tools (acceptable for this use case)

This is a modern, lightweight approach to background task execution in FastAPI applications. Arq's simplicity makes it easier to maintain while still solving the multiprocessing deadlock.

Start with minimal Arq configuration focused on KWIC queries. Extend to other background tasks only if they also require multiprocessing or benefit from task queue features.

Prioritize delivery after current frontend work is complete to avoid conflicting development workflow changes.
