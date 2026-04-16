# Docker Image Build

This directory contains the runtime files that are copied into the API image.

The image build is driven by:

- [Dockerfile](Dockerfile)
- [build-local-image.sh](build-local-image.sh)
- [.github/scripts/build-and-push-image.sh](../.github/scripts/build-and-push-image.sh)

## What The Image Contains

The build process does this:

1. Builds a wheel from the `swedeb-api` repository root with `uv build`.
2. Writes that wheel to the temporary `docker/wheels/` directory.
3. Builds the image from [Dockerfile](Dockerfile).
4. Copies the built wheel plus the runtime files in this directory into the image.

At runtime:

- [entrypoint.sh](entrypoint.sh) starts the container.
- [download-frontend.sh](download-frontend.sh) fetches frontend assets from GitHub releases when needed.
- [main.py](main.py) exposes the FastAPI app for `uvicorn`.

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

- Docker
- `uv`
- `act` if you want to run the workflows locally
- a GitHub token if you want `act` to fetch actions or log in to GHCR

### Fastest Local Build Test

This is the simplest local check and does not push anything:

```bash
bash docker/build-local-image.sh test
bash docker/build-local-image.sh staging
```

This uses the same Dockerfile and the same wheel-first build pattern as CI, but it tags the image locally as `swedeb-api`.

### Run The Shared CI Build Script Without Pushing

If you want to test the same script that GitHub Actions uses, run it with `SKIP_PUSH=1`:

```bash
SKIP_PUSH=1 \
GITHUB_REPOSITORY=humlab-swedeb/swedeb-api \
./.github/scripts/build-and-push-image.sh "$(uv version | awk '{print $NF}')" staging
```

Notes:

- `SKIP_PUSH=1` skips both registry push and registry login inside the shared script.
- `GITHUB_REPOSITORY` keeps the local tags aligned with CI tag names.
- You can replace `staging` with `test` or `production`.

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
