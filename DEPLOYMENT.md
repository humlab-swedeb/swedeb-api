# Environment Deployment Guide

## Branch Strategy

This project uses a three-branch workflow:

```
dev → test → staging → main
 ↑      ↑        ↑        ↑
 │      │        │        └── Production releases (semantic versioning)
 │      │        └────────── Staging/pre-production testing
 │      └─────────────────── Test environment
 └────────────────────────── Integration branch (feature work lands here, no auto-builds)
```

### Workflow
1. **Feature Development**: Create feature branches and PR to `dev`
2. **Integration**: Merge features to `dev` (no automatic builds)
3. **Test Environment**: PR `dev` → `test` (builds `test` images)
4. **Staging Testing**: PR `test` → `staging` (builds `staging` images)
5. **Production Release**: PR `staging` → `main` (builds production images, creates release)

## Architecture Overview

All three environments use the **same unified build script** (`.github/scripts/build-and-push-image.sh`) with different parameters:

- **Test**: `.github/workflows/test.yml` calls `build-and-push-image.sh {version} test`
- **Staging**: `.github/workflows/staging.yml` calls `build-and-push-image.sh {version} staging`
- **Production**: `.releaserc.yml` calls `build-and-push-image.sh {version} production`

This ensures consistency and maintainability across environments.

## Image Tagging Strategy

### Test (test branch)
When code is pushed to `test`, the test workflow creates:
- `ghcr.io/humlab-swedeb/swedeb-api:0.6.1-test` - Versioned test build
- `ghcr.io/humlab-swedeb/swedeb-api:test` - Latest test build
- `ghcr.io/humlab-swedeb/swedeb-api:test-latest` - Test alias

### Staging (staging branch)
When code is pushed to `staging`, the staging workflow creates:
- `ghcr.io/humlab-swedeb/swedeb-api:0.6.1-staging` - Versioned staging
- `ghcr.io/humlab-swedeb/swedeb-api:staging` - Latest staging

### Production (main branch)
When code is pushed to `main`, semantic-release creates:
- `ghcr.io/humlab-swedeb/swedeb-api:0.6.1` - Specific version
- `ghcr.io/humlab-swedeb/swedeb-api:0.6` - Minor version
- `ghcr.io/humlab-swedeb/swedeb-api:0` - Major version
- `ghcr.io/humlab-swedeb/swedeb-api:latest` - Latest release
- `ghcr.io/humlab-swedeb/swedeb-api:production` - Production tag

## Deployment Workflows

### Test Environment

**Auto-deploy on test push:**
```bash
# Push to test branch triggers automatic test build
git push origin test
```

**Manual deploy specific version:**
```bash
# Via GitHub UI: Actions → Deploy to Test → Run workflow
# Enter version: 0.6.1 (or leave empty for current version)

# Or deploy locally:
cd docker
docker-compose -f compose.test.yml pull
docker-compose -f compose.test.yml up -d
```

### Staging Environment

**Auto-deploy on staging push:**
```bash
# Push to staging branch triggers automatic staging build
git push origin staging
```

**Manual deploy specific version:**
```bash
# Via GitHub UI: Actions → Deploy to Staging → Run workflow
# Enter version: 0.6.1 (or leave empty for current version)

# Or deploy locally:
cd docker
docker-compose -f compose.staging.yml pull
docker-compose -f compose.staging.yml up -d
```

### Production Environment

**Option 1: Use production tag (auto-updates)**
```yaml
# compose.production.yml
image: ghcr.io/humlab-swedeb/swedeb-api:production
```

**Option 2: Pin specific version (recommended)**
```yaml
# compose.production.yml
image: ghcr.io/humlab-swedeb/swedeb-api:0.6.1
```

**Deploy:**
```bash
cd docker

# Pull latest production image
docker-compose -f compose.production.yml pull

# Restart with new image
docker-compose -f compose.production.yml up -d

# Verify deployment
docker-compose -f compose.production.yml ps
docker-compose -f compose.production.yml logs -f
```

## Promotion Workflow

### From Dev → Staging → Production

```bash
# 1. Develop on feature branch
git checkout -b feature/my-feature
# ... make changes ...
git commit -m "feat: add new feature"

# 2. Merge to dev (triggers staging deployment)
git checkout dev
git merge feature/my-feature
git push origin dev

# 3. Test on staging
# Visit staging environment and verify

# 4. Promote to production via PR
git checkout main
git merge dev  # Or create PR: dev → main
git push origin main

# 5. Semantic-release creates new version automatically
# GitHub Actions builds and tags production image

# 6. Update production compose file
cd docker
# Edit compose.production.yml to pin new version
sed -i 's/:production/:0.6.1/' compose.production.yml

# 7. Deploy to production
docker-compose -f compose.production.yml pull
docker-compose -f compose.production.yml up -d
```

## Frontend Versioning

The API Dockerfile uses frontend via build arg:
```dockerfile
ARG FRONTEND_VERSION=latest
FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
```

### Pin Frontend Version for Staging
```bash
# Modify staging workflow or set environment variable
FRONTEND_VERSION=0.10.0
```

### Pin Frontend Version for Production
Production builds use `latest` by default, but you can override:
```bash
# Local build with specific frontend
docker build --build-arg FRONTEND_VERSION=0.10.0 -t custom-build .
```

## Rollback Procedure

### Quick Rollback
```bash
cd docker

# Rollback to specific version
docker-compose -f compose.production.yml down
sed -i 's/:0.6.1/:0.6.0/' compose.production.yml
docker-compose -f compose.production.yml pull
docker-compose -f compose.production.yml up -d
```

### Emergency Rollback via Tag
```bash
# Re-tag old version as production
docker pull ghcr.io/humlab-swedeb/swedeb-api:0.6.0
docker tag ghcr.io/humlab-swedeb/swedeb-api:0.6.0 ghcr.io/humlab-swedeb/swedeb-api:production
docker push ghcr.io/humlab-swedeb/swedeb-api:production

# Redeploy
docker-compose -f compose.production.yml pull
docker-compose -f compose.production.yml up -d
```

## Best Practices

1. **Staging**: Always use `:staging` tag for auto-updates
2. **Production**: Pin specific versions (`:0.6.1`) for controlled deployments
3. **Testing**: Verify on staging before promoting to production
4. **Rollback Plan**: Keep previous version pinned in comments for quick rollback
5. **Frontend Sync**: Ensure compatible frontend versions in multi-image setup

## Monitoring

```bash
# Check running version
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

# View logs
docker-compose -f compose.production.yml logs -f --tail=100

# Check image versions
docker images ghcr.io/humlab-swedeb/swedeb-api
```

## Build Scripts Reference

### Unified Build Script
**Location**: `.github/scripts/build-and-push-image.sh`

**Usage**:
```bash
build-and-push-image.sh <version> [environment]
# environment: production (default) or staging
```

**Called by**:
- **Production**: semantic-release via `.releaserc.yml` → `publishCmd`
- **Staging**: GitHub Actions via `.github/workflows/staging.yml`

**What it does**:
1. Authenticates to GHCR (with cross-org token if available)
2. Builds Docker image with appropriate tags based on environment
3. Pushes all tags to registry

### Asset Preparation Script
**Location**: `.github/scripts/prepare-release-assets.sh`

**Usage**:
```bash
prepare-release-assets.sh <version>
```

**Called by**: semantic-release via `.releaserc.yml` → `prepareCmd`

**What it does**:
1. Validates version format (SemVer)
2. Updates `pyproject.toml` with new version
3. Syncs version to `api_swedeb/__init__.py`
4. Builds Python wheel package

