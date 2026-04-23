# Comprehensive Operations Guide

## Purpose

This guide documents how the Swedeb API is operated across deployed environments. It focuses on runtime configuration, versioned data dependencies, build artifacts, CI/CD behavior, deployment flow, verification, and operational maintenance.

It is not the primary guide for local development, contributor workflow, or unit-test practice. Those topics belong in [DEVELOPMENT.md](./DEVELOPMENT.md).

## Table of Contents

- [Comprehensive Operations Guide](#comprehensive-operations-guide)
  - [Purpose](#purpose)
  - [Table of Contents](#table-of-contents)
  - [Environments](#environments)
  - [Branch Strategy](#branch-strategy)
  - [Operational Assumptions and Invariants](#operational-assumptions-and-invariants)
  - [Configuration and Secrets Model](#configuration-and-secrets-model)
    - [Runtime configuration](#runtime-configuration)
      - [Key configuration sections](#key-configuration-sections)
    - [Runtime environment variables](#runtime-environment-variables)
    - [Secrets and credentials](#secrets-and-credentials)
    - [Build-time versus runtime configuration](#build-time-versus-runtime-configuration)
  - [Data Layout](#data-layout)
  - [Build Artifacts](#build-artifacts)
  - [Deployment Flow](#deployment-flow)
  - [CI Pipeline Stages](#ci-pipeline-stages)
    - [Test and staging workflows](#test-and-staging-workflows)
    - [Production workflow](#production-workflow)
  - [CD Trigger and Release Process](#cd-trigger-and-release-process)
    - [Hotfix and emergency release notes](#hotfix-and-emergency-release-notes)
  - [Celery Worker Deployment](#celery-worker-deployment)
  - [Post-Deployment Verification](#post-deployment-verification)
  - [Rollback Procedure](#rollback-procedure)
  - [Health Checks, Observability, and Alerting](#health-checks-observability-and-alerting)
  - [Backup, Recovery, and Incident Basics](#backup-recovery-and-incident-basics)
  - [Related Resources](#related-resources)

## Environments

Swedeb API uses a four-branch promotion model, but only three branches correspond to deployed environments.

## Branch Strategy

This project uses a **four-branch workflow** for controlled progression through environments:

```
┌─────────────────────────────────────────────────────────────────┐
│                     BRANCH WORKFLOW STRATEGY                    │
└─────────────────────────────────────────────────────────────────┘

    Feature Branches
         │
         │ PR
         ▼
    ┌─────────┐
    │   dev   │ ← Integration branch (NO auto-builds)
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │  test   │ ← Test environment
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │ staging │ ← Staging/pre-production testing
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │  main   │ ← Production releases (semantic versioning)
    └─────────┘
```

| Scope       | Branch    | Build trigger                    | Primary image tags                                        | Operational role                                                   |
|-------------|-----------|----------------------------------|-----------------------------------------------------------|--------------------------------------------------------------------|
| Integration | `dev`     | None                             | N/A                                                       | Integration branch only; not an automatically deployed environment |
| Test        | `test`    | Push or manual workflow dispatch | `{version}-test`, `test`, `test-latest`                   | QA and integration validation                                      |
| Staging     | `staging` | Push or manual workflow dispatch | `{version}-staging`, `staging`                            | Pre-production validation                                          |
| Production  | `main`    | Push or manual workflow dispatch | `{version}`, `{major}`, `{minor}`, `latest`, `production` | Release and live service                                           |

Operationally, `test`, `staging`, and `production` are the environments that matter. `dev` remains part of the promotion path, but it is not a deployment target in the current workflow.

## Operational Assumptions and Invariants

- The current source of truth for release/build behavior is `.github/workflows/`, `.github/scripts/`, `docker/`, and mounted runtime configuration.
- The primary delivery artifact is a container image published to `ghcr.io/humlab-swedeb/swedeb-api`.
- The repository currently targets Podman/Quadlet-style runtime deployment, with Compose files and Docker utilities available as supporting material rather than the primary runbook.
- Only `test`, `staging`, and `main` trigger CI/CD builds in the current workflow.
- Production operations should pin a specific backend image tag. Floating production tags such as `latest` should not be treated as the default operational choice.
- Frontend assets are currently baked into the container image at build time through the Docker build argument `FRONTEND_VERSION`. The runtime image is expected to contain `/app/public/index.html` and `/app/public/.frontend_version`.
- The current shared build script does not pass `FRONTEND_VERSION` to `docker build`. Unless another build path overrides it, the Dockerfile default applies.
- Runtime paths inside the container must match the mounted configuration file. If host mounts or directory layouts change, the mounted `config.yml` must change with them.
- In production, Redis and the Celery worker container must share the same `cache.root_dir` volume as the API container so that ticket artifacts written by the worker are readable by the API.

## Configuration and Secrets Model

### Runtime configuration

At application startup, the API reads configuration from `SWEDEB_CONFIG_PATH`, defaulting to `config/config.yml` if the variable is not set.

The checked-in `config/config.yml` defines the main runtime settings, including:

- metadata version and metadata database path
- CWB registry directory and corpus name
- DTM and tagged-frame folders
- bootstrap speech corpus location
- cache settings
- FastAPI allowed origins

In deployed environments, the supported pattern is to mount a configuration file into the container and point `SWEDEB_CONFIG_PATH` at that file. The example Quadlet file under [docker/app.container](../docker/app.container) mounts a read-only `config.yml` into `/app/config/config.yml`.

#### Key configuration sections

The `config.yml` structure includes the following operational sections:

**`metadata`** - Corpus metadata configuration
- `version` - Metadata schema version (e.g., `v1.1.3`)
- `database.folder` - Path to metadata database directory
- `database.name` - SQLite database filename

**`cwb`** - IMS Open Corpus Workbench configuration
- `registry_dir` - CWB registry directory path
- `corpus_name` - Target corpus name for KWIC queries

**`corpus`** - Corpus data locations
- `version` - Corpus version tag (e.g., `v1.4.1`)
- `dtm.folder` - Document-term matrix data directory
- `tagged_frames.folder` - Tagged frame input data
- `bootstrap_corpus_folder` - Prebuilt speech corpus location

**`cache`** - Shared ticket-based paging configuration (used by both KWIC and word trends paging)
- `result_ttl_seconds` - Ticket lifetime before expiration (default: `600`)
- `cleanup_interval_seconds` - Frequency of automatic cleanup (default: `60`)
- `max_artifact_bytes` - Maximum total storage for all ticket artifacts in bytes (default: `2147483648` = 2GB)
- `max_pending_jobs` - Maximum concurrent pending tickets (default: `2`)
- `root_dir` - Filesystem path for ticket artifact storage (e.g., `/tmp/swedeb-kwic-cache`)
- `max_page_size` - Maximum page size for paginated results (default: `200`)

**`celery`** - Background task queue configuration (required for production ticket execution)
- `broker_url` - Redis connection URL for task queue
- `result_backend` - Redis connection URL for result storage
- `worker_concurrency` - Number of concurrent Celery worker processes
- `result_expires` - Task result expiration time in seconds
- `default_queue` - Queue name consumed by the general-purpose Celery worker (default: `celery`)
- `multiprocessing_queue` - Queue name consumed by the dedicated multiprocessing worker (default: `multiprocessing`)

**`fastapi`** - Web API configuration
- `origins` - CORS allowed origins list

**Operational notes:**
- The `cache.root_dir` volume must be shared between API and Celery worker containers so ticket artifacts are accessible across processes
- Cache settings apply globally to all ticket-based endpoints (KWIC and word trends speeches)
- Ticket artifacts are stored as feather files under `cache.root_dir`
- Cleanup runs automatically at `cleanup_interval_seconds` frequency to remove expired tickets

### Runtime environment variables

The runtime deployment layer is expected to provide environment variables such as:

- `SWEDEB_CONFIG_PATH`
- `SWEDEB_DATA_FOLDER`
- `SWEDEB_IMAGE_TAG`
- `SWEDEB_PORT`
- `SWEDEB_HOST_PORT`
- `SWEDEB_METADATA_FILENAME`

See the archived [ENVIRONMENT_VARIABLE.md](./archive/ENVIRONMENT_VARIABLE.md) for the older variable inventory reference.

### Secrets and credentials

Secrets are split by phase:

- CI credentials: GitHub Actions uses `GITHUB_TOKEN` for repository and package operations, and may use `CWB_REGISTRY_TOKEN` for cross-organization package access during image builds.
- Runtime secrets: host-specific `.env` files, environment files, and mounted config/secrets should be managed outside the repository.

Do not treat checked-in config files as the place for production secrets. Checked-in config should be treated as repository defaults or examples, not the authoritative production secret store.

### Build-time versus runtime configuration

Keep these concerns separate:

- Build-time: `FRONTEND_VERSION` is a Docker build argument that determines which frontend release is bundled into the image.
- Runtime: `SWEDEB_*` variables and the mounted `config.yml` determine how the application starts and where it finds its data.

At the time of writing, the checked-in GitHub build workflows use the shared build script, and that script does not explicitly pass `FRONTEND_VERSION` into `docker build`. Any assumed frontend-version policy should therefore be verified against the current Dockerfile and build scripts rather than inferred from branch names alone.

## Data Layout

Operationally, the application depends on mounted corpus assets, registry data, and metadata files that match the configured paths inside the container.

The current checked-in config expects a versioned data layout with these functional groups:

- CWB registry data
- metadata database
- DTM artifacts
- tagged-frame input data
- speech/bootstrap corpus data

A minimal conceptual layout looks like this:

```text
/data/
  registry/
  swedeb/
    metadata/
      riksprot_metadata.vX.Y.Z.db
    vX.Y.Z/
      dtm/
      tagged_frames/
      speeches/
        bootstrap_corpus/
```

The exact host layout is less important than the invariant that mounted paths and `config.yml` agree. If the host uses a different directory structure, update the mounted config rather than assuming the checked-in sample paths are valid everywhere.

Versioning matters operationally:

- metadata version is tracked under `metadata.version`
- corpus assets are stored under versioned directories
- deployment should not silently mix incompatible corpus and metadata versions

Redis is treated as ephemeral runtime state. Task queue entries and task execution state are stored in Redis by the Celery integration, but these are short-lived and do not require persistent backup. Redis persistence (`appendonly yes`) is enabled in `docker/redis.container` as a convenience for crash recovery of in-flight tasks, not as a primary data store.

## Build Artifacts

The current build/release process produces these operational artifacts:

| Artifact                | Produced by                                | Location                           | Operational use                    |
|-------------------------|--------------------------------------------|------------------------------------|------------------------------------|
| Backend container image | `.github/scripts/build-and-push-image.sh`  | `ghcr.io/humlab-swedeb/swedeb-api` | Deployed runtime artifact          |
| Python wheel            | `prepare-release-assets.sh` and `uv build` | `dist/` and GitHub release assets  | Release artifact, packaging output |
| GitHub release notes    | semantic-release                           | GitHub Releases                    | Production release record          |
| Git tags                | semantic-release                           | Git repository                     | Production version tracking        |
| Bundled frontend assets | `docker/Dockerfile` during image build     | `/app/public` inside the image     | Frontend served by the API image   |

Environment tag policy is:

- Test: `{version}-test`, `test`, `test-latest`
- Staging: `{version}-staging`, `staging`
- Production: `{version}`, `{major}`, `{minor}`, `latest`, `production`

The build script also builds a wheel into `docker/wheels/` as an intermediate step before the Docker build. That intermediate directory is part of the build process, not a runtime artifact to preserve.

## Deployment Flow

The operational deployment path is:

1. A workflow builds and publishes the target image tag to GHCR.
2. The operator selects the correct tag for the target environment.
3. The target host pulls the new image.
4. The runtime service is reinstalled or restarted with the intended config and image tag.
5. Post-deployment verification is performed before the rollout is considered complete.

Environment-specific expectations:

- Test and staging commonly use the floating environment tags (`test`, `staging`) or their versioned equivalents.
- Production should use a pinned version tag rather than `latest`.

The current FAQ shows the supported Quadlet-oriented update pattern:

```bash
podman image pull ghcr.io/humlab-swedeb/swedeb-api:<tag>
manage-quadlet remove
manage-quadlet install
```

Use the environment-appropriate `<tag>`:

- `staging` or `{version}-staging` for staging
- `test` or `{version}-test` for test
- a specific release version such as `0.7.0` for production

## CI Pipeline Stages

### Test and staging workflows

The workflows [test.yml](../.github/workflows/test.yml) and [staging.yml](../.github/workflows/staging.yml) follow the same high-level stages:

1. Check out the repository.
2. Set up Python 3.13.
3. Install `uv`.
4. Resolve the version from workflow input or `uv version`.
5. Authenticate to GHCR.
6. Run `.github/scripts/build-and-push-image.sh` for the target environment.

### Production workflow

The workflow [release.yml](../.github/workflows/release.yml) adds release-management stages before the image build:

1. Check out the full repository history.
2. Set up Node.js and Python 3.13.
3. Install `uv`.
4. Install `semantic-release` dependencies with `npm ci`.
5. Run `semantic-release`.
6. Build and push the production image only if a new release was actually published.

## CD Trigger and Release Process

Current triggers are:

- `test.yml`: push to `test`, or manual `workflow_dispatch` with an optional `version`
- `staging.yml`: push to `staging`, or manual `workflow_dispatch` with an optional `version`
- `release.yml`: push to `main`, or manual `workflow_dispatch`

The production release process is governed by `.releaserc.yml` and `prepare-release-assets.sh`:

- semantic-release analyzes Conventional Commits on `main`
- it determines the next release version
- it updates versioned release artifacts, including `pyproject.toml`
- `prepare-release-assets.sh` syncs `api_swedeb/__init__.py` and builds the wheel
- semantic-release publishes the GitHub release and changelog
- the workflow then builds and pushes the production image with production tags

Operationally, this means:

- test and staging build images directly from the branch state
- production first creates a formal release, then publishes the deployable image for that release

### Hotfix and emergency release notes

- Prefer the normal promotion path through `dev` → `test` → `staging` → `main` when time allows, so the fix is validated in each environment.
- If an operationally urgent production issue requires an emergency release, a direct release path to `main` may be used, but the fix should then be reconciled back into the active promotion branches.
- Use the same release mechanics as normal production releases: a valid Conventional Commit history, semantic-release on `main`, and a pinned production image tag for rollout.
- Manual `workflow_dispatch` remains available for `test`, `staging`, and `release.yml` when an operator needs to rebuild or publish from the workflow UI rather than waiting for the next branch push.

## Celery Worker Deployment

In production (`development.celery_enabled: true`), background tasks are split across two Celery workers deployed as sibling containers to the API.

Quadlet files:

- `docker/quadlets/redis.container`: Redis 7 service; uses `appendonly yes` for AOF persistence
- `docker/quadlets/celery-worker.container`: default-queue Celery worker for word-trend speeches and other lightweight jobs
- `docker/quadlets/multiprocessing-worker.container`: dedicated solo-pool Celery worker for the `multiprocessing` queue
- `docker/quadlets/swedeb-staging-app.container`: API container for the staging environment

The default worker starts with:

```
celery -A api_swedeb.celery_tasks worker --loglevel=info --concurrency=4 --queues=celery
```

The dedicated multiprocessing worker starts with:

```
celery -A api_swedeb.celery_tasks worker --loglevel=info --pool=solo --concurrency=1 --queues=multiprocessing
```

The worker reads its configuration from `SWEDEB_CONFIG_PATH` during the `worker_init` signal, then calls `configure_celery()` to apply broker and backend URLs. In the staging Quadlets, `SWEDEB_CONFIG_PATH` is set explicitly to `/app/config/config.yml`, which matches the mounted runtime config path.

The shared image entrypoint executes any explicit container command before falling back to the default Uvicorn startup. This allows the worker Quadlet to run `celery ... worker` while the API container continues to boot the web app by default.

The deployed Celery broker/backend URL must target the Redis container on the shared Podman network, not `localhost`. The checked-in production config uses `redis://redis:6379/0`, and the Redis Quadlet publishes a stable in-network alias `redis` for that purpose.

The API routes multiprocessing-capable tickets such as KWIC to `celery.multiprocessing_queue` and word-trend speeches tickets to `celery.default_queue`. The queue names in `config.yml` must stay aligned with the `--queues=` arguments in the worker Quadlets.

Service dependency order: `redis.service` must be running before `celery-worker.service`, `multiprocessing-worker.service`, and the API service. The API and worker units declare that relationship explicitly, and `BindsTo=` plus `PartOf=` ensure they are restarted when Redis is restarted so their Celery clients reconnect cleanly.

The `Network=swedeb-staging-app.network` setting already makes Quadlet generate the required network dependency. Do not add manual `Requires=` or `After=` lines that reference `swedeb-staging-app.network` directly; that is a Quadlet file name, not a valid systemd unit name.

The API container, both Celery worker containers, and the Redis container must all be on the same Podman network (`swedeb-*-app.network`). The API and workers must share a common writable volume mounted at `cache.root_dir` (default: `/tmp/swedeb-kwic-cache`) so that ticket artifacts written by workers are visible to the API when a client polls for results.

To restart the workers after a deployment:

```bash
systemctl --user restart multiprocessing-worker.service
systemctl --user restart celery-worker.service
systemctl --user status multiprocessing-worker.service
systemctl --user status celery-worker.service
journalctl --user -u multiprocessing-worker.service -n 100
journalctl --user -u celery-worker.service -n 100
```

## Post-Deployment Verification

Use verification steps that confirm the running container, the API surface, and the bundled frontend assets.

Recommended checks:

- confirm the service/container is running
- confirm the expected image tag was deployed
- check the API docs endpoint
- verify that the bundled frontend marker file exists and matches expectations
- review startup logs for configuration or asset errors

Short operator checklist:

- Confirm the expected image tag was pulled and the service restarted cleanly.
- Confirm `http://localhost:<port>/docs` responds from the target environment.
- Confirm `/app/public/.frontend_version` exists in the running container and matches expectations.
- Confirm `/app/public/index.html` exists in the running container.
- Confirm Redis is running and accepting connections.
- Confirm the default Celery worker started and shows as `READY` in its logs.
- Confirm the dedicated multiprocessing worker started and shows as `READY` in its logs.
- Review recent service logs for startup, configuration, or asset errors before declaring the rollout complete.

Useful commands in current operational material:

```bash
curl http://localhost:<port>/docs
journalctl --user -u <service-name> -n 200
journalctl --user -u redis.service -n 50
journalctl --user -u celery-worker.service -n 100
podman exec <container> cat /app/public/.frontend_version
podman exec <container> test -f /app/public/index.html && echo ok
# Confirm Redis accepts connections:
podman exec <redis-container> redis-cli ping
```

The current runtime image does not define a checked-in Docker `HEALTHCHECK`, and this repository does not document a supported `/health` or `/version` endpoint as an operational contract. Use `/docs` plus representative endpoint checks and service logs as the baseline smoke test unless a deployment-specific runbook defines more.

## Rollback Procedure

`TBD`

The repository does not currently contain a single authoritative rollback runbook for deployed environments.

## Health Checks, Observability, and Alerting

Current observability is basic and service-oriented:

- `docker/entrypoint.sh` logs startup progress and the bundled frontend version when the marker file is present
- the entrypoint exits with an error if `/app/public/index.html` is missing
- operators can use `journalctl` and `podman logs` as the primary first-line log sources

Current practical health signals are:

- the service starts successfully
- the frontend files exist in `/app/public`
- the API docs endpoint responds

Alerting is not defined in an authoritative repository runbook at this time.

`TBD`: alert routing, thresholds, ownership, and escalation procedures.

## Backup, Recovery, and Incident Basics

`TBD`

The repository does not currently define an authoritative backup/recovery procedure. No in-repo incident runbook currently specifies recovery ordering, restore sources, or data validation steps after restore.

## Related Resources

- [DEVELOPMENT.md](./DEVELOPMENT.md) for contributor workflow and local development guidance
- [archive/ENVIRONMENT_VARIABLE.md](./archive/ENVIRONMENT_VARIABLE.md) as historical variable inventory reference only
- [FAQ.md](./FAQ.md) for current operational command examples
- [docker/README.md](../docker/README.md) for image-build details
- [archive/DEPLOY_PODMAN.md](./archive/DEPLOY_PODMAN.md) and [archive/DEPLOY_DOCKER.md](./archive/DEPLOY_DOCKER.md) as historical references only
- [archive/TROUBLESHOOTING.md](./archive/TROUBLESHOOTING.md) as historical troubleshooting reference only
