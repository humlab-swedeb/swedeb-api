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
  - [Docker Compose Deployment Guide](./DEPLOY_DOCKER.md)
  - [Podman Quadlet Deployment Guide](./DEPLOY_PODMAN.md)
- [Promotion Workflows](#promotion-workflows)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Frontend Versioning](#frontend-versioning)
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

| Branch | Purpose | Build Trigger | Image Tags |
|--------|---------|---------------|------------|
| **dev** | Integration (no auto-builds) | ❌ Manual only | N/A |
| **test** | Test environment | ✅ Auto on push | `{version}-test`, `test`, `test-latest` |
| **staging** | Pre-production validation | ✅ Auto on push | `{version}-staging`, `staging` |
| **main** | Production releases | ✅ Auto on push | `{version}`, `{major}`, `{minor}`, `latest`, `production` |

### Development Workflow
1. **Feature Development**: Create feature branches and PR to `dev`
2. **Integration**: Merge features to `dev` (no automatic builds)
3. **Test Environment**: PR `dev` → `test` (builds test images)
4. **Staging Testing**: PR `test` → `staging` (builds staging images)
5. **Production Release**: PR `staging` → `main` (triggers semantic-release, creates production images)

## Architecture Overview

### System Architecture
```
┌───────────────────────────────────────────────────┐
│                 GitHub Actions                    │
│  ┌─────────────┐    ┌───────────────────────────┐ │
│  │Push to test/│──> │ Build & Push Docker Image │ │
│  │staging/main │    └───────────────────────────┘ │
│  └─────────────┘                │                 │
└─────────────────────────────────┼─────────────────┘
                                  ▼
┌─────────────────────────────────────────────────┐
│           GitHub Container Registry             │
│    ghcr.io/humlab-swedeb/swedeb-api            │
│    (test, staging, production tags)             │
└─────────────────────────────────┼───────────────┘
                                  ▼
┌─────────────────────────────────────────────────┐
│                  Target Server                  │
│  ┌──────────────────────────────────────────┐   │
│  │              Docker Compose              │   │
│  │  ┌────────────────────────────────────┐  │   │
│  │  │         Swedeb API Container       │  │   │
│  │  │  ┌──────────┐  ┌─────────────────┐ │  │   │
│  │  │  │Frontend  │  │   Backend API   │ │  │   │
│  │  │  │Assets    │  │   + CWB Tools   │ │  │   │
│  │  │  └──────────┘  └─────────────────┘ │  │   │
│  │  └────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Unified Build System

All three environments use the **same unified build script** (`.github/scripts/build-and-push-image.sh`) with different parameters:

- **Test**: `.github/workflows/test.yml` calls `build-and-push-image.sh {version} test`
- **Staging**: `.github/workflows/staging.yml` calls `build-and-push-image.sh {version} staging`
- **Production**: `.releaserc.yml` calls `build-and-push-image.sh {version} production`

This ensures consistency and maintainability across environments.

### Multi-Stage Docker Build

The Docker image combines three base images:
- **Frontend**: `ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION}`
- **CWB Tools**: `ghcr.io/humlab/cwb-container:latest` (cross-org access)
- **Application**: Built from current repository

```dockerfile
ARG FRONTEND_VERSION=latest
FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
FROM ghcr.io/humlab/cwb-container:latest AS final
COPY --from=frontend-dist /app/public ./public
# ... rest of build
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

When code is pushed to `main`, semantic-release orchestrates:

1. **Commit Analysis**: Analyzes commits using conventional commit format
2. **Version Determination**: Calculates version bump (major/minor/patch)
3. **Asset Preparation**: 
   - Updates `pyproject.toml` and `api_swedeb/__init__.py`
   - Builds Python wheel package (`.whl`)
4. **GitHub Release**: Creates release with changelog and wheel artifact
5. **Docker Build & Push**: Builds and publishes multi-tagged images
6. **Git Commit**: Commits `CHANGELOG.md` and version updates back to `main`

