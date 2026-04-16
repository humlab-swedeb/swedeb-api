# Frontend/Backend Workflow Improvements

## Current Issues

1. **No automatic branch alignment**: Backend defaults to `FRONTEND_VERSION=latest` regardless of which branch it's deployed from
2. **Manual configuration required**: Deployments must explicitly set `FRONTEND_VERSION` to match the environment
3. **Build script is simple but could be clearer**: Frontend `build-assets.sh` just takes a version string without understanding branch context
4. **Potential version mismatches**: Easy to deploy staging backend with production frontend or vice versa

## Recommended Improvements

### 1. **Auto-detect Branch for Frontend Version** (Backend)

**Problem**: Backend always defaults to `latest`, requiring manual override.

**Solution**: Detect the current git branch and use matching frontend release.

**Implementation** in `docker/download-frontend.sh`:

```bash
# Auto-detect branch if FRONTEND_VERSION not explicitly set
if [ -z "${FRONTEND_VERSION:-}" ]; then
    # Try to detect git branch
    if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
        DETECTED_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        case "$DETECTED_BRANCH" in
            main|master)
                FRONTEND_VERSION="latest"
                ;;
            staging|test)
                FRONTEND_VERSION="$DETECTED_BRANCH"
                ;;
            *)
                FRONTEND_VERSION="latest"
                ;;
        esac
        log "Auto-detected branch: $DETECTED_BRANCH → using frontend: $FRONTEND_VERSION"
    else
        FRONTEND_VERSION="latest"
    fi
else
    log "Using explicit FRONTEND_VERSION: $FRONTEND_VERSION"
fi
```

**Benefits**:
- Staging backend automatically uses staging frontend
- Test backend automatically uses test frontend
- Production (main) uses latest release
- Can still override with explicit `FRONTEND_VERSION` env var

### 2. **Add Branch Detection via Environment Variable**

For containerized deployments where `.git` isn't available, pass branch info as build arg:

**In `docker/Dockerfile`**:
```dockerfile
ARG GIT_BRANCH=main
ARG FRONTEND_VERSION
ENV GIT_BRANCH=${GIT_BRANCH}
# Only set FRONTEND_VERSION if explicitly provided
ENV FRONTEND_VERSION=${FRONTEND_VERSION:-}
```

**In `docker/entrypoint.sh`**:
```bash
# Auto-detect frontend version based on backend branch
if [ -z "${FRONTEND_VERSION:-}" ]; then
    case "${GIT_BRANCH:-main}" in
        main|master)
            FRONTEND_VERSION="latest"
            ;;
        staging|test)
            FRONTEND_VERSION="${GIT_BRANCH}"
            ;;
        *)
            FRONTEND_VERSION="latest"
            ;;
    esac
    log "Auto-detected frontend version from branch ${GIT_BRANCH}: ${FRONTEND_VERSION}"
fi
export FRONTEND_VERSION
```

**In CI/CD** (`.github/workflows/`):
```yaml
- name: Build Docker image
  run: |
    docker build \
      --build-arg GIT_BRANCH=${{ github.ref_name }} \
      -t myimage:tag \
      .
```

**Benefits**:
- Works in containers without git repo
- Explicit branch tracking
- Still allows manual override

### 3. **Simplify Deployment Configuration**

**Current**: Must remember to set `FRONTEND_VERSION` in every deployment

**Improved**: Set once in Docker build, with sensible defaults

**In `docker/compose.yml`**:
```yaml
services:
  swedeb_api:
    image: "${SWEDEB_IMAGE_NAME}:${SWEDEB_IMAGE_TAG}"
    environment:
      # Optional: only set to override auto-detection
      - FRONTEND_VERSION=${FRONTEND_VERSION:-}
    # ...
```

**In `.env` (optional override)**:
```bash
# Uncomment to override auto-detected frontend version
# FRONTEND_VERSION=staging
# FRONTEND_VERSION=1.2.3
# FRONTEND_VERSION=latest
```

### 4. **Enhanced Build Script** (Frontend - Optional)

**Current**: `build-assets.sh` receives full version string including branch

**Improved**: Could be more explicit about what it's doing

