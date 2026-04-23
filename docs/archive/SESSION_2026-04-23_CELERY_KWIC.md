# Session Resume Note: Celery, Redis, KWIC, and Staging Deployment

## Purpose

This file stores a resumable summary of the April 22-23, 2026 Codex session around:

- Podman/Quadlet staging deployment failures
- Redis/Celery connectivity
- ticketed KWIC and word-trend speeches behavior
- KWIC multiprocessing under Celery

It is a high-signal resume note, not a literal full transcript.

## Repo State At Time Of Note

- Repository: `swedeb-api`
- Branch: `dev`
- `HEAD`: `dbfd9e936e298cfafe78d1f339a25ee8152d3016`
- Working tree: dirty, with additional uncommitted Celery/KWIC topology changes

## Important Commits Already Created

- `8409e1c` `fix: harden staging celery deployment`
- `69d56db` `fix: connect staging celery to redis over quadlet network`
- `dbfd9e9` `fix: sync celery ticket state in api process`

## GitHub Issue Already Created

- `#308` Handle Celery dispatch failures without leaking pending tickets

That issue is still open and was not fixed in this session.

## What Was Diagnosed Earlier

### 1. Worker was not actually running Celery

Originally `celery-worker.service` started Uvicorn because the image entrypoint always launched the API server. That was fixed earlier by making `docker/entrypoint.sh` honor explicit container commands.

### 2. Redis/Celery networking was wrong in staging

The staging deployment originally tried to use `redis://localhost:6379/0` inside containers. That was corrected to use the Redis container hostname on the Podman network:

- `redis://redis:6379/0`

### 3. API-side ticket state drift caused false `429`

The API process kept local in-memory tickets in `pending` even after Celery workers completed successfully. That exhausted `cache.max_pending_jobs` and caused both word-trend speeches and KWIC to return `429`. This was fixed and committed in `dbfd9e9`.

### 4. Missing tickets incorrectly looked "pending"

In Celery mode, nonexistent ticket IDs such as `status/null` could return a synthetic pending status instead of `404`. That was also fixed in the same backend ticket-state work.

## Latest Problem Investigated

### KWIC failure under Celery

Observed worker traceback:

- Celery worker process was `prefork`
- KWIC execution tried to create its own `multiprocessing.Pool`
- Python raised:
  - `AssertionError: daemonic processes are not allowed to have children`

Root cause:

- Celery prefork workers are daemonic processes
- daemon workers cannot spawn child worker processes
- KWIC multiprocessing therefore crashes inside the current Celery worker topology

## Latest Uncommitted Fixes In Working Tree

### A. Safe fallback inside daemon workers

`api_swedeb/api/services/kwic_service.py`

- If KWIC multiprocessing is enabled but the current process is daemonic, the service now disables inner multiprocessing for that execution.
- This prevents the hard crash.

### B. Celery task wrappers now fail correctly

`api_swedeb/api/services/kwic_ticket_service.py`
`api_swedeb/api/services/word_trend_speeches_ticket_service.py`

- Task wrappers now inspect the worker `ResultStore` ticket after execution.
- If the ticket ended in `error`, they raise instead of returning success.
- This prevents Celery from reporting `SUCCESS` when the service actually stored an error result.

### C. Split queue / split worker topology

The main performance-preserving change is now also patched locally but not committed yet.

#### Celery app changes

`api_swedeb/celery_app.py`

- Added explicit queue config:
  - default queue: `celery`
  - KWIC queue: `kwic`
- Added routing:
  - `api_swedeb.execute_kwic_ticket` -> `kwic`
  - `api_swedeb.execute_word_trend_speeches_ticket` -> `celery`

#### Router changes

`api_swedeb/api/v1/endpoints/tool_router.py`

- `submit_kwic_query()` now sends to `queue=get_kwic_queue_name()`
- `submit_word_trend_speeches_query()` now sends to `queue=get_default_queue_name()`

#### New staging Quadlet

`docker/quadlets/kwic-worker.container`

- Added dedicated KWIC worker:
  - `celery -A api_swedeb.celery_tasks worker --loglevel=info --pool=solo --concurrency=1 --queues=kwic`

#### Existing worker repurposed

`docker/quadlets/celery-worker.container`

