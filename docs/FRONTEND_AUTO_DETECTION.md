# Frontend Version Auto-Detection

## Overview

The backend now automatically detects which frontend version to download based on the git branch it's deployed from.

## Automatic Mapping

- **main/master branch** → Downloads `latest` frontend release
- **staging branch** → Downloads `staging` frontend pre-release  
- **test branch** → Downloads `test` frontend pre-release
- **Unknown branch** → Falls back to `latest`

## How It Works

### 1. During Docker Build

Pass the git branch as a build argument:

```bash
docker build --build-arg GIT_BRANCH=staging -t api:staging .
```

**In CI/CD** (automatic):
```yaml
- name: Build image
  run: |
    docker build \
      --build-arg GIT_BRANCH=${{ github.ref_name }} \
      -t ghcr.io/org/api:${{ github.ref_name }} \
      .
```

### 2. At Container Startup

The `entrypoint.sh` script:
1. Checks if `FRONTEND_VERSION` is explicitly set
2. If not, uses `GIT_BRANCH` to determine the frontend version
3. If `GIT_BRANCH` is not set, tries to detect from `.git` folder
4. Falls back to `latest` if all else fails

## Manual Override

You can still explicitly set the frontend version:

### Option 1: Environment Variable
```bash
docker run -e FRONTEND_VERSION=1.2.3 api:staging
```

### Option 2: Docker Compose
```yaml
services:
  api:
    environment:
      - FRONTEND_VERSION=1.2.3  # Use specific version
```

### Option 3: Build Argument
```bash
docker build \
  --build-arg GIT_BRANCH=staging \
  --build-arg FRONTEND_VERSION=1.2.3 \
  -t api:staging .
```

## Usage Examples

### Standard Staging Deployment
```bash
# Build from staging branch - automatically uses staging frontend
git checkout staging
docker build --build-arg GIT_BRANCH=staging -t api:staging .
docker run api:staging

# Container logs will show:
# [2026-04-16 12:00:00] Auto-detected frontend version from branch 'staging': staging
# [2026-04-16 12:00:01] Fetching staging version information...
# [2026-04-16 12:00:02] Staging tarball: frontend-1.2.3-staging.tar.gz
```

### Production Deployment
```bash
# Build from main branch - automatically uses latest frontend
git checkout main
docker build --build-arg GIT_BRANCH=main -t api:prod .
docker run api:prod

# Container logs will show:
# [2026-04-16 12:00:00] Auto-detected frontend version from branch 'main': latest
# [2026-04-16 12:00:01] Fetching latest version information...
# [2026-04-16 12:00:02] Latest release tag: v1.2.3
```

### Testing Specific Frontend Version on Staging
```bash
# Override to test specific frontend version
docker run -e FRONTEND_VERSION=1.2.2 api:staging

# Container logs will show:
# [2026-04-16 12:00:00] Using explicit FRONTEND_VERSION: 1.2.2
# [2026-04-16 12:00:01] Using specified version: 1.2.2
```

## Benefits

✅ **Zero configuration** needed for standard deployments  
✅ **Branch alignment** - staging backend uses staging frontend automatically  
✅ **Reduces errors** - no more mismatched frontend/backend versions  
✅ **Still flexible** - can override when needed for testing  
✅ **Backward compatible** - existing explicit configs still work  

## Troubleshooting

### Frontend version not auto-detected

**Check**:
1. Was `GIT_BRANCH` passed as build arg?
   ```bash
   docker inspect api:staging | grep GIT_BRANCH
   ```

2. Is `.git` folder available in container? (Usually not in production images)

**Solution**: Always pass `--build-arg GIT_BRANCH=$BRANCH` during build

### Using wrong frontend version

**Check container logs**:
```bash
docker logs container-name 2>&1 | grep -i frontend
```

Look for:
- "Auto-detected frontend version from branch..."
- "Using explicit FRONTEND_VERSION..."

**Solution**: Set explicit `FRONTEND_VERSION` environment variable

### Want to disable auto-detection

Set `FRONTEND_VERSION` explicitly:
```yaml
environment:
  - FRONTEND_VERSION=latest  # Always use latest, ignore branch
```

## Migration from Previous Behavior

### Before (Required Configuration)
```yaml
services:
  api:
    environment:
      - FRONTEND_VERSION=staging  # Had to set manually
```

### After (Auto-detected)
```yaml
services:
  api:
    # FRONTEND_VERSION auto-detected from GIT_BRANCH
    # Only set if you want to override
```

### Migration Steps

1. **Update build scripts** to pass `GIT_BRANCH`:
   ```bash
   docker build --build-arg GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD) .
   ```

2. **Remove explicit `FRONTEND_VERSION`** from compose files (optional)

3. **Test** that correct frontend is downloaded

4. **Add overrides** only where needed for special cases

## See Also

- [FRONTEND_ASSET_FLOW.md](FRONTEND_ASSET_FLOW.md) - Complete download flow documentation
- [FRONTEND_ASSET_FIXES.md](FRONTEND_ASSET_FIXES.md) - Bug fixes and edge cases
- [FRONTEND_WORKFLOW_IMPROVEMENTS.md](FRONTEND_WORKFLOW_IMPROVEMENTS.md) - Future enhancements
