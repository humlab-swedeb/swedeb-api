# Local Testing Guide

This directory contains tools for building and testing the Swedeb API container **locally** before deploying to production. This is essential for debugging container startup issues, testing network isolation scenarios, and verifying fixes.

## Quick Start

```bash
cd docker

# Full build and test
make test-local

# Test with Podman (mimics production environment)
make test-local-podman

# Test offline fallback mechanism
make test-local-fallback

# Test with writable /app/public mount
make test-local-mount-public
```

## Available Test Commands

### Makefile Targets

| Command | Description |
|---------|-------------|
| `make test-local` | Build and run container locally with full output |
| `make test-local-podman` | Test using Podman (mimics production) |
| `make test-local-skip-build` | Test existing image without rebuilding |
| `make test-local-fallback` | Test with local fallback tarball |
| `make test-local-mount-public` | Test with writable `/app/public` mount |
| `make test-local-podman-fallback` | Podman + fallback testing |
| `make test-help` | Show all test script options |
| `make test-clean` | Clean up test artifacts |

### Direct Script Usage

```bash
# Show all options
./test-local.sh --help

# Custom testing scenarios
./test-local.sh --use-fallback --podman
./test-local.sh --mount-public --skip-build
```

## Testing Scenarios

### 1. Test Full Startup with GitHub Download

```bash
make test-local
```

What this tests:
- Image builds successfully
- Frontend assets download from GitHub
- Container starts and serves API
- All initialization scripts run correctly

### 2. Test Offline/Network-Isolated Deployment

```bash
make test-local-fallback
```

What this tests:
- Downloads `frontend-staging.tar.gz` to `test-data/dist/`
- Container falls back to local tarball when GitHub is unreachable
- Verifies fallback mechanism works

### 3. Test Read-Only Filesystem Workaround

```bash
# Don't mount /app/public - test the /tmp extraction workaround
make test-local-podman-fallback
```

What this tests:
- Simulates read-only `/app/public`
- Verifies automatic `/tmp` extraction
- Tests copy from `/tmp` to `/app/public`

### 4. Test with Writable /app/public

```bash
make test-local-mount-public
```

What this tests:
- Mounts `test-data/public` as `/app/public`
- Verifies direct extraction works when directory is writable
- Good for comparing against read-only behavior

## Understanding Test Output

### Success Indicators

Look for these in the output:

```
✓ Wheel built successfully
✓ Image built successfully
[2026-04-17 10:15:30] Checking frontend assets...
[2026-04-17 10:15:30] Auto-detected frontend version from branch 'dev': staging
[2026-04-17 10:15:30] Downloading frontend assets...
[2026-04-17 10:15:35] Frontend assets successfully downloaded and extracted
[2026-04-17 10:15:35] Starting application server on port 8092
```

### Fallback Mechanism

```
[2026-04-17 10:15:30] GitHub download failed after 3 attempts
[2026-04-17 10:15:30] Falling back to local tarball: /data/dist/frontend-staging.tar.gz
[2026-04-17 10:15:30] Successfully copied from local fallback
```

### Read-Only Workaround

```
WARNING: Assets directory may not be writable (will use /tmp extraction workaround if needed)
Attempting workaround: extract to /tmp and copy...
Successfully extracted to temporary directory
Successfully copied files to /app/public
```

### Failure Indicators

```
✗ Wheel build failed
✗ Image build failed
ERROR: Assets directory is not writable
ERROR: GitHub download failed and no local fallback found
```

## Directory Structure

```
docker/
├── test-local.sh           # Main test script
├── compose.local.yml       # Local testing docker-compose
├── Makefile                # Test targets
├── test-data/              # Created during tests
│   ├── dist/               # Local fallback tarballs
│   └── public/             # Optional writable mount
├── Dockerfile              # Container definition
├── download-frontend.sh    # Frontend asset downloader
└── entrypoint.sh           # Container startup script
```

## Debugging Tips

### 1. Watch Container Logs

```bash
# In another terminal while test runs
docker logs -f swedeb-api-local-test
```

### 2. Inspect Running Container

```bash
# After container starts (in another terminal)
docker exec -it swedeb-api-local-test /bin/bash

# Inside container, check:
ls -la /app/public/
cat /app/public/.frontend_version
stat /app/public
mount | grep overlay
```

### 3. Test Network Isolation

```bash
# Inside running container
/app/docker/test-network.sh
```

### 4. Check Build Logs

```bash
# Build logs saved to:
cat /tmp/docker-build.log
```

### 5. Rebuild Without Cache

```bash
# Clean slate rebuild
make test-clean
docker build --no-cache -t swedeb-api:local-test -f Dockerfile ..
make test-local-skip-build
```

## Common Issues & Solutions

### Issue: "Cannot write to assets directory"

**Solution**: Use the `--mount-public` option or test the workaround:

```bash
# Test workaround (should work)
make test-local-podman-fallback

# Test with writable mount (should also work)
make test-local-mount-public
```

### Issue: "GitHub download failed"

**Solution**: Test fallback mechanism:

```bash
# This downloads tarball and tests fallback
make test-local-fallback
```

### Issue: "Wheel build failed"

**Solution**: Build wheel manually first:

```bash
cd ..
uv build --wheel --out-dir docker/wheels
cd docker
make test-local-skip-build
```

### Issue: Container exits immediately

**Diagnosis**: Check exit code and logs:

```bash
# Run test - note the exit code
make test-local

# Check what went wrong in logs above
# Look for ERROR or ✗ markers
```

## Integration with CI/CD

Before creating a PR or merging to staging:

1. **Test locally first**:
   ```bash
   make test-local-podman-fallback
   ```

2. **Verify it works** (container starts and serves on port 8092)

3. **Then commit and push** to trigger GitHub Actions

4. **CI/CD builds** will use the same Dockerfile and scripts

## Advanced: Manual Build and Run

```bash
# Build manually
cd ..
uv build --wheel --out-dir docker/wheels
docker build -t swedeb-api:manual-test \
  --build-arg GIT_BRANCH=dev \
  --build-arg FRONTEND_VERSION=staging \
  -f docker/Dockerfile .

# Run manually with custom options
docker run --rm -it \
  --name swedeb-manual-test \
  -p 8092:8092 \
  -v $(pwd)/docker/test-data/dist:/data/dist:ro \
  -e FRONTEND_VERSION=staging \
  swedeb-api:manual-test
```

## Next Steps

After successful local testing:

1. Commit changes to `dev` branch
2. Create PR to `staging`
3. Wait for CI/CD to build staging image
4. Deploy to staging environment
5. Verify in staging before promoting to `main`

## Questions?

See also:
- [../README.md](../README.md) - Main project documentation
- [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) - Deployment troubleshooting
- [../docs/DEPLOY_PODMAN.md](../docs/DEPLOY_PODMAN.md) - Podman deployment guide
