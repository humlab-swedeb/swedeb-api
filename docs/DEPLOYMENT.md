# 🚀 Comprehensive Deployment Guide

This document provides complete instructions for deploying the Swedeb API system across all environments (test, staging, production) using the automated CI/CD pipeline and Docker containers.

## 📋 Table of Contents

- [Branch Strategy & Workflows](#branch-strategy--workflows)
- [Architecture Overview](#architecture-overview)
- [Image Tagging Strategy](#image-tagging-strategy)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment Prerequisites](#deployment-prerequisites)
- [Container Runtime Options](#container-runtime-options)
- [Environment-Specific Deployment Instructions](#environment-specific-deployment-instructions)
  - [Podman Quadlet Deployment Guide](./DEPLOY_PODMAN.md)
- [Promotion Workflows](#promotion-workflows)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Frontend Runtime Asset Management](#frontend-runtime-asset-management)
- [Troubleshooting](./TROUBLESHOOTING.md)
- [Best Practices](#best-practices)
- [Build Scripts Reference](#build-scripts-reference)

## Branch Strategy & Workflows

This project uses a **four-branch workflow** with progressive environment promotion:

```
┌────────────────────────────────────────────────────────────────┐
│                    BRANCH WORKFLOW STRATEGY                    │
└────────────────────────────────────────────────────────────────┘

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
    │  test   │ ← Test environment (auto-builds)
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │ staging │ ← Staging/pre-production (auto-builds)
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │  main   │ ← Production releases (semantic versioning)
    └─────────┘
```

| Branch      | Purpose                      | Build Trigger  | Image Tags                                                |
|-------------|------------------------------|----------------|-----------------------------------------------------------|
| **dev**     | Integration (no auto-builds) | ❌ Manual only  | N/A                                                       |
| **test**    | Test environment             | ✅ Auto on push | `{version}-test`, `test`, `test-latest`                   |
| **staging** | Pre-production validation    | ✅ Auto on push | `{version}-staging`, `staging`                            |
| **main**    | Production releases          | ✅ Auto on push | `{version}`, `{major}`, `{minor}`, `latest`, `production` |

For detailed developer workflow instructions, see the [Workflow Guide](./WORKFLOW_GUIDE.md).

## Architecture Overview

### System Architecture
```
┌───────────────────────────────────────────────────────────┐
│                      GitHub Actions                       │
│  ┌─────────────┐     ┌──────────────────────────────────┐ │
│  │Push to test/│ ──> │ Build & Push Backend Image Only  │ │
│  │staging/main │     └──────────────────────────────────┘ │
│  └─────────────┘                     │                    │
└──────────────────────────────────────┼────────────────────┘
                                       ▼
┌───────────────────────────────────────────────────────────┐
│                 GitHub Container Registry                 │
│          ghcr.io/humlab-swedeb/swedeb-api                 │
│          (backend image tags per environment)             │
└──────────────────────────────────────┬────────────────────┘
                                       │
                                       │ container start
                                       ▼
┌───────────────────────────────────────────────────────────┐
│                       Target Server                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                Swedeb API Container                 │  │
│  │  1. Start entrypoint                                │  │
│  │  2. Download/update frontend assets                 │  │
│  │     from swedeb_frontend release artifacts          │  │
│  │  3. Persist deployed version in .frontend_version   │  │
│  │  4. Start backend API + serve frontend from /public │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

### Unified Build System

All three environments use the **same unified build script** (`.github/scripts/build-and-push-image.sh`) with different parameters:

- **Test**: `.github/workflows/test.yml` calls `build-and-push-image.sh {version} test`
- **Staging**: `.github/workflows/staging.yml` calls `build-and-push-image.sh {version} staging`
- **Production**: `.releaserc.yml` calls `build-and-push-image.sh {version} production`

This ensures consistency and maintainability across environments. The script now builds a backend image only; frontend assets are resolved later at container startup via runtime configuration.

### Backend Image + Runtime Frontend Download

The deployment model is now decoupled:
- **Backend image**: Built from the current repository and published to GHCR
- **Frontend assets**: Downloaded at container startup from `humlab-swedeb/swedeb_frontend` releases
- **CWB tools**: Still provided by the `ghcr.io/humlab/cwb-container:latest` base image

Key runtime components:
- `docker/download-frontend.sh` downloads release artifacts from GitHub
- `docker/entrypoint.sh` checks the requested frontend version and refreshes assets when needed
- `docker/healthcheck.sh` validates both the API and frontend asset presence
- `/app/public/.frontend_version` records the currently deployed frontend version inside the container

Supported frontend version modes:

```bash
FRONTEND_VERSION=latest
FRONTEND_VERSION=staging
FRONTEND_VERSION=v1.2.3
```

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

## CI/CD Pipeline

### Automatic Release Pipeline (Production)

When code is pushed to `main`, semantic-release executes:

1. **Commit Analysis**: Analyzes commits using conventional commit format
2. **Version Determination**: Calculates version bump (major/minor/patch)
3. **Asset Preparation**: 
   - Updates `pyproject.toml` and `api_swedeb/__init__.py`
   - Builds Python wheel package (`.whl`)
4. **GitHub Release**: Creates release with changelog and wheel artifact
5. **Docker Build & Push**: Builds and publishes backend-only multi-tagged images
6. **Git Commit**: Commits `CHANGELOG.md` and version updates back to `main`

Production releases no longer attempt to synchronize frontend and backend versions during image build. Frontend selection is a deployment-time concern via `FRONTEND_VERSION`.

### Environment Build Pipelines (Test & Staging)

Test and staging branches trigger simplified workflows:

1. **Checkout Code**: Retrieves current branch state
2. **Get Version**: Reads version from `pyproject.toml`
3. **Docker Login**: Authenticates to GHCR
4. **Build & Push**: Creates environment-specific backend image tags

These workflows no longer pass a frontend build argument. The deployed environment decides which frontend release to fetch when the container starts.

### Artifacts Produced

| Artifact Type     | Location                           | Environments                  |
|-------------------|------------------------------------|-------------------------------|
| **Docker Image**  | `ghcr.io/humlab-swedeb/swedeb-api` | All (test/staging/production) |
| **Python Wheel**  | GitHub Releases                    | Production only               |
| **Release Notes** | GitHub Releases                    | Production only               |
| **Git Tags**      | Repository                         | Production only               |

## Deployment Prerequisites

### Server Requirements
- **Podman**: Version 4.0+ (recommended for production)
- **systemd**: For Quadlet integration

### Network Requirements
- Outbound HTTPS access from the container host to GitHub Releases
- If `FRONTEND_VERSION=latest`, outbound access to the GitHub API for release resolution
- Registry access to `ghcr.io/humlab-swedeb/swedeb-api`

### Data Requirements

The application requires corpus data and metadata on the host system:

```bash
# Required directory structure on host
/data/swedeb/
├── v1.4.1/                         # Corpus version
│   ├── registry/                   # CWB registry
│   ├── dtm/                        # Document-term matrices
│   ├── tagged_frames/              # Processed corpus files
│   ├── ...
│   └── riksprot_metadata.v1.1.3.db # Database file (copy)
└── metadata/
    ├── v1.1.3/                     # Metadata version (not used)
    └── riksprot_metadata.v1.1.3.db # Database file (not used)
```

### Authentication Setup

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | podman login ghcr.io -u $GITHUB_USERNAME --password-stdin

# Or using Personal Access Token
podman login ghcr.io -u your-username
# Enter PAT when prompted

# Store credentials for systemd services (if using Quadlet)
# Credentials are stored in ${XDG_RUNTIME_DIR}/containers/auth.json
# or /run/user/$(id -u)/containers/auth.json
```

**Note**: For cross-organization access to `ghcr.io/humlab/cwb-container`, the `CWB_REGISTRY_TOKEN` secret must be configured in GitHub Actions.

### Runtime Configuration

The decoupled deployment model adds runtime configuration that controls frontend selection independently from the backend image tag:

```bash
SWEDEB_IMAGE_TAG=latest
FRONTEND_VERSION=latest
SWEDEB_CONFIG_PATH=/app/config/config.yml
SWEDEB_DATA_FOLDER=/data
```

Use `FRONTEND_VERSION` to choose which frontend release the container should fetch at startup. Changing `FRONTEND_VERSION` and restarting the container is enough to roll the frontend forward or back without rebuilding the backend image.

---

## Deployment Approach

This project uses **Podman with Quadlet** as the primary deployment method for production environments.

## Podman Quadlet Setup

For Podman installation and Quadlet configuration details, see the dedicated **[Podman Deployment Guide](./DEPLOY_PODMAN.md)**.

---

## Environment-Specific Deployment Instructions

For detailed step-by-step deployment procedures, see the **[Podman Quadlet Deployment Guide](./DEPLOY_PODMAN.md)**.

### Environment Overview

| Environment    | Port | Image Tag                   | Branch    | Purpose                                         |
|----------------|------|-----------------------------|-----------|-------------------------------------------------|
| **Test**       | 8001 | `test`                      | `test`    | QA validation and integration testing           |
| **Staging**    | 8002 | `staging`                   | `staging` | Pre-production environment mirroring production |
| **Production** | 8092 | `{version}` (e.g., `0.7.0`) | `main`    | Production deployment serving end users         |

**Important**: Always pin specific backend versions in production (for example `0.7.0`) and explicitly set `FRONTEND_VERSION` to the intended frontend release. Do not rely on floating production defaults unless that behavior is intentional.

For deployment instructions:
- [Podman Quadlet Deployment Guide](./DEPLOY_PODMAN.md) - Recommended for production

---

## Promotion Workflows

For detailed promotion workflows including the complete pipeline and hotfix procedures, see the [Workflow Guide](./WORKFLOW_GUIDE.md).

**Quick links:**
- [Complete Promotion Pipeline](./WORKFLOW_GUIDE.md#complete-promotion-pipeline) - Full end-to-end workflow from feature to production
- [Hotfix Workflow](./WORKFLOW_GUIDE.md#hotfix-workflow) - Fast-track and emergency procedures

## Rollback Procedures

For rollback procedures, see:
- [Podman Quadlet Rollback Guide](./DEPLOY_PODMAN.md#rollback-procedures) - Recommended
- [Docker Compose Rollback Guide](./DEPLOY_DOCKER.md#rollback-procedures) - Alternative

## Monitoring & Maintenance

For monitoring and maintenance procedures, see:
- [Podman Quadlet Monitoring Guide](./DEPLOY_PODMAN.md#monitoring--maintenance) - Recommended
- [Docker Compose Monitoring Guide](./DEPLOY_DOCKER.md#monitoring--maintenance) - Alternative

### Application Health

```bash
# Check API endpoints
curl http://localhost:8092/docs
curl http://localhost:8092/health  # If health endpoint exists

# Check API version
curl http://localhost:8092/version  # If version endpoint exists

# Test specific endpoint
curl http://localhost:8092/api/v1/your-endpoint

# Verify frontend assets are present
podman exec swedeb-api cat /app/public/.frontend_version
podman exec swedeb-api test -f /app/public/index.html
```

## Frontend Runtime Asset Management

Frontend assets are no longer embedded into the backend image. They are downloaded during container startup and cached in `/app/public`.

Operational implications:
- First startup of a new container can take longer because assets are fetched before the API starts
- Reusing the same `FRONTEND_VERSION` avoids unnecessary downloads because `.frontend_version` is checked first
- Changing `FRONTEND_VERSION` and restarting the container forces a refresh of frontend assets
- Failed frontend downloads now block container readiness rather than surfacing as a bad build artifact

Recommended verification steps after deployment:

```bash
# Watch startup logs for frontend download/update messages
podman logs -f swedeb-api

# Confirm deployed frontend version
podman exec swedeb-api cat /app/public/.frontend_version

# Confirm frontend entry file exists
podman exec swedeb-api test -f /app/public/index.html && echo ok
```

If you deploy with Docker Compose instead of Podman, use the equivalent `docker compose logs` and `docker exec` commands.

## Troubleshooting

For troubleshooting common deployment issues, see the dedicated [Troubleshooting Guide](./TROUBLESHOOTING.md).

## Best Practices

### Development
1. **Uses conventional commits** - Ensures proper semantic versioning
2. **No auto-builds on dev** - Keep dev as stable integration point
3. **Test thoroughly** - Use test environment before promoting
4. **Code review** - All PRs require review before merge

### Deployment
1. **Pin backend and frontend versions in production** - Use a specific image tag (for example `0.7.0`) and an explicit `FRONTEND_VERSION`
2. **Auto-update for test/staging** - Use environment tags (`test`, `staging`)
3. **Validate before promotion** - Test in each environment before promoting
4. **Document changes** - Update changelog and release notes
5. **Monitor after deployment** - Watch logs and metrics

### Operations (Podman)
1. **Use rootless mode** - Better security isolation
2. **Enable lingering** - Ensure services survive logout (`loginctl enable-linger`)
3. **Pin versions in Quadlet** - Explicitly set image tags
5. **Monitor via journald** - Centralized logging with `journalctl`
6. **Test Quadlet changes** - Validate with `systemctl --user daemon-reload`
7. **Auto-update carefully** - Use systemd timers with notification on failure
9. **Health checks** - Configure health checks in container definitions
10. **Backup Quadlet files** - Keep versioned copies of `.container` files


## Build Scripts Reference

### 1. Unified Build Script

**Location**: `.github/scripts/build-and-push-image.sh`

**Purpose**: Single source of truth for building and pushing Docker images across all environments.

**Usage**:
```bash
build-and-push-image.sh <version> <environment>
# version: Semantic version (e.g., 0.6.1)
# environment: test | staging | production
```

**Called by**:
- **Test**: `.github/workflows/test.yml`
- **Staging**: `.github/workflows/staging.yml`
- **Production**: semantic-release via `.releaserc.yml` → `publishCmd`

**Environment Variables Required**:
- `DOCKER_USERNAME`: GitHub actor
- `DOCKER_PASSWORD`: GitHub token
- `CWB_REGISTRY_TOKEN`: PAT for cross-org access (optional)
- `GITHUB_REPOSITORY`: Org/repo name

**What it does**:
1. Validates environment parameter (test/staging/production)
2. Authenticates to GHCR (uses `CWB_REGISTRY_TOKEN` if available)
3. Builds the backend image with the runtime frontend download scripts included
4. Tags image according to environment:
   - **Test**: `{version}-test`, `test`, `test-latest`
   - **Staging**: `{version}-staging`, `staging`
   - **Production**: `{version}`, `{major}`, `{minor}`, `latest`, `production`
5. Pushes all tags to registry

What it no longer does:
- It does not coordinate a frontend image tag during build
- It does not embed frontend assets into the backend image
- It does not require a frontend rebuild when only backend code changes

**Example**:
```bash
# Production build
./build-and-push-image.sh 0.6.1 production
# Creates: 0.6.1, 0.6, 0, latest, production

# Staging build
./build-and-push-image.sh 0.6.1 staging
# Creates: 0.6.1-staging, staging

# Test build
./build-and-push-image.sh 0.6.1 test
# Creates: 0.6.1-test, test, test-latest
```

### 2. Asset Preparation Script

**Location**: `.github/scripts/prepare-release-assets.sh`

**Purpose**: Prepares release artifacts for production releases.

**Usage**:
```bash
prepare-release-assets.sh <version>
# version: Semantic version (e.g., 0.6.1)
```

**Called by**: semantic-release via `.releaserc.yml` → `prepareCmd` (production only)

**What it does**:
1. Validates version format (SemVer compliance)
2. Updates `pyproject.toml` with new version
3. Syncs version to `api_swedeb/__init__.py`
4. Builds Python wheel package using uv
5. Outputs wheel to `dist/` directory

**Example**:
```bash
./prepare-release-assets.sh 0.6.1
# Creates: dist/api_swedeb-0.6.1-py3-none-any.whl
```

### 3. Files Involved in CI/CD

```
.github/
├── workflows/
│   ├── test.yml                       # Test environment workflow
│   ├── staging.yml                    # Staging environment workflow
│   └── release.yml                    # Production release workflow
└── scripts/
    ├── build-and-push-image.sh        # Unified Docker build script
    └── prepare-release-assets.sh      # Version sync & wheel build

.releaserc.yml                         # Semantic-release configuration
package.json                           # Node.js dependencies for semantic-release
pyproject.toml                         # Python project metadata & dependencies
```

### Docker Build Files

```
docker/
├── Dockerfile                         # Backend image build with runtime frontend download support
├── download-frontend.sh               # Frontend artifact downloader
├── entrypoint.sh                      # Startup script that refreshes frontend assets if needed
├── healthcheck.sh                     # API + frontend asset health validation
└── deployment/example-decoupled.env   # Example runtime configuration for decoupled deployments
```

## Deployment Checklist

### Pre-Deployment
- [ ] Data directory structure exists (`/data/swedeb/`)
- [ ] Proper permissions set on data directories (user 1021:1021)
- [ ] Compose installed and running
- [ ] Network connectivity to GHCR verified
- [ ] Network connectivity to GitHub Releases verified
- [ ] Authentication to GHCR configured
- [ ] `FRONTEND_VERSION` set for the target environment
- [ ] Backup of existing configuration (if updating)

### Test Deployment
- [ ] Test environment configured in `.env`
- [ ] Image pull successful (`:test` tag)
- [ ] Container starts without errors
- [ ] Frontend download completes during startup
- [ ] `/app/public/.frontend_version` matches the requested version
- [ ] Application responds to requests
- [ ] Integration tests pass
- [ ] Logs show no errors

### Staging Deployment
- [ ] Staging environment configured in `.env`
- [ ] Image pull successful (`:staging` tag)
- [ ] Container starts without errors
- [ ] Frontend assets refresh as expected for the configured version
- [ ] All endpoints accessible
- [ ] Acceptance tests pass
- [ ] Performance meets requirements
- [ ] Security validation completed

### Production Deployment
- [ ] Specific version tag pinned in config (not `latest`)
- [ ] `FRONTEND_VERSION` pinned or intentionally configured as floating
- [ ] Image pull successful (specific version)
- [ ] Container starts without errors
- [ ] Reverse proxy configured (if applicable)
- [ ] SSL certificates valid
- [ ] DNS configured correctly
- [ ] Health checks passing
- [ ] Frontend version file verified after startup
- [ ] Monitoring configured
- [ ] Log rotation configured
- [ ] Backup procedures implemented
- [ ] Rollback procedure tested
- [ ] Team notified of deployment
- [ ] Documentation updated

## Related Resources

- [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) - Developer workflow and branching strategy
- [WORKFLOW_ARCHITECTURE.md](./WORKFLOW_ARCHITECTURE.md) - CI/CD architecture diagrams
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Troubleshooting common deployment issues
- [README.md](../README.md) - Project overview and quick start
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Podman Documentation](https://docs.podman.io/)
- [Quadlet Documentation](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [systemd.unit Manual](https://www.freedesktop.org/software/systemd/man/systemd.unit.html)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Semantic Release](https://semantic-release.gitbook.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

*Last updated: Reflects decoupled frontend/backend deployments with runtime frontend asset downloads.*

