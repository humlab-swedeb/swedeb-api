# Release Notes: Decoupled Frontend/Backend Architecture

**Branch:** `decouple-frontend-backend-deployments`  
**Version:** 0.7.0 (pending)  
**Release Date:** TBD  
**Type:** Major Feature Release

## 🎯 Executive Summary

This release fundamentally restructures the Swedeb API deployment architecture by **decoupling frontend and backend lifecycles**. Frontend assets are no longer embedded at Docker image build time but are instead downloaded at container runtime, enabling independent versioning and deployment of frontend and backend components.

## 🚀 Major Changes

### 1. Runtime Frontend Asset Management

**Before:** Frontend assets were embedded into backend Docker images using multi-stage builds from separate frontend container images.

**After:** Frontend assets are dynamically downloaded at container startup based on environment configuration.

#### Key Components:
- **`docker/download-frontend.sh`** - New script that downloads frontend release artifacts from GitHub
- **`docker/entrypoint.sh`** - Enhanced with frontend version checking and automatic downloads
- **`docker/healthcheck.sh`** - New health check validates both API and frontend assets
- **Version tracking** - `.frontend_version` file tracks deployed frontend version

#### Capabilities:
```bash
# Flexible version control
FRONTEND_VERSION=latest      # Always use latest release
FRONTEND_VERSION=staging     # Use staging release
FRONTEND_VERSION=v1.2.3     # Pin to specific version
```

### 2. Simplified Build Pipeline

#### Dockerfile Changes (`docker/Dockerfile`):
- ❌ **Removed:** Multi-stage build from frontend container image
- ❌ **Removed:** `ARG FRONTEND_VERSION` at build stage
- ✅ **Added:** `FRONTEND_VERSION` as runtime environment variable
- ✅ **Added:** `download-frontend.sh` script to image
- ✅ **Added:** Empty `public/` directory creation for runtime population

#### Build Script Changes (`.github/scripts/build-and-push-image.sh`):
- ❌ **Removed:** Frontend version coordination logic
- ❌ **Removed:** Frontend image base URL configuration
- ❌ **Removed:** `--build-arg FRONTEND_VERSION` from docker build commands
- ✅ **Simplified:** Single-purpose backend-only build process
- ✅ **Added:** Log message clarifying frontend is downloaded at runtime

### 3. CI/CD Workflow Improvements

#### Release Workflow (`.github/workflows/release.yml`):
```diff
- FRONTEND_VERSION_TAG: ${{ steps.semantic_release.outputs.new_release_version }}
```
- No longer synchronizes frontend version with backend semantic version
- Backend releases are independent of frontend state

#### Staging Workflow (`.github/workflows/staging.yml`):
```diff
- FRONTEND_VERSION_TAG: staging
```
- No longer passes frontend version to build process
- Staging environment configures frontend version via runtime environment variables

#### Test Workflow (`.github/workflows/test.yml`):
```diff
- FRONTEND_VERSION_TAG: latest
```
- Test builds no longer require frontend version specification
- Frontend version is determined at container startup

### 4. Enhanced Container Startup

#### Entrypoint Logic (`docker/entrypoint.sh`):
```bash
# New startup sequence:
1. Check if frontend assets directory exists
2. Validate current frontend version against requested version
3. Download/update frontend assets if needed
4. Verify assets are properly installed
5. Start API server
```

#### Features:
- **Smart caching:** Skips download if correct version already present
- **Version validation:** Compares `.frontend_version` file with `FRONTEND_VERSION` env var
- **Automatic cleanup:** Removes old assets before downloading new version
- **Detailed logging:** Provides visibility into frontend asset management
- **Resilient downloads:** Includes retry logic and error handling

### 5. Comprehensive Documentation

