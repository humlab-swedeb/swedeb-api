# Local Docker Testing Guide

**Purpose:** Test the Docker build and container startup workflow locally before pushing to CI/CD. This validates that:
- The Docker image builds successfully with bundled frontend
- The container starts and serves both API and frontend
- The image matches what GitHub Actions will produce

**Not covered here:** Local development with `uvicorn` (see main README) or CI/CD configuration (see docs/OPERATIONS.md).

---

## Quick Start

```bash
cd docker

# Build image and run container (most common)
make test-local

# Test with Podman (production-like)
make test-local-podman

# Mount local frontend for rapid iteration
make test-local-repl
```

**Access the running application:**
- Frontend: http://localhost:8092/public/index.html#/
- API Docs: http://localhost:8092/docs
- API: http://localhost:8092/v1/

## Test Commands

| Command | Purpose |
|---------|---------|
| `make test-local` | Build image with bundled frontend and run |
| `make test-local-podman` | Same as above, using Podman |
| `make test-local-skip-build` | Run existing image without rebuilding |
| `make test-local-repl` | Mount local frontend for rapid iteration |
| `make test-help` | Show all script options |
| `make test-clean` | Remove test artifacts and images |

## What Gets Built

The Docker build process:
1. Builds Python wheel from current code
2. Downloads frontend from GitHub (`FRONTEND_VERSION=staging` by default)
3. Bundles frontend into `/app/public` in the image
4. Creates self-contained image with API + frontend

**Build output to look for:**
```
Downloading frontend version: staging
Frontend assets installed: 49 files
```

**Runtime output to look for:**
```
[2026-04-17 10:15:35] Frontend version: staging
[2026-04-17 10:15:35] Frontend assets present: 49 files
INFO: Uvicorn running on http://0.0.0.0:8092
```

## Common Issues

### Frontend assets not found at runtime
```bash
# Rebuild with explicit version
make test-local
```

### Frontend download fails during build
```bash
# Check tarball exists
curl -I https://github.com/humlab-swedeb/swedeb_frontend/releases/download/staging/frontend-staging.tar.gz

# Try different version
docker build -t swedeb-api:local-test --build-arg FRONTEND_VERSION=test -f Dockerfile ..
```

### REPL test can't find frontend
```bash
# Build frontend first
cd ../../swedeb_frontend && pnpm build
cd ../swedeb-api/docker && make test-local-repl
```

### Container exits immediately
Check logs for ERROR markers. Common causes:
- Config file missing/invalid
- Data directory not mounted
- Port 8092 already in use

## Debugging Commands

```bash
# Watch logs
docker logs -f swedeb-api-local-test

# Inspect running container
docker exec -it swedeb-api-local-test /bin/bash
ls -la /app/public/
cat /app/public/.frontend_version

# Verify frontend in built image
docker run --rm swedeb-api:local-test ls -la /app/public/

# Rebuild without cache
make test-clean
docker build --no-cache -t swedeb-api:local-test -f Dockerfile ..
```

## REPL Development Workflow

Fast iteration when changing frontend code:

```bash
# Build API image once
make test-local
# Press Ctrl+C after verifying

# Development loop
cd ../../swedeb_frontend
# Make changes...
pnpm build
cd ../swedeb-api/docker
make test-local-repl
# Press Ctrl+C, repeat...
```

This mounts local frontend over `/app/public` without rebuilding the API image.

## Before Pushing to CI/CD

```bash
# Test locally
cd docker && make test-local

# Verify works
curl http://localhost:8092/docs
open http://localhost:8092/public/index.html#/

# Then commit
git add . && git commit -m "feat: your changes" && git push
```

## Notes

- **Frontend versions:** `staging`, `test`, or `vX.Y.Z`
- **Local build mirrors CI:** Same Dockerfile, same frontend download
- **ReadOnly compatible:** Frontend baked in, no `/app/public` tmpfs needed
- **Cleanup:** `make test-clean` removes artifacts and images

## See Also

- [README.md](README.md) - Docker build overview
- [CI-CD.md](../CI-CD.md) - GitHub Actions workflows

## Questions?

See also:
- [../README.md](../README.md) - Main project documentation