### Environment Build Pipelines (Test & Staging)

Test and staging branches trigger simplified workflows:

1. **Checkout Code**: Retrieves current branch state
2. **Get Version**: Reads version from `pyproject.toml`
3. **Docker Login**: Authenticates to GHCR
4. **Build & Push**: Creates environment-specific tags

### Artifacts Produced

| Artifact Type | Location | Environments |
|---------------|----------|--------------|
| **Docker Image** | `ghcr.io/humlab-swedeb/swedeb-api` | All (test/staging/production) |
| **Python Wheel** | GitHub Releases | Production only |
| **Release Notes** | GitHub Releases | Production only |
| **Git Tags** | Repository | Production only |

## Deployment Prerequisites

### Server Requirements
- **Docker Engine**: Version 20.10+ 
- **Docker Compose**: Version 2.0+
- **Minimum RAM**: 4GB (8GB+ recommended for production)
- **Disk Space**: 10GB+ for data and images
- **Network**: Internet access for pulling images from GHCR

### Data Requirements

The application requires corpus data and metadata on the host system:

```bash
# Required directory structure on host
/data/swedeb/
├── v1.4.1/                         # Corpus version
│   ├── registry/                   # CWB registry
│   ├── dtm/                        # Document-term matrices
│   ├── tagged_frames/              # Processed corpus files
│   └── ...
└── metadata/
    ├── v1.1.3/                     # Metadata version
    └── riksprot_metadata.v1.1.3.db # Database file
```

### Authentication Setup

#### Docker
```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# Or using Personal Access Token (PAT)
docker login ghcr.io -u your-username
# Enter PAT when prompted
```

#### Podman
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

## Container Runtime Options

You can deploy using either **Docker Compose** (traditional) or **Podman with Quadlet** (recommended for production). This guide covers both approaches.

### Docker Compose (Traditional Approach)

**Pros**:
- Well-established, widely documented
- Rich ecosystem of tools
- docker-compose.yml files are portable

**Cons**:
- Requires Docker daemon running as root
- No native systemd integration
- Separate service management

### Podman with Quadlet (Recommended for Production)

**Pros**:
- **Rootless by default** - Better security
- **Native systemd integration** - Automatic startup, logging, resource control
- **Declarative configuration** - Quadlet `.container` files
- **Drop-in Docker replacement** - Compatible with Docker images
- **Better resource isolation** - cgroups v2 support
- **Auto-updates** - Can be configured with systemd timers

**Cons**:
- Requires systemd (Linux only)
- Slightly different configuration syntax
- Less familiar to Docker-only users

### When to Use Each

| Scenario | Recommended |
|----------|-------------|
| Production deployments | **Podman + Quadlet** |
| Development environments | Either (preference) |
| CI/CD pipelines | Docker (wider support) |
| Rootless containers | **Podman** |
| Windows/macOS | Docker |
| systemd integration | **Podman + Quadlet** |

---

## Podman Quadlet Setup

For Podman installation and Quadlet configuration details, see the dedicated **[Podman Deployment Guide](./DEPLOY_PODMAN.md)**.

---

## Environment-Specific Deployment Instructions

This section provides environment-specific deployment instructions. Detailed step-by-step procedures are available in dedicated guides:

- **[Docker Compose Deployment](./DEPLOY_DOCKER.md)** - Complete Docker Compose deployment procedures for all environments
- **[Podman Quadlet Deployment](./DEPLOY_PODMAN.md)** - Complete Podman systemd deployment procedures for all environments

Both guides include:
- Prerequisites and authentication
- Environment-specific configuration
- Deployment steps and validation
- Updating deployments
- Rollback procedures
- Monitoring and maintenance
- Best practices

### Quick Reference

#### Test Environment

| Property | Value |
|----------|-------|
| **Purpose** | QA validation and integration testing |
| **Port** | 8001 |
| **Image Tag** | `test` |
| **Branch** | `test` |
| **Configuration** | Debug logging, verbose errors |