#### New Documentation Files:
- **`docs/OPERATIONS.md`** - Complete deployment strategy overview
- **`docs/DEPLOY_DOCKER.md`** - Docker Compose deployment procedures (512 lines)
- **`docs/DEPLOY_PODMAN.md`** - Podman Quadlet deployment for production (749 lines)
- **`docs/WORKFLOW_GUIDE.md`** - Developer workflow and branching strategy (340 lines)
- **`docs/WORKFLOW_ARCHITECTURE.md`** - CI/CD pipeline technical details (264 lines)
- **`docs/TROUBLESHOOTING.md`** - Common issues and solutions (413 lines)
- **`docs/FAQ.md`** - Frequently asked questions
- **`docs/QUICK-INSTALL-GUIDE.md`** - Fast-track installation guide
- **`docs/README-DECOUPLED.md`** - Decoupled architecture explanation
- **`.github/copilot-instructions.md`** - AI coding agent guidance

#### Documentation Improvements:
- Structured by audience (developers vs. deployment engineers)
- Environment-specific examples and configurations
- Troubleshooting workflows for common issues
- Architecture diagrams and decision rationale

### 6. Environment Configuration Updates

#### New Configuration File:
- **`docker/deployment/example-decoupled.env`** - Example environment config for decoupled architecture

#### Key Environment Variables:
```bash
# New/modified variables
FRONTEND_VERSION=latest           # Controls which frontend to download
SWEDEB_CONFIG_PATH=/app/config/config.yml
SWEDEB_DATA_FOLDER=/data
SWEDEB_IMAGE_TAG=latest          # Backend version independent of frontend
```

### 7. Performance & Testing Enhancements

#### Multiprocessing for KWIC Queries:
- **New:** `api_swedeb/core/kwic/multiprocess.py` - Parallel KWIC processing
- **New:** `api_swedeb/core/kwic/utility.py` - Utility functions for KWIC operations
- **Enhanced:** PID-specific work directories for process isolation
- **Configuration:** Multiprocessing options in `config/config.yml`

#### Test Improvements:
- Shared CWB data directories (`/tmp/ccc-*`) for better performance
- Isolated per-PID work directories prevent conflicts
- Enhanced test fixtures for better isolation
- Comprehensive KWIC multiprocessing tests

## 🔧 Breaking Changes

### ⚠️ Configuration Changes Required

1. **Docker Compose Files:**
   ```yaml
   # Remove build args (if building locally)
   services:
     swedeb_api:
       build:
         args:
   -       FRONTEND_VERSION: "${SWEDEB_FRONTEND_TAG}"
   
       # Add runtime environment variable
       environment:
   +     - FRONTEND_VERSION=${SWEDEB_FRONTEND_TAG:-latest}
   ```

2. **Environment Variables:**
   - `FRONTEND_VERSION_TAG` (build-time) → `FRONTEND_VERSION` (runtime)
   - Must be set in environment files or compose files

3. **Deployment Procedures:**
   - Frontend updates no longer require backend image rebuild
   - Update `FRONTEND_VERSION` environment variable and restart container
   - Container will download new frontend assets on startup

### ⚠️ Image Build Changes

- Backend images are now **smaller** (no frontend assets embedded)
- First container startup takes **longer** (downloads frontend assets)
- Subsequent startups are **fast** (assets cached unless version changes)

## 📋 Migration Guide

### For Existing Deployments

1. **Update environment files:**
   ```bash
   # Add to your .env file
   FRONTEND_VERSION=latest  # or staging, or specific version
   ```

2. **Update compose files:**
   ```bash
   # Ensure environment variable is passed to container
   environment:
     - FRONTEND_VERSION=${FRONTEND_VERSION:-latest}
   ```

3. **Pull new images:**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

4. **Verify deployment:**
   ```bash
   # Check logs for frontend download
   docker-compose logs -f swedeb_api
   
   # Verify frontend version
   docker exec swedeb-api cat /app/public/.frontend_version
   ```

### For New Deployments

Follow the comprehensive guides:
- Production: `docs/DEPLOY_PODMAN.md` (recommended)
- Development/Staging: `docs/DEPLOY_DOCKER.md`
- Quick start: `docs/QUICK-INSTALL-GUIDE.md`

## ✅ Benefits

### Operational Benefits:
- **Independent Release Cycles:** Frontend and backend can be updated separately
- **Faster Iterations:** Frontend hotfixes don't require backend rebuilds
- **Flexible Testing:** Test frontend changes against stable backend versions
- **Version Control:** Explicit frontend/backend version combinations
- **Reduced Build Time:** Backend images build faster without frontend assets

