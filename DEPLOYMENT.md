# 🚀 Comprehensive Deployment Guide

This document provides complete instructions for deploying the Swedeb API system across all environments (test, staging, production) using the automated CI/CD pipeline and Docker containers.

## 📋 Table of Contents

- [Branch Strategy & Workflows](#branch-strategy--workflows)
- [Architecture Overview](#architecture-overview)
- [Image Tagging Strategy](#image-tagging-strategy)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment Prerequisites](#deployment-prerequisites)
- [Test Environment Deployment](#test-environment-deployment)
- [Staging Environment Deployment](#staging-environment-deployment)
- [Production Environment Deployment](#production-environment-deployment)
- [Promotion Workflows](#promotion-workflows)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)
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
├── v1.4.1/                          # Corpus version
│   ├── registry/                    # CWB registry
│   ├── dtm/                        # Document-term matrices
│   ├── tagged_frames/              # Processed corpus files
│   └── ...
└── metadata/
    ├── v1.1.3/                     # Metadata version
    └── riksprot_metadata.v1.1.3.db # Database file
```

### Authentication Setup

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# Or using Personal Access Token (PAT)
docker login ghcr.io -u your-username
# Enter PAT when prompted
```

**Note**: For cross-organization access to `ghcr.io/humlab/cwb-container`, the `CWB_REGISTRY_TOKEN` secret must be configured in GitHub Actions.

## Test Environment Deployment

### Purpose
Test environment for QA validation and integration testing before promoting to staging.

### Step 1: Prepare Test Server

```bash
# Create deployment directory
sudo mkdir -p /opt/swedeb-api-test
cd /opt/swedeb-api-test

# Download compose configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/test/docker/compose.test.yml
```

### Step 2: Configure Environment

Create or edit `.env` file:

```bash
# Test Environment Configuration
SWEDEB_ENVIRONMENT=test
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=test                      # Use 'test' tag for auto-updates
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=8001                      # Test environment port

# Data Configuration
SWEDEB_DATA_FOLDER=/data/swedeb/v1.4.1
SWEDEB_METADATA_FILENAME=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db
METADATA_VERSION=v1.1.3
CORPUS_VERSION=v1.4.1

# Container Configuration
SWEDEB_CONTAINER_NAME=swedeb-api-test
```

### Step 3: Verify Data

```bash
# Ensure corpus data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/riksprot_metadata.v1.1.3.db

# Verify permissions
sudo chown -R 1021:1021 /data/swedeb/
```

### Step 4: Deploy Test

```bash
# Pull latest test image
docker compose -f compose.test.yml pull

# Start services
docker compose -f compose.test.yml up -d

# Verify deployment
docker compose -f compose.test.yml ps
docker compose -f compose.test.yml logs -f
```

### Step 5: Validate

```bash
# Check API health
curl http://localhost:8001/docs
curl http://localhost:8001/health

# Run integration tests
# ... your test commands ...
```

## Staging Environment Deployment

### Purpose
Pre-production environment mirroring production configuration for final validation.

### Step 1: Prepare Staging Server

```bash
# Create deployment directory
sudo mkdir -p /opt/swedeb-api-staging
cd /opt/swedeb-api-staging

# Download compose configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/staging/docker/compose.staging.yml
```

### Step 2: Configure Environment

Create or edit `.env` file:

```bash
# Staging Environment Configuration
SWEDEB_ENVIRONMENT=staging
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=staging                   # Use 'staging' tag for auto-updates
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=8002                      # Staging environment port

# Data Configuration (typically same as production)
SWEDEB_DATA_FOLDER=/data/swedeb/v1.4.1
SWEDEB_METADATA_FILENAME=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db
METADATA_VERSION=v1.1.3
CORPUS_VERSION=v1.4.1

# Container Configuration
SWEDEB_CONTAINER_NAME=swedeb-api-staging
```

### Step 3: Deploy Staging

```bash
# Pull latest staging image
docker compose -f compose.staging.yml pull

# Start services
docker compose -f compose.staging.yml up -d

# Verify deployment
docker compose -f compose.staging.yml ps
docker compose -f compose.staging.yml logs -f
```

### Step 4: Validate

```bash
# Acceptance testing
curl http://localhost:8002/docs

# Performance testing
# ... load testing commands ...
```

## Production Environment Deployment

### Purpose
Production deployment serving end users.

### Step 1: Prepare Production Server

```bash
# Create deployment directory
sudo mkdir -p /opt/swedeb-api
cd /opt/swedeb-api

# Download compose configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/main/docker/compose.production.yml
```

### Step 2: Configure Environment

Create or edit `.env` file:

```bash
# Production Environment Configuration
SWEDEB_ENVIRONMENT=production
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=0.6.1                     # Pin specific version (RECOMMENDED)
# SWEDEB_IMAGE_TAG=production              # Or use 'production' tag for auto-updates
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=443                       # Production port (or 80 for HTTP)

# Data Configuration  
SWEDEB_CONFIG_PATH=/app/config/config.yml
SWEDEB_DATA_FOLDER=/data/swedeb/v1.4.1
SWEDEB_METADATA_FILENAME=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db
METADATA_VERSION=v1.1.3
CORPUS_VERSION=v1.4.1

# Container Configuration
SWEDEB_CONTAINER_NAME=swedeb-api
```

**Best Practice**: Pin specific versions in production (e.g., `0.6.1`) rather than using `latest` or `production` tags.

### Step 3: Verify Data Availability

```bash
# Ensure corpus data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/riksprot_metadata.v1.1.3.db

# Verify permissions
sudo chown -R 1021:1021 /data/swedeb/
```

### Step 4: Deploy Application

```bash
# Pull production image
docker compose -f compose.production.yml pull

# Start services
docker compose -f compose.production.yml up -d

# Verify deployment
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs -f
```

### Step 5: Configure Reverse Proxy

For production, configure nginx or similar web server:

```nginx
# /etc/nginx/sites-available/swedeb-api
server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8092;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and reload nginx:
```bash
sudo ln -s /etc/nginx/sites-available/swedeb-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Deployment Workflows

### Triggering Builds

**Automatic (push to branch):**
```bash
# Test environment
git push origin test

# Staging environment  
git push origin staging

# Production environment (triggers semantic-release)
git push origin main
```

**Manual (via GitHub Actions UI):**
```bash
# Using GitHub CLI
gh workflow run test.yml -f version=0.6.1
gh workflow run staging.yml -f version=0.6.1

# Or via GitHub Web UI:
# Actions → Deploy to Test/Staging → Run workflow → Enter version
```

### Updating Deployments

**Test/Staging (auto-update tags):**
```bash
cd /opt/swedeb-api-test  # or staging
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d
```

**Production (pinned version):**
```bash
cd /opt/swedeb-api

# Option 1: Update .env with new version
sed -i 's/SWEDEB_IMAGE_TAG=0.6.0/SWEDEB_IMAGE_TAG=0.6.1/' .env

# Option 2: Edit compose file directly
sed -i 's/:0.6.0/:0.6.1/' compose.production.yml

# Pull and deploy
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d
```

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

### Test Environment Rollback

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

## Monitoring & Maintenance

### Health Checks

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

## Troubleshooting

### Common Issues

#### 1. Image Pull Errors

```bash
# Error: pull access denied
# Solution: Ensure proper authentication
docker login ghcr.io -u username
# Enter PAT when prompted

# Verify login
docker pull ghcr.io/humlab-swedeb/swedeb-api:latest

# Check if image exists
docker manifest inspect ghcr.io/humlab-swedeb/swedeb-api:0.6.1
```

#### 2. Cross-Organization Access Issues

```bash
# Error: Failed to pull ghcr.io/humlab/cwb-container
# Solution: Ensure CWB_REGISTRY_TOKEN is configured in GitHub Actions

# For local builds, login with appropriate PAT:
echo $CWB_TOKEN | docker login ghcr.io -u username --password-stdin
```

#### 3. Data Mount Issues

```bash
# Error: Permission denied or file not found
# Solution: Check data paths and permissions

# Verify data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/riksprot_metadata.v1.1.3.db

# Fix permissions
sudo chown -R 1021:1021 /data/swedeb/

# Check mount paths in compose file match actual data location
docker compose config | grep volumes
```

#### 4. Port Conflicts

```bash
# Error: Port already in use
# Solution: Check for conflicting services

# Find process using port
netstat -tulpn | grep :8092
lsof -i :8092

# Check Docker containers
docker ps --filter "publish=8092"

# Change port in .env
# Edit: SWEDEB_HOST_PORT=8093
```

#### 5. Container Won't Start

```bash
# Check container logs
docker compose -f compose.production.yml logs swedeb_api

# Check resource usage
docker stats
df -h
free -m

# Verify configuration
docker compose -f compose.production.yml config

# Check for errors in entrypoint
docker compose -f compose.production.yml logs | grep -i error

# Try running interactively
docker compose -f compose.production.yml run --rm swedeb_api /bin/bash
```

#### 6. Application Not Responding

```bash
# Check if container is running
docker compose -f compose.production.yml ps

# Check internal connectivity
docker compose -f compose.production.yml exec swedeb_api curl localhost:8092/docs

# Check configuration loading
docker compose -f compose.production.yml exec swedeb_api cat /app/config/config.yml

# Check environment variables
docker compose -f compose.production.yml exec swedeb_api env | grep SWEDEB

# Check if data is mounted
docker compose -f compose.production.yml exec swedeb_api ls -la /data/
```

#### 7. Out of Memory

```bash
# Check memory usage
docker stats swedeb-api

# Increase container memory limits
# Add to compose file:
services:
  swedeb_api:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
        reservations:
          memory: 4G
          cpus: '2'

# Check host memory
free -m
```

### Debug Commands

```bash
# Enter container for debugging
docker compose -f compose.production.yml exec swedeb_api /bin/bash

# Check Python environment
docker compose -f compose.production.yml exec swedeb_api python --version
docker compose -f compose.production.yml exec swedeb_api pip list

# Test configuration loading
docker compose -f compose.production.yml exec swedeb_api python -c \
  "from api_swedeb.core.configuration import ConfigStore; print(ConfigStore.default())"

# Check file permissions
docker compose -f compose.production.yml exec swedeb_api ls -la /app/
docker compose -f compose.production.yml exec swedeb_api ls -la /data/

# Check network connectivity
docker compose -f compose.production.yml exec swedeb_api ping -c 3 ghcr.io
docker compose -f compose.production.yml exec swedeb_api curl -I https://ghcr.io

# Test CWB tools
docker compose -f compose.production.yml exec swedeb_api cwb-describe-corpus
```

### Performance Tuning

```bash
# Optimize Docker daemon
# Edit /etc/docker/daemon.json:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  }
}

# Increase resource limits in compose file
services:
  swedeb_api:
    deploy:
      resources:
        limits:
          memory: 16G
          cpus: '8'
    ulimits:
      nofile:
        soft: 65536
        hard: 65536

# Monitor performance
docker stats --no-stream
docker compose -f compose.production.yml top
```

## Frontend Versioning

The API Docker build includes the frontend as a base image:

```dockerfile
ARG FRONTEND_VERSION=latest
FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
```

### Pin Frontend Version

For production builds with a specific frontend version:

```bash
# Modify .releaserc.yml or staging.yml workflow to set FRONTEND_VERSION_TAG
export FRONTEND_VERSION_TAG=0.10.0

# Or build locally with specific frontend
cd docker
docker build --build-arg FRONTEND_VERSION=0.10.0 -t custom-build .
```

### Frontend Compatibility

Ensure compatible frontend and backend versions:

| Backend Version | Compatible Frontend | Notes |
|----------------|---------------------|-------|
| 0.6.x | 0.10.x | Current stable |
| 0.5.x | 0.9.x | Legacy |

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
1. **Regular backups** - Backup configuration files
2. **Log rotation** - Configure log management
3. **Resource monitoring** - Track CPU, memory, disk usage
4. **Security updates** - Keep Docker and base images updated
5. **Disaster recovery plan** - Document rollback procedures

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
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Semantic Release](https://semantic-release.gitbook.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

*Last updated: Following 4-branch workflow implementation (dev → test → staging → main)*