**Deployment**:
- [Docker Compose Instructions](./DEPLOY_DOCKER.md#test-environment)
- [Podman Quadlet Instructions](./DEPLOY_PODMAN.md#test-environment)

#### Staging Environment

| Property | Value |
|----------|-------|
| **Purpose** | Pre-production environment mirroring production |
| **Port** | 8002 |
| **Image Tag** | `staging` |
| **Branch** | `staging` |
| **Configuration** | Production-like, moderate logging |

**Deployment**:
- [Docker Compose Instructions](./DEPLOY_DOCKER.md#staging-environment)
- [Podman Quadlet Instructions](./DEPLOY_PODMAN.md#staging-environment)

#### Production Environment

| Property | Value |
|----------|-------|
| **Purpose** | Production deployment serving end users |
| **Port** | 8092 |
| **Image Tag** | `{version}` (e.g., `0.6.1`) |
| **Branch** | `main` |
| **Configuration** | Minimal logging, production security |

**Important**: Always pin specific versions in production (e.g., `0.6.1`), never use `latest` or `production` tags.

**Deployment**:
- [Docker Compose Instructions](./DEPLOY_DOCKER.md#production-environment)
- [Podman Quadlet Instructions](./DEPLOY_PODMAN.md#production-environment)

---

## Promotion Workflows

### Complete Promotion Pipeline

```bash
# 1. Feature Development
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# Make changes with conventional commits
git add .
git commit -m "feat: add new API endpoint"
git push origin feature/my-feature

# Create PR to dev branch
# After review and approval, merge to dev

# 2. Promote to Test
git checkout test
git pull origin test
git merge dev
git push origin test
# ✅ Automatic build triggered → creates test images

# 3. Test in Test Environment
# Visit test environment and run integration tests
# URL: http://test-server:8001/docs

# 4. Promote to Staging
git checkout staging
git pull origin staging
git merge test
git push origin staging
# ✅ Automatic build triggered → creates staging images

# 5. Validate in Staging
# Visit staging environment and run acceptance tests
# URL: http://staging-server:8002/docs

# 6. Promote to Production
git checkout main
git pull origin main
git merge staging
git push origin main
# ✅ Semantic-release triggered → creates production images, tags, changelog

# 7. Deploy to Production Server
ssh production-server
cd /opt/swedeb-api

# Check new version from GitHub releases
NEW_VERSION=$(curl -s https://api.github.com/repos/humlab-swedeb/swedeb-api/releases/latest | grep '"tag_name"' | sed 's/.*"v\(.*\)".*/\1/')

# Update to new version
sed -i "s/SWEDEB_IMAGE_TAG=.*/SWEDEB_IMAGE_TAG=${NEW_VERSION}/" .env
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d

# 8. Verify Production Deployment
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=100
curl https://your-domain.com/docs
```

### Hotfix Workflow

For urgent production fixes:

```bash
# Option 1: Fast-track through pipeline (RECOMMENDED)
git checkout dev
git checkout -b hotfix/critical-fix

# Make fix with conventional commit
git commit -m "fix: resolve critical security issue"
git push origin hotfix/critical-fix

# Fast-track PRs:
# 1. PR hotfix → dev → merge
# 2. PR dev → test → merge → test in test environment
# 3. PR test → staging → merge → validate in staging
# 4. PR staging → main → merge → deploys to production

# Backport to all branches
git checkout test && git cherry-pick <commit-hash> && git push
git checkout staging && git cherry-pick <commit-hash> && git push
```

```bash
# Option 2: Direct to main (EMERGENCY ONLY)
git checkout main
git checkout -b hotfix/emergency

# Make fix
git commit -m "fix: critical production issue"
git push origin hotfix/emergency

# Create PR to main
# After merge, semantic-release creates new version

# Backport to all branches
git checkout staging && git cherry-pick <commit-hash> && git push
git checkout test && git cherry-pick <commit-hash> && git push
git checkout dev && git cherry-pick <commit-hash> && git push
```

## Rollback Procedures

### Docker Compose Rollback

#### Test Environment Rollback

```bash
cd /opt/swedeb-api-test

# Option 1: Rollback to specific test version
docker compose -f compose.test.yml down
sed -i 's/SWEDEB_IMAGE_TAG=test/SWEDEB_IMAGE_TAG=0.6.0-test/' .env
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d

# Option 2: Re-pull previous test image (if still tagged as 'test')
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d
```

### Staging Environment Rollback

```bash
cd /opt/swedeb-api-staging

# Rollback to specific staging version
docker compose -f compose.staging.yml down
sed -i 's/SWEDEB_IMAGE_TAG=staging/SWEDEB_IMAGE_TAG=0.6.0-staging/' .env
docker compose -f compose.staging.yml pull
docker compose -f compose.staging.yml up -d
```

### Production Environment Rollback

```bash
cd /opt/swedeb-api

# Quick rollback to previous version
docker compose -f compose.production.yml down

# Update to previous version
sed -i 's/SWEDEB_IMAGE_TAG=0.6.1/SWEDEB_IMAGE_TAG=0.6.0/' .env
# Or edit .env manually to set: SWEDEB_IMAGE_TAG=0.6.0

# Pull and restart
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d

# Verify rollback
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=50
```

### Emergency Rollback (Re-tag Image)

If you need to rollback but also want to maintain the `production` tag:

```bash
# Re-tag old version as production
docker pull ghcr.io/humlab-swedeb/swedeb-api:0.6.0
docker tag ghcr.io/humlab-swedeb/swedeb-api:0.6.0 ghcr.io/humlab-swedeb/swedeb-api:production

# Push to registry (requires appropriate permissions)
docker push ghcr.io/humlab-swedeb/swedeb-api:production

# Redeploy
cd /opt/swedeb-api
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d
```

### Git Rollback (Code Level)

If you need to revert code changes:

```bash
# Revert last commit on main
git checkout main
git revert HEAD
git push origin main
# This will trigger a new release

# Or reset to specific commit (use with caution)
git reset --hard <commit-hash>
git push origin main --force
```

---

### Podman Quadlet Rollback

#### Test/Staging Rollback

```bash
# Stop service
systemctl --user stop swedeb-api-test.service

# Pull specific older version
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.0-test

# Edit Quadlet file to pin version
nano ~/.config/containers/systemd/swedeb-api-test.container
# Change: Image=ghcr.io/humlab-swedeb/swedeb-api:test
# To:     Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.0-test

# Reload and restart
systemctl --user daemon-reload
systemctl --user start swedeb-api-test.service

# Verify
systemctl --user status swedeb-api-test.service
podman inspect swedeb-api-test | grep Image
```

#### Production Rollback

```bash
# Quick rollback to previous version
systemctl --user stop swedeb-api-production.service

# Edit Quadlet file
nano ~/.config/containers/systemd/swedeb-api-production.container
# Change: Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.1
# To:     Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.0

# Pull old version
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.0

# Reload and restart
systemctl --user daemon-reload
systemctl --user start swedeb-api-production.service

# Verify rollback
systemctl --user status swedeb-api-production.service
journalctl --user -u swedeb-api-production.service --since "5 minutes ago"
podman ps
```

#### Emergency Rollback (Keep Running)

```bash
# Create new container with old version
podman run -d \
  --name swedeb-api-production-rollback \
  -p 8092:8000 \
  -v /data/swedeb/v1.4.1:/data/swedeb:Z,ro \
  -v /data/swedeb/metadata/riksprot_metadata.v1.1.3.db:/data/metadata/riksprot_metadata.v1.1.3.db:Z,ro \
  -e ENVIRONMENT=production \
  ghcr.io/humlab-swedeb/swedeb-api:0.6.0

# Stop systemd service
systemctl --user stop swedeb-api-production.service

# Update Quadlet to match emergency container
# Then reload systemd
systemctl --user daemon-reload
systemctl --user start swedeb-api-production.service

# Remove emergency container
podman stop swedeb-api-production-rollback
podman rm swedeb-api-production-rollback
```

## Monitoring & Maintenance

### Docker Compose Monitoring

#### Health Checks

```bash
# Check container status
docker compose -f compose.production.yml ps

# Check container health (if health check configured)
docker inspect --format='{{.State.Health.Status}}' swedeb-api

# View recent logs
docker compose -f compose.production.yml logs --tail=100

# Follow logs in real-time
docker compose -f compose.production.yml logs -f

# Check specific service logs
docker compose -f compose.production.yml logs -f swedeb_api
```

### Application Health

```bash
# Check API endpoints
curl http://localhost:8092/docs
curl http://localhost:8092/health  # If health endpoint exists

# Check API version
curl http://localhost:8092/version  # If version endpoint exists

# Test specific endpoint
curl http://localhost:8092/api/v1/your-endpoint
```

### Resource Monitoring

```bash
# Check Docker resource usage
docker stats

# Check disk space
df -h
docker system df

# Check container resource limits
docker inspect swedeb-api | grep -A 10 "Memory"

# View detailed container stats
docker stats swedeb-api --no-stream
```

### Image Management

```bash
# Check running version
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

# List available local images
docker images ghcr.io/humlab-swedeb/swedeb-api

# Remove old unused images
docker image prune -a

# Check image layers and size
docker history ghcr.io/humlab-swedeb/swedeb-api:0.6.1
```

### Log Management

```bash
# Configure log rotation in docker daemon
# Edit /etc/docker/daemon.json:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart docker after changes
sudo systemctl restart docker

# Or use logrotate for compose logs
# Create /etc/logrotate.d/docker-compose:
/opt/swedeb-api/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

### Backup Procedures

```bash
# Backup configuration
tar -czf swedeb-config-$(date +%Y%m%d).tar.gz \
  .env \
  compose.production.yml \
  /path/to/custom/config.yml

# Backup to remote location
scp swedeb-config-*.tar.gz backup-server:/backups/

# Data backup (corpus data - typically separate backup strategy)
# Corpus data is large and typically backed up separately
# rsync -av /data/swedeb/ backup-server:/data-backups/swedeb/
```

### Updates

```bash
# Update to latest version (production)
cd /opt/swedeb-api

# Check for new releases
curl -s https://api.github.com/repos/humlab-swedeb/swedeb-api/releases/latest | grep tag_name

# Update .env with new version
# Edit SWEDEB_IMAGE_TAG=0.6.2

# Pull and update
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d

# Verify update
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=50
```

---

### Podman Quadlet Monitoring

#### Health Checks

```bash
# Check service status
systemctl --user status swedeb-api-production.service

# Check container status
podman ps
podman inspect swedeb-api-production

# Health check status (if configured in Quadlet)
podman healthcheck run swedeb-api-production
```

#### Logs

```bash
# View logs via journald (recommended)
journalctl --user -u swedeb-api-production.service

# Recent logs
journalctl --user -u swedeb-api-production.service --since "1 hour ago"

# Follow logs
journalctl --user -u swedeb-api-production.service -f

# Filter by priority
journalctl --user -u swedeb-api-production.service -p err

# Export logs
journalctl --user -u swedeb-api-production.service --since "2024-01-01" > production-logs.txt

# Or view Podman logs directly
podman logs swedeb-api-production
podman logs -f --since 1h swedeb-api-production
```

#### Resource Monitoring

```bash
# Real-time stats
podman stats swedeb-api-production

# All containers
podman stats

# Resource usage details
podman inspect swedeb-api-production | jq '.[0].HostConfig | {Memory, MemorySwap, CpuQuota}'

# Check systemd resource control
systemctl --user show swedeb-api-production.service | grep -E "Memory|CPU"
```

#### Application Health

```bash
# Check API endpoints
curl http://localhost:8092/docs
curl http://localhost:8092/health

# Test specific endpoint
curl http://localhost:8092/api/v1/your-endpoint

# Using podman exec
podman exec swedeb-api-production curl -f http://localhost:8000/health
```

#### Image Management

```bash
# List images
podman images ghcr.io/humlab-swedeb/swedeb-api

# Check image details
podman inspect ghcr.io/humlab-swedeb/swedeb-api:0.6.1

# Clean up old images
podman image prune -a

# Remove specific image
podman rmi ghcr.io/humlab-swedeb/swedeb-api:0.6.0
```

#### Log Management (journald)

```bash
# journald automatically manages logs, but you can configure retention

# Check journal size
journalctl --disk-usage

# Configure retention
sudo mkdir -p /etc/systemd/journald.conf.d/
sudo tee /etc/systemd/journald.conf.d/retention.conf <<EOF
[Journal]
SystemMaxUse=1G
SystemMaxFileSize=100M
MaxRetentionSec=7day
EOF

# Restart journald
sudo systemctl restart systemd-journald

# Vacuum old logs
journalctl --vacuum-time=7d
journalctl --vacuum-size=500M
```

#### Automated Monitoring with systemd

Create a monitoring service that checks health:

`~/.config/systemd/user/swedeb-api-healthcheck.service`:
```ini
[Unit]
Description=Swedeb API Health Check
After=swedeb-api-production.service

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -f http://localhost:8092/health
```

`~/.config/systemd/user/swedeb-api-healthcheck.timer`:
```ini
[Unit]
Description=Run Swedeb API Health Check Every 5 Minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
AccuracySec=1s

[Install]
WantedBy=timers.target
```

Enable:
```bash
systemctl --user daemon-reload
systemctl --user enable --now swedeb-api-healthcheck.timer
systemctl --user list-timers
```

#### Backup Procedures

```bash
# Backup Quadlet configuration
tar -czf swedeb-quadlet-backup-$(date +%Y%m%d).tar.gz \
  ~/.config/containers/systemd/swedeb-api-*.container \
  ~/.config/containers/systemd/swedeb-api-*.env

# Backup container volume data (if any local volumes)
podman volume ls
podman volume export <volume-name> > volume-backup.tar

# Backup to remote
scp swedeb-quadlet-backup-*.tar.gz backup-server:/backups/
```

#### Updates

```bash
# Update to new version
cd ~/.config/containers/systemd

# Edit Quadlet file
nano swedeb-api-production.container
# Update Image= line with new version

# Pull new image
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.2

# Reload and restart
systemctl --user daemon-reload
systemctl --user restart swedeb-api-production.service

# Verify update
systemctl --user status swedeb-api-production.service
podman ps
journalctl --user -u swedeb-api-production.service --since "2 minutes ago"
```

#### Automated Updates (Optional)

Create `~/.config/systemd/user/swedeb-api-update.service`:
```ini
[Unit]
Description=Update Swedeb API Production
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.1
ExecStartPost=/usr/bin/systemctl --user restart swedeb-api-production.service

# Optional: Send notification on failure
OnFailure=status-email@%n.service
```

Create timer `~/.config/systemd/user/swedeb-api-update.timer`:
```ini
[Unit]
Description=Check for Swedeb API updates

[Timer]
# Check daily at 3 AM
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
systemctl --user daemon-reload
systemctl --user enable --now swedeb-api-update.timer
```


## Troubleshooting

For troubleshooting common deployment issues, see the dedicated [Troubleshooting Guide](./TROUBLESHOOTING.md).

Common topics covered:
- **Docker-specific issues**: Image pull errors, data mounts, port conflicts, container startup
- **Podman-specific issues**: Rootless port binding, SELinux permissions, systemd service management
- **Debug commands**: Comprehensive debugging steps for both Docker and Podman
- **Performance tuning**: Optimization tips and resource limit configuration

## Best Practices

### Development
1. **Use conventional commits** - Ensures proper semantic versioning
2. **No auto-builds on dev** - Keep dev as stable integration point
3. **Test thoroughly** - Use test environment before promoting
4. **Code review** - All PRs require review before merge

### Deployment
1. **Pin versions in production** - Use specific tags (e.g., `0.6.1`) not `latest`
2. **Auto-update for test/staging** - Use environment tags (`test`, `staging`)
3. **Validate before promotion** - Test in each environment before promoting
4. **Document changes** - Update changelog and release notes
5. **Monitor after deployment** - Watch logs and metrics

### Operations

#### Docker Compose
1. **Regular backups** - Backup configuration files
2. **Log rotation** - Configure log management
3. **Resource monitoring** - Track CPU, memory, disk usage
4. **Security updates** - Keep Docker and base images updated
5. **Disaster recovery plan** - Document rollback procedures

#### Podman Quadlet
1. **Use rootless mode** - Better security isolation
2. **Enable lingering** - Ensure services survive logout (`loginctl enable-linger`)
3. **Pin versions in Quadlet** - Explicitly set image tags
4. **Use SELinux** - Add `:Z` to volume mounts for proper labeling
5. **Monitor via journald** - Centralized logging with `journalctl`
6. **Test Quadlet changes** - Validate with `systemctl --user daemon-reload`
7. **Auto-update carefully** - Use systemd timers with notification on failure
8. **Resource limits** - Set Memory, CPU limits in Quadlet files
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
- `FRONTEND_VERSION_TAG`: Frontend version to include (default: `latest`)
- `GITHUB_REPOSITORY`: Org/repo name

**What it does**:
1. Validates environment parameter (test/staging/production)
2. Authenticates to GHCR (uses `CWB_REGISTRY_TOKEN` if available)
3. Builds multi-stage Docker image with frontend and CWB tools
4. Tags image according to environment:
   - **Test**: `{version}-test`, `test`, `test-latest`
   - **Staging**: `{version}-staging`, `staging`
   - **Production**: `{version}`, `{major}`, `{minor}`, `latest`, `production`
5. Pushes all tags to registry

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
4. Builds Python wheel package using Poetry
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
├── Dockerfile                         # Multi-stage application build
├── entrypoint.sh                      # Container startup script
├── compose.test.yml                   # Test environment compose
├── compose.staging.yml                # Staging environment compose
└── compose.production.yml             # Production environment compose
```

## Deployment Checklist

### Pre-Deployment
- [ ] Server meets minimum requirements (Docker 20.10+, 4GB+ RAM, 10GB+ disk)
- [ ] Data directory structure exists (`/data/swedeb/`)
- [ ] Proper permissions set on data directories (user 1021:1021)
- [ ] Docker and Docker Compose installed and running
- [ ] Network connectivity to GHCR verified
- [ ] Authentication to GHCR configured
- [ ] Backup of existing configuration (if updating)

### Test Deployment
- [ ] Test environment configured in `.env`
- [ ] Docker login successful
- [ ] Image pull successful (`:test` tag)
- [ ] Container starts without errors
- [ ] Application responds to requests
- [ ] Integration tests pass
- [ ] Logs show no errors

### Staging Deployment
- [ ] Staging environment configured in `.env`
- [ ] Image pull successful (`:staging` tag)
- [ ] Container starts without errors
- [ ] All endpoints accessible
- [ ] Acceptance tests pass
- [ ] Performance meets requirements
- [ ] Security validation completed

### Production Deployment
- [ ] Specific version tag pinned in config (not `latest`)
- [ ] Image pull successful (specific version)
- [ ] Container starts without errors
- [ ] Reverse proxy configured (if applicable)
- [ ] SSL certificates valid
- [ ] DNS configured correctly
- [ ] Health checks passing
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

*Last updated: Following 4-branch workflow implementation with Podman Quadlet support (dev → test → staging → main)*