**In `.github/scripts/build-assets.sh`**:
```bash
#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

VERSION=$1
BRANCH=${2:-main}  # Optional branch parameter

if [ -z "$VERSION" ]; then
    log "ERROR: Version argument is missing!"
    log "Usage: build-assets.sh <version> [branch]"
    exit 1
fi

# Construct tarball name based on branch
if [ "$BRANCH" = "main" ]; then
    TARBALL_NAME="frontend-${VERSION}.tar.gz"
else
    TARBALL_NAME="frontend-${VERSION}-${BRANCH}.tar.gz"
fi

log "Building frontend assets for ${BRANCH} branch, version ${VERSION}"
log "Output: ${TARBALL_NAME}"

pnpm build

# Validate build output
if [ ! -d "dist/spa" ] || [ -z "$(ls -A dist/spa)" ]; then
    log "ERROR: Build output is empty or missing!"
    exit 1
fi

# Create tarball
tar -czvf "dist/${TARBALL_NAME}" -C dist/spa .

# Verify tarball was created
if [ ! -f "dist/${TARBALL_NAME}" ]; then
    log "ERROR: Failed to create tarball!"
    exit 1
fi

TARBALL_SIZE=$(du -h "dist/${TARBALL_NAME}" | cut -f1)
log "Assets prepared: dist/${TARBALL_NAME} (${TARBALL_SIZE})"
```

**In `.github/workflows/ci-ghcr.yml`**:
```yaml
# For main branch
./.github/scripts/build-assets.sh "${VERSION}" "main"

# For staging/test
./.github/scripts/build-assets.sh "${VERSION}" "${BRANCH}"
```

**Note**: This is optional since current approach works fine.

## Recommended Implementation Order

### Phase 1: Backend Auto-detection (High Value, Low Risk)
1. Add `GIT_BRANCH` build arg to Dockerfile
2. Update `entrypoint.sh` to auto-detect frontend version from branch
3. Update CI/CD workflows to pass branch name
4. Test with staging deployment

**Impact**: Eliminates need for manual `FRONTEND_VERSION` configuration in 90% of cases

### Phase 2: Documentation and Defaults (Quick Win)
1. Update deployment docs with new auto-detection behavior
2. Add example `.env` showing override options
3. Update `compose.yml` with clearer comments

**Impact**: Reduces deployment errors and confusion

### Phase 3: Frontend Build Script (Optional Enhancement)
1. Only if team prefers more explicit branch handling
2. Currently works fine as-is

**Impact**: Marginal improvement in clarity

## Example Usage After Implementation

### Deployment - No Configuration Needed
```bash
# Staging deployment - automatically uses staging frontend
git checkout staging
docker build -t api:staging .
docker run api:staging
# → Automatically downloads staging frontend

# Production deployment - automatically uses latest
git checkout main
docker build -t api:prod .
docker run api:prod
# → Automatically downloads latest frontend
```

### Deployment - With Override
```bash
# Staging backend but test a specific frontend version
docker build --build-arg GIT_BRANCH=staging -t api:staging .
docker run -e FRONTEND_VERSION=1.2.3 api:staging
# → Downloads frontend version 1.2.3
```

### CI/CD - Automatic Branch Alignment
```yaml
# In .github/workflows/staging.yml
- name: Build image
  run: |
    docker build \
      --build-arg GIT_BRANCH=${{ github.ref_name }} \
      -t ghcr.io/org/api:staging \
      .
# → Staging builds automatically configure for staging frontend
```

## Migration Path

1. **Add auto-detection** (non-breaking): Defaults still work, adds convenience
2. **Update deployments gradually**: Each environment can migrate when convenient
3. **Remove manual configs**: Once proven, remove explicit `FRONTEND_VERSION` from configs
4. **Document**: Update all deployment guides

## Testing Strategy

1. **Unit test** branch detection logic in isolation
2. **Integration test** each combination:
   - Main branch → latest frontend
   - Staging branch → staging frontend
   - Test branch → test frontend
   - Manual override → specified version
3. **Deployment test** in staging environment first
4. **Rollback plan**: Keep explicit `FRONTEND_VERSION` option for safety

## Alternatives Considered

### Alternative 1: Single Environment Variable
Set `ENVIRONMENT=staging` and derive everything from that.

**Pros**: Single source of truth
**Cons**: Less flexible, couples unrelated concerns

### Alternative 2: Git Tags Only
Use git tags to determine version/branch.

**Pros**: Canonical source
**Cons**: Doesn't work in containers, requires git repo

### Alternative 3: Config File
Put branch mapping in a config file.

**Pros**: Very explicit
**Cons**: Extra file to maintain, more complex

**Recommendation**: Go with git branch detection + build arg as described above for best balance of simplicity and flexibility.

## Summary

**Most Important Change**: Add automatic branch-to-frontend-version mapping in `entrypoint.sh` using `GIT_BRANCH` build arg.

**Expected Result**: 
- Zero configuration needed for standard deployments
- Staging always uses staging frontend
- Production always uses latest frontend
- Manual override still available when needed
- Reduced deployment errors

**Effort**: ~2 hours implementation + testing
**Risk**: Low (adds defaults, doesn't break existing configs)
**Value**: High (eliminates entire class of deployment mistakes)