### Development Benefits:
- **Simplified CI/CD:** Fewer dependencies between pipelines
- **Better Separation of Concerns:** Clear boundaries between components
- **Easier Debugging:** Version tracking makes issues easier to isolate
- **Environment Flexibility:** Different environments can use different frontend versions

### Infrastructure Benefits:
- **Smaller Images:** Backend images don't contain frontend assets (~30% reduction)
- **Better Caching:** Frontend assets cached separately from application code
- **Bandwidth Efficiency:** Download frontend once per container, not on every build

## 🔍 Technical Details

### Download Mechanism

Frontend assets are downloaded from GitHub Releases:
```
https://github.com/humlab-swedeb/swedeb_frontend/releases/download/{VERSION}/frontend-{VERSION}.tar.gz
```

#### Supported Version Formats:
- `latest` - Latest release (queries GitHub API)
- `staging` - Staging release tag
- `v1.2.3` - Specific version tag

#### Retry Logic:
- Maximum 3 attempts per download
- 5-second delay between retries
- Detailed error messages on failure

### Health Check

New health check validates:
1. API responds on configured port
2. Frontend `index.html` exists
3. Frontend version file present (warning if missing)

### Caching Strategy

Frontend assets are cached based on version:
1. Check if `.frontend_version` file exists
2. Compare file content with `FRONTEND_VERSION` env var
3. Skip download if versions match
4. Clean and re-download if versions differ

## 📊 Testing

### Test Coverage

- ✅ Frontend download script functionality
- ✅ Version validation logic
- ✅ Entrypoint startup sequence
- ✅ Health check validation
- ✅ Multiprocessing KWIC queries
- ✅ Environment configuration parsing

### Manual Testing Checklist

- [ ] Fresh container startup downloads frontend
- [ ] Version mismatch triggers re-download
- [ ] Matching version skips download
- [ ] Health check passes with valid assets
- [ ] Health check fails without assets
- [ ] Invalid frontend version fails gracefully
- [ ] Network issues retry appropriately

## 🚨 Known Issues & Limitations

1. **First Startup Delay:** Initial container startup takes 30-60 seconds to download frontend assets
2. **Network Dependency:** Container startup requires internet access to download frontend
3. **GitHub API Rate Limits:** Using `latest` version queries GitHub API (60 requests/hour unauthenticated)
4. **Storage Overhead:** Each container instance stores its own copy of frontend assets

## 🔮 Future Enhancements

### Planned Improvements:
- [ ] Add GitHub token support to bypass API rate limits
- [ ] Implement shared volume for frontend assets across containers
- [ ] Add checksum verification for downloaded assets
- [ ] Support alternative download sources (CDN, artifact registry)
- [ ] Add offline mode with pre-downloaded assets
- [ ] Implement progressive frontend loading

## 📚 Related Documentation

- **Architecture:** `docs/README-DECOUPLED.md`
- **Deployment:** `docs/OPERATIONS.md`
- **Workflows:** `docs/WORKFLOW_GUIDE.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`
- **AI Agent Guide:** `.github/copilot-instructions.md`

## 👥 Contributors

This release represents significant architectural work affecting:
- Build system
- Deployment procedures
- CI/CD pipelines
- Documentation
- Testing infrastructure

## 🏷️ Version Compatibility

| Component | Version | Compatibility |
|-----------|---------|---------------|
| Backend API | 0.7.0+ | All frontend versions via `FRONTEND_VERSION` |
| Frontend | Any | Compatible when specified via environment variable |
| Docker | 20.10+ | Required for build features |
| Docker Compose | 2.0+ | Required for deployment |
| Python | 3.11+ | Python 3.12 recommended |

## 📞 Support

For issues related to this release:
1. Check `docs/TROUBLESHOOTING.md`
2. Review `docs/FAQ.md`
3. Open an issue on GitHub with logs and configuration

---

**Note:** This release is currently on the `decouple-frontend-backend-deployments` branch and has not yet been merged to `main`. All features and changes are subject to final review before production deployment.