- Now handles only the default queue:
  - `--queues=celery`

This is the intended final topology:

- API process enqueues KWIC tickets to queue `kwic`
- dedicated KWIC worker runs `--pool=solo`
- KWIC task itself may safely use `multiprocessing.Pool`
- word-trend speeches remain on the normal prefork/default worker

## Config Changes In Working Tree

Added queue settings to:

- `config/config.yml`
- `config/debug.config.yml`
- `tests/config.yml`

New keys:

```yaml
celery:
  default_queue: celery
  kwic_queue: kwic
```

## Docs Updated In Working Tree

- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/OPERATIONS.md`

These docs were updated to describe:

- queue splitting
- dedicated KWIC worker
- expected deployment/restart steps

## Current Uncommitted Files

At the time of writing:

- `api_swedeb/api/services/kwic_service.py`
- `api_swedeb/api/services/kwic_ticket_service.py`
- `api_swedeb/api/services/word_trend_speeches_ticket_service.py`
- `api_swedeb/api/v1/endpoints/tool_router.py`
- `api_swedeb/celery_app.py`
- `config/config.yml`
- `config/debug.config.yml`
- `docker/quadlets/celery-worker.container`
- `docker/quadlets/kwic-worker.container`
- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/OPERATIONS.md`
- `tests/api_swedeb/api/endpoints/test_tool_router.py`
- `tests/api_swedeb/api/services/test_kwic_service.py`
- `tests/api_swedeb/api/services/test_kwic_ticket_service.py`
- `tests/api_swedeb/api/services/test_word_trend_speeches_ticket_service.py`
- `tests/api_swedeb/test_celery_app.py`
- `tests/config.yml`

## Tests Run For The Latest Worktree

Executed:

```bash
uv run pytest tests/api_swedeb/test_celery_app.py \
  tests/api_swedeb/api/endpoints/test_tool_router.py \
  tests/api_swedeb/api/services/test_kwic_service.py \
  tests/api_swedeb/api/services/test_kwic_ticket_service.py \
  tests/api_swedeb/api/services/test_word_trend_speeches_ticket_service.py \
  tests/api_swedeb/test_celery_integration.py
```

Result:

- `88 passed in 0.33s`

## Likely Next Steps

### If resuming code work

1. Review the uncommitted Celery queue split and decide whether to keep it as the final approach.
2. If yes, commit the current worktree in one or two commits:
   - one for daemon-safe task/result handling
   - one for split queue / dedicated KWIC worker topology
3. Deploy the new Quadlet:
   - `docker/quadlets/kwic-worker.container`
4. Reload and restart user units on staging.

### If resuming staging deployment

Copy updated Quadlets and config, then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now kwic-worker.service
systemctl --user restart redis.service celery-worker.service kwic-worker.service swedeb-staging-app.service
```

Verify:

```bash
journalctl --user -u kwic-worker.service -n 100
journalctl --user -u celery-worker.service -n 100
journalctl --user -u swedeb-staging-app.service -n 100
```

Expected:

- `kwic-worker.service` ready on queue `kwic`
- `celery-worker.service` ready on queue `celery`
- API can submit KWIC tickets without the daemon multiprocessing crash

## Known Follow-Ups Still Open

### 1. Issue `#308`

If `send_task()` fails after ticket creation, there is still a separate dispatch-failure cleanup problem tracked in GitHub issue `#308`.

### 2. Frontend empty-search behavior

Earlier logs showed frontend requests like:

- `/v1/tools/word_trends/?...`

That is an empty-search frontend bug and is separate from the backend Celery/KWIC work.

### 3. Possible staging app port mismatch

Earlier analysis noted this staging Quadlet line:

- `PublishPort=127.0.0.1:8098:8092`

while the app logs showed Uvicorn listening on port `8098` inside the container. If that mismatch is still present on the deployed host, it remains a separate operational issue to verify.

## Files To Open First When Resuming

- `api_swedeb/celery_app.py`
- `api_swedeb/api/v1/endpoints/tool_router.py`
- `api_swedeb/api/services/kwic_service.py`
- `api_swedeb/api/services/kwic_ticket_service.py`
- `docker/quadlets/celery-worker.container`
- `docker/quadlets/kwic-worker.container`
- `docs/OPERATIONS.md`
