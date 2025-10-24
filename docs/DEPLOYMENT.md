# 🚀 Comprehensive Deployment Guide

This document provides complete instructions for deploying the Swedeb API system across all environments (test, staging, production) using the automated CI/CD pipeline and Docker containers.

## 📋 Table of Contents

- [Branch Strategy & Workflows](#branch-strategy--workflows)
- [Architecture Overview](#architecture-overview)
- [Image Tagging Strategy](#image-tagging-strategy)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment Prerequisites](#deployment-prerequisites)
- [Container Runtime Options](#container-runtime-options)
- [Test Environment Deployment](#test-environment-deployment)
- [Staging Environment Deployment](#staging-environment-deployment)
- [Production Environment Deployment](#production-environment-deployment)
- [Promotion Workflows](#promotion-workflows)
- [Rollback Procedures](#rollback-procedures)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Frontend Versioning](#frontend-versioning)
- [Troubleshooting](#troubleshooting)
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

Quadlet is Podman's systemd integration that converts `.container` files into systemd services. This provides automatic startup, dependency management, and native logging.

### Installation

```bash
# Install Podman (RHEL/Fedora/CentOS)
sudo dnf install podman

# Install Podman (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install podman

# Verify installation
podman --version
podman info

# Enable user lingering (keeps user services running after logout)
sudo loginctl enable-linger $USER
```

### Quadlet File Locations

Quadlet files can be placed in different locations depending on scope:

```bash
# System-wide (requires root)
/etc/containers/systemd/

# User-specific (rootless, recommended)
~/.config/containers/systemd/

# Runtime directory
${XDG_RUNTIME_DIR}/containers/systemd/
```

For this guide, we'll use **user-specific rootless deployments**.

### Quadlet File Format

Quadlet uses `.container` files that look similar to systemd units:

```ini
# Example: swedeb-api-production.container
[Unit]
Description=Swedeb API Production Container
After=network-online.target
Wants=network-online.target

[Container]
Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.1
ContainerName=swedeb-api-production
PublishPort=8092:8000
Volume=/data/swedeb/v1.4.1:/data/swedeb:Z
Volume=/data/swedeb/metadata:/data/metadata:Z
Environment=ENVIRONMENT=production
Environment=LOG_LEVEL=INFO

[Service]
Restart=always
TimeoutStartSec=900

[Install]
WantedBy=default.target
```

**Note**: For cross-organization access to `ghcr.io/humlab/cwb-container`, the `CWB_REGISTRY_TOKEN` secret must be configured in GitHub Actions.

## Test Environment Deployment

### Purpose
Test environment for QA validation and integration testing before promoting to staging.

---

### Docker Compose Method

#### Step 1: Prepare Test Server

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

#### Step 5: Validate

```bash
# Check API health
curl http://localhost:8001/docs
curl http://localhost:8001/health

# Run integration tests
# ... your test commands ...
```

---

### Podman Quadlet Method

#### Step 1: Create Quadlet Directory

```bash
# Create user systemd directory
mkdir -p ~/.config/containers/systemd
cd ~/.config/containers/systemd
```

#### Step 2: Create Container File

Create `swedeb-api-test.container`:

```ini
[Unit]
Description=Swedeb API Test Environment
After=network-online.target
Wants=network-online.target

[Container]
Image=ghcr.io/humlab-swedeb/swedeb-api:test
ContainerName=swedeb-api-test
PublishPort=8001:8000

# Volume mounts (use :Z for SELinux compatibility)
Volume=/data/swedeb/v1.4.1:/data/swedeb:Z
Volume=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db:/data/metadata/riksprot_metadata.v1.1.3.db:Z,ro

# Environment variables
Environment=ENVIRONMENT=test
Environment=LOG_LEVEL=DEBUG
Environment=METADATA_VERSION=v1.1.3
Environment=CORPUS_VERSION=v1.4.1

# Health check (optional)
HealthCmd=/usr/bin/curl -f http://localhost:8000/health || exit 1
HealthInterval=30s
HealthTimeout=10s
HealthRetries=3
HealthStartPeriod=40s

[Service]
Restart=always
TimeoutStartSec=900
TimeoutStopSec=70

[Install]
WantedBy=default.target
```

#### Step 3: Verify Data Permissions

```bash
# Ensure corpus data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/riksprot_metadata.v1.1.3.db

# Verify permissions (important for rootless Podman)
# For rootless, ensure your user can read the data
chmod -R u+rX /data/swedeb/
```

#### Step 4: Reload systemd and Start Service

```bash
# Reload systemd to pick up the new Quadlet file
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable --now swedeb-api-test.service

# Check status
systemctl --user status swedeb-api-test.service

# View logs
journalctl --user -u swedeb-api-test.service -f
```

#### Step 5: Validate

```bash
# Check API health
curl http://localhost:8001/docs

# Check container status
podman ps

# Check logs
podman logs swedeb-api-test
# Or via journalctl:
journalctl --user -u swedeb-api-test.service --since "1 hour ago"
```

#### Step 6: Manage Service

```bash
# Stop service
systemctl --user stop swedeb-api-test.service

# Restart service
systemctl --user restart swedeb-api-test.service

# Update image and restart
podman pull ghcr.io/humlab-swedeb/swedeb-api:test
systemctl --user restart swedeb-api-test.service

# Disable service
systemctl --user disable swedeb-api-test.service
```

## Staging Environment Deployment

### Purpose
Pre-production environment mirroring production configuration for final validation.

---

### Docker Compose Method

#### Step 1: Prepare Staging Server

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

#### Step 4: Validate

```bash
# Acceptance testing
curl http://localhost:8002/docs

# Performance testing
# ... load testing commands ...
```

---

### Podman Quadlet Method

#### Step 1: Create Container File

Create `~/.config/containers/systemd/swedeb-api-staging.container`:

```ini
[Unit]
Description=Swedeb API Staging Environment
After=network-online.target
Wants=network-online.target

[Container]
Image=ghcr.io/humlab-swedeb/swedeb-api:staging
ContainerName=swedeb-api-staging
PublishPort=8002:8000

# Volume mounts
Volume=/data/swedeb/v1.4.1:/data/swedeb:Z
Volume=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db:/data/metadata/riksprot_metadata.v1.1.3.db:Z,ro

# Environment variables
Environment=ENVIRONMENT=staging
Environment=LOG_LEVEL=INFO
Environment=METADATA_VERSION=v1.1.3
Environment=CORPUS_VERSION=v1.4.1

# Resource limits (optional)
Memory=8G
MemorySwap=8G
CPUQuota=400%

# Health check
HealthCmd=/usr/bin/curl -f http://localhost:8000/health || exit 1
HealthInterval=30s
HealthTimeout=10s
HealthRetries=3

[Service]
Restart=always
TimeoutStartSec=900
TimeoutStopSec=70

[Install]
WantedBy=default.target
```

#### Step 2: Deploy

```bash
# Reload systemd
systemctl --user daemon-reload

# Enable and start
systemctl --user enable --now swedeb-api-staging.service

# Check status
systemctl --user status swedeb-api-staging.service

# View logs
journalctl --user -u swedeb-api-staging.service -f
```

#### Step 3: Validate

```bash
# Check API
curl http://localhost:8002/docs

# Monitor resource usage
podman stats swedeb-api-staging
```

## Production Environment Deployment

### Purpose
Production deployment serving end users.

---

### Docker Compose Method

#### Step 1: Prepare Production Server

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

---

### Podman Quadlet Method (Recommended for Production)

#### Step 1: Create Container File

Create `~/.config/containers/systemd/swedeb-api-production.container`:

```ini
[Unit]
Description=Swedeb API Production
After=network-online.target
Wants=network-online.target

[Container]
# Pin specific version for production (CRITICAL)
Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.1
ContainerName=swedeb-api-production
PublishPort=8092:8000

# Volume mounts
Volume=/data/swedeb/v1.4.1:/data/swedeb:Z,ro
Volume=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db:/data/metadata/riksprot_metadata.v1.1.3.db:Z,ro
Volume=/opt/swedeb-api/config/config.yml:/app/config/config.yml:Z,ro

# Environment variables
Environment=ENVIRONMENT=production
Environment=LOG_LEVEL=WARNING
Environment=METADATA_VERSION=v1.1.3
Environment=CORPUS_VERSION=v1.4.1

# Production resource limits
Memory=16G
MemorySwap=16G
CPUQuota=800%
PidsLimit=4096

# Security options
SecurityLabelDisable=false
ReadOnlyTmpfs=true
NoNewPrivileges=true

# Health check
HealthCmd=/usr/bin/curl -f http://localhost:8000/health || exit 1
HealthInterval=30s
HealthTimeout=10s
HealthRetries=3
HealthStartPeriod=60s

[Service]
Restart=always
RestartSec=10s
TimeoutStartSec=900
TimeoutStopSec=70

# Ensure service restarts on failure
StartLimitInterval=0

[Install]
WantedBy=default.target
```

#### Step 2: Create Environment File (Optional)

For easier version management, create `~/.config/containers/systemd/swedeb-api-production.env`:

```bash
# Production Configuration
ENVIRONMENT=production
LOG_LEVEL=WARNING
METADATA_VERSION=v1.1.3
CORPUS_VERSION=v1.4.1
```

Then reference it in the container file:
```ini
[Container]
EnvironmentFile=/home/username/.config/containers/systemd/swedeb-api-production.env
```

#### Step 3: Verify Data and Permissions

```bash
# Ensure data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/

# For rootless Podman, ensure user has read access
chmod -R u+rX /data/swedeb/

# Create config directory if needed
mkdir -p /opt/swedeb-api/config
```

#### Step 4: Deploy Production Service

```bash
# Reload systemd to discover new Quadlet
systemctl --user daemon-reload

# Enable service (auto-start on boot)
systemctl --user enable swedeb-api-production.service

# Start service
systemctl --user start swedeb-api-production.service

# Check status
systemctl --user status swedeb-api-production.service

# View logs
journalctl --user -u swedeb-api-production.service -f
```

#### Step 5: Configure Reverse Proxy

Same nginx configuration as Docker Compose method above.

#### Step 6: Production Monitoring

```bash
# Check service status
systemctl --user status swedeb-api-production.service

# View recent logs
journalctl --user -u swedeb-api-production.service --since "1 hour ago"

# Follow logs in real-time
journalctl --user -u swedeb-api-production.service -f

# Check resource usage
podman stats swedeb-api-production

# Inspect container
podman inspect swedeb-api-production
```

#### Step 7: Auto-Update Configuration (Optional)

Create a systemd timer to automatically check for and pull new images:

Create `~/.config/systemd/user/swedeb-api-update.service`:
```ini
[Unit]
Description=Update Swedeb API Production Image
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.1
ExecStartPost=/usr/bin/systemctl --user try-restart swedeb-api-production.service
```

Create `~/.config/systemd/user/swedeb-api-update.timer`:
```ini
[Unit]
Description=Check for Swedeb API updates daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer:
```bash
systemctl --user daemon-reload
systemctl --user enable --now swedeb-api-update.timer

# Check timer status
systemctl --user list-timers
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

#### Docker Compose

**Test/Staging (auto-update tags):**
```bash
cd /opt/swedeb-api-test  # or staging
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d
```

**Production (pinned version):**
```bash
cd /opt/swedeb-api

# Update .env with new version
sed -i 's/SWEDEB_IMAGE_TAG=0.6.0/SWEDEB_IMAGE_TAG=0.6.1/' .env

# Pull and deploy
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d
```

#### Podman Quadlet

**Test/Staging (auto-update tags):**
```bash
# Pull new image
podman pull ghcr.io/humlab-swedeb/swedeb-api:test

# Restart service (systemd will use new image)
systemctl --user restart swedeb-api-test.service

# Or for staging
podman pull ghcr.io/humlab-swedeb/swedeb-api:staging
systemctl --user restart swedeb-api-staging.service
```

**Production (pinned version):**
```bash
# Method 1: Update Quadlet file
cd ~/.config/containers/systemd

# Edit swedeb-api-production.container
# Change: Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.0
# To:     Image=ghcr.io/humlab-swedeb/swedeb-api:0.6.1

# Reload systemd and restart
systemctl --user daemon-reload
systemctl --user restart swedeb-api-production.service

# Method 2: Pull specific version and restart
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.1
# Update Quadlet file as above
systemctl --user daemon-reload
systemctl --user restart swedeb-api-production.service

# Verify new version
podman inspect swedeb-api-production | grep -A 5 "Image"
journalctl --user -u swedeb-api-production.service --since "5 minutes ago"
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

