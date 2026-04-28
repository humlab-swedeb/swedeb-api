# Docker Image Build

This directory contains the runtime files that are copied into the API image.

The image build is driven by:

- [Dockerfile](Dockerfile) - Multi-stage container build definition
- [.github/scripts/build-and-push-image.sh](../.github/scripts/build-and-push-image.sh) - Shared build script used by CI/CD

## Directory Structure

```
docker/
├── Dockerfile              # Container build definition
├── README.md               # This file
├── .dockerignore           # Files excluded from build context
├── compose.yml             # Production Docker Compose configuration
├── main.py                 # FastAPI app entry point (copied into image)
├── entrypoint.sh           # Container startup script (copied into image)
├── test-network.sh         # Network diagnostics script (copied into image)
├── .env                    # Environment variables for compose.yml
├── wheels/                 # Temporary directory for Python wheels (build artifact)
└── quadlets/               # Podman quadlet definitions for production deployment
```

**Build Context:** All Docker builds use this `docker/` directory as the build context, not the repository root. This means `COPY` commands in the Dockerfile reference paths relative to this directory.

## What The Image Contains

The build process does this:

1. Builds a wheel from the `swedeb-api` repository root with `uv build`.
2. Writes that wheel to the temporary `docker/wheels/` directory.
3. Builds the image from [Dockerfile](Dockerfile).
4. Copies the built wheel plus the runtime files in this directory into the image.
5. **Downloads and bakes frontend assets into the image** at `/app/public` during build.

At runtime:

- [entrypoint.sh](entrypoint.sh) starts the container
- [main.py](main.py) exposes the FastAPI app for `uvicorn`.


**Note:** Frontend is bundled into the image during build. This eliminates runtime download complexity, works with ReadOnly containers, and ensures consistent deployments. Frontend version is controlled via the `FRONTEND_VERSION` build argument (defaults to `staging`). For compatibility, `FRONTEND_VERSION=staging|test` now resolves to the frontend release tags `frontend-staging|frontend-test` while keeping the asset names `frontend-staging.tar.gz|frontend-test.tar.gz`.

## GitHub Actions Workflow

The repository has three build-related workflows:

- [test.yml](../.github/workflows/test.yml): on pushes to `test`, builds and pushes test tags.
- [staging.yml](../.github/workflows/staging.yml): on pushes to `staging`, builds and pushes staging tags.
- [release.yml](../.github/workflows/release.yml): on pushes to `main`, runs `semantic-release` first and only builds the production image when a new release is published.

All three workflows call the same shared script:

- [.github/scripts/build-and-push-image.sh](../.github/scripts/build-and-push-image.sh)

That script:

- derives tags from the requested environment and version
- builds the wheel into `docker/wheels/`
- runs `docker build` from the `docker/` directory
- pushes tags to `ghcr.io` unless `SKIP_PUSH=1`

## Local Testing

### Prerequisites

- Docker or Podman
- `uv` for Python package management
- `act` if you want to run GitHub Actions workflows locally
- A GitHub token for `act` to fetch actions or log in to GHCR

### CI/CD Build Script (Recommended)

The most reliable way to test the build locally is to run the same script that GitHub Actions uses:

```bash
# Build without pushing to registry
SKIP_PUSH=1 \
GITHUB_REPOSITORY=humlab-swedeb/swedeb-api \
./.github/scripts/build-and-push-image.sh "$(uv version | awk '{print $NF}')" staging
```

This script:
- Builds the Python wheel from the repo root
- Downloads frontend assets for the specified environment
- Builds the Docker image from the `docker/` directory
- Tags the image locally (does not push when `SKIP_PUSH=1`)

You can replace `staging` with `test` or `production` to test different frontend versions.

### Manual Build

If you prefer to build manually:

```bash
cd docker

# Build the wheel
(cd .. && uv build --wheel --out-dir docker/wheels)

# Build the image
docker build \
  --build-arg FRONTEND_VERSION=staging \
  -t swedeb-api:local \
  .
```

**Note:** This requires manually managing frontend download and wheel building.

### Running the Image Locally

After building, you can run the container locally:

```bash
docker run --rm -p 8092:8000 \
  -v /path/to/data:/data:ro \
  -v /path/to/config.yml:/config/config.yml:ro \
  swedeb-api:local
```

Then access:
- **Frontend UI**: http://localhost:8092/public/index.html#/
- **API Docs**: http://localhost:8092/docs
- **API Endpoints**: http://localhost:8092/v1/

### Deprecated Local Testing Workflow

Previous comprehensive local testing scripts (`test-local.sh`, `build-local-image.sh`, etc.) have been removed pending redesign. See [../docs/change_requests/LOCAL-CONTAINER-TESTING-WORKFLOW.md](../docs/change_requests/LOCAL-CONTAINER-TESTING-WORKFLOW.md) for the intent and future considerations.

## Testing With `act`

`act` is useful for validating workflow wiring locally. For this repository, `test.yml` and `staging.yml` are the practical workflows to run with `act`.

### Dry-Run A Workflow

This checks the workflow structure without executing containers:

```bash
act -n workflow_dispatch \
  -W .github/workflows/staging.yml \
  -s GITHUB_TOKEN="$(gh auth token)"
```

### Run A Workflow Locally Without Pushing

To execute the staging workflow locally while still preventing image push:

```bash
act workflow_dispatch \
  -W .github/workflows/staging.yml \
  -a <your-github-username> \
  --env SKIP_PUSH=1 \
  -s GITHUB_TOKEN="$(gh auth token)" \
  -s CWB_REGISTRY_TOKEN=<github-pat-with-read-packages>
```

Notes:

- `SKIP_PUSH=1` is consumed by [.github/scripts/build-and-push-image.sh](../.github/scripts/build-and-push-image.sh), so the workflow can build locally without publishing tags.
- `-a <your-github-username>` matters because the workflow uses `github.actor` during `docker login`.
- `CWB_REGISTRY_TOKEN` is the safer option when the build needs authenticated access to `ghcr.io/humlab/cwb-container`.
- If you only want to validate the workflow definition, prefer `act -n`.

### About `release.yml`

You can inspect [release.yml](../.github/workflows/release.yml) with `act -n`, but a full local run is usually not worth it because it also expects `semantic-release`, repository history, and release credentials to behave like GitHub.
