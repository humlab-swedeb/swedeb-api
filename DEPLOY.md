# 🚀 Deployment Guide

This document provides step-by-step instructions for deploying the Swedeb API system to production or staging servers using the automated CI/CD pipeline and Docker images.

## 📋 Table of Contents

- [Overview](#overview)
- [CI/CD Implementation](#cicd-implementation)
- [Artifacts & Dependencies](#artifacts--dependencies)
- [Files Involved in CI/CD](#files-involved-in-cicd)
- [Deployment Prerequisites](#deployment-prerequisites)
- [Production Deployment](#production-deployment)
- [Staging Deployment](#staging-deployment)
- [Local Testing with Runlike](#local-testing-with-runlike)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

## 🔍 Overview

The Swedeb API system is deployed as a containerized application using Docker images built and published through GitHub Actions. The CI/CD pipeline automatically creates ready-to-use Docker images that can be pulled from GitHub Container Registry (GHCR) and deployed to any compatible Docker environment.

### System Architecture
```
┌───────────────────────────────────────────────────┐
│                 GitHub Actions                    │
│  ┌─────────────┐    ┌───────────────────────────┐ │
│  │   Commit    │──> │ Semantic Release Pipeline │ │
│  │  to main    │    └───────────────────────────┘ │
│  └─────────────┘                │                 │
└─────────────────────────────────┼─────────────────┘
                                  ▼
┌─────────────────────────────────────────────────┐
│           GitHub Container Registry             │
│    ghcr.io/humlab-swedeb/swedeb-api:latest      │
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

## 🔄 CI/CD Implementation

### Automatic Release Pipeline

The CI/CD pipeline is triggered on every push to the `main` branch and follows these stages:

#### 1. **Commit Analysis** 
- Analyzes commit messages using conventional commit format
- Determines version bump (major, minor, patch, or no release)

#### 2. **Asset Preparation**
- Updates version in `pyproject.toml` and `api_swedeb/__init__.py`
- Builds Python wheel package using Poetry
- Creates `dist/*.whl` artifacts

#### 3. **Docker Image Build**
- Uses multi-stage Dockerfile combining three base images:
  - **Frontend**: `ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION}`
  - **CWB Tools**: `ghcr.io/humlab/cwb-container:latest`
  - **Application**: Built from current repository

#### 4. **Image Publishing**
- Publishes to GitHub Container Registry (GHCR)
- Creates multiple tags: `latest`, `x.y.z`, `x.y`, `x`
- Available at: `ghcr.io/humlab-swedeb/swedeb-api`

#### 5. **Release Creation**
- Creates GitHub release with changelog
- Uploads Python wheel as release artifact
- Commits version updates back to repository

### Artifacts Produced

| Artifact Type | Location | Description |
|---------------|----------|-------------|
| **Docker Image** | `ghcr.io/humlab-swedeb/swedeb-api:latest` | Complete application container |
| **Python Wheel** | GitHub Releases | Installable Python package |
| **Release Notes** | GitHub Releases | Auto-generated changelog |
| **Version Tags** | Git Tags | Semantic version tags |

## 📁 Files Involved in CI/CD

### Core CI/CD Files
```
.github/
├── workflows/
│   └── release.yml                    # Main GitHub Actions workflow
└── scripts/
    ├── prepare-release-assets.sh      # Version sync & wheel build
    └── publish-docker.sh              # Docker build & push

.releaserc.yml                         # Semantic-release configuration
package.json                           # Node.js dependencies for semantic-release
pyproject.toml                         # Python project & dependencies
```

### Docker Files
```
docker/
├── Dockerfile                         # Multi-stage application build
├── entrypoint.sh                     # Container startup script
├── compose.yml                       # Development compose file
└── compose/
    ├── production/
    │   ├── compose.yml               # Production deployment
    │   └── .env                      # Production environment
    ├── staging/
    │   ├── compose.yml               # Staging deployment  
    │   └── .env                      # Staging environment
    └── riksdagsdebatter.se/
        ├── compose.yml               # Site-specific deployment
        └── .env                      # Site-specific environment
```

### Configuration Files
```
config/
└── config.yml                       # Application configuration template

docker/config/
└── config.yml                       # Docker-specific configuration
```

## 🛠️ Deployment Prerequisites

### Server Requirements
- **Docker Engine**: Version 20.10+ 
- **Docker Compose**: Version 2.0+
- **Minimum RAM**: 4GB (8GB+ recommended)
- **Disk Space**: 10GB+ for data and images
- **Network**: Internet access for pulling images

### Data Requirements
The application requires corpus data and metadata to be available on the host system:

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

# Or using Personal Access Token
docker login ghcr.io -u your-username -p your-pat
```

## 🚢 Production Deployment

### Step 1: Prepare Production Server

```bash
# Create deployment directory
sudo mkdir -p /opt/swedeb-api
cd /opt/swedeb-api

# Copy compose configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/main/docker/compose/production/compose.yml
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/main/docker/compose/production/.env
```

### Step 2: Configure Environment

Edit the production `.env` file:

```bash
# Production Environment Configuration
SWEDEB_ENVIRONMENT=production
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=latest                    # Or specific version tag
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=443                       # Or 80 for HTTP

# Data Configuration  
SWEDEB_CONFIG_PATH=/app/config/config.yml
SWEDEB_DATA_FOLDER=/data/swedeb/v1.4.1
SWEDEB_METADATA_FILENAME=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db
METADATA_VERSION=v1.1.3
CORPUS_VERSION=v1.4.1

# Container Configuration
SWEDEB_CONTAINER_NAME=swedeb-api
```

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
# Pull latest image
docker compose pull

# Start services
docker compose up -d

# Verify deployment
docker compose ps
docker compose logs -f swedeb_api
```

### Step 5: Configure Reverse Proxy (Optional)

For production, configure nginx or similar:

```nginx
# /etc/nginx/sites-available/swedeb-api
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8092;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🧪 Staging Deployment

### Step 1: Prepare Staging Environment

```bash
# Create staging directory
sudo mkdir -p /opt/swedeb-api-staging
cd /opt/swedeb-api-staging

# Copy staging configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/main/docker/compose/staging/compose.yml
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/main/docker/compose/staging/.env
```

### Step 2: Configure Staging Environment

```bash
# Staging Environment Configuration
SWEDEB_ENVIRONMENT=staging
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=latest                    # Test specific versions here
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=10443                     # Non-standard port for staging

# Use same data as production or separate staging data
SWEDEB_DATA_FOLDER=/data/swedeb/v1.4.1
SWEDEB_METADATA_FILENAME=/data/swedeb/metadata/riksprot_metadata.v1.1.3.db
```

### Step 3: Deploy Staging

```bash
# Deploy to staging
docker compose up -d

# Test staging deployment
curl http://localhost:10443/docs
```

## 🧪 Local Testing with Runlike

For testing the GitHub Actions workflow locally, you can use the `runlike` tool to recreate the exact container environment.

### Step 1: Install Runlike

```bash
# Install runlike
pip install runlike
```

### Step 2: Extract Running Container Configuration

```bash
# If you have a running container
docker ps
runlike swedeb-api-staging > recreate-container.sh

# Make it executable and test
chmod +x recreate-container.sh
./recreate-container.sh
```

### Step 3: Test Local GitHub Actions Workflow

```bash
# Install act for local GitHub Actions testing
# https://github.com/nektos/act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Test the workflow locally
act push -j release --secret GITHUB_TOKEN=$GITHUB_TOKEN

# Test specific steps
act push -j release --secret GITHUB_TOKEN=$GITHUB_TOKEN --dryrun
```

### Step 4: Local Development Testing

```bash
# Build image locally to test changes
cd docker
docker build --build-arg FRONTEND_VERSION=latest -t local-swedeb-api .

# Test with runlike configuration
sed 's/ghcr.io\/humlab-swedeb\/swedeb-api:latest/local-swedeb-api/g' recreate-container.sh > test-local.sh
chmod +x test-local.sh
./test-local.sh
```

## 📊 Monitoring & Maintenance

### Health Check

```bash
# Check container health
docker compose ps
docker compose logs --tail=100 swedeb_api

# Check application health
curl http://localhost:8092/docs
curl http://localhost:8092/health  # If health endpoint exists
```

### Updates

```bash
# Update to latest version
docker compose pull
docker compose up -d

# Update to specific version
# Edit .env file to change SWEDEB_IMAGE_TAG
docker compose up -d
```

### Backup Strategy

```bash
# Backup configuration
tar -czf swedeb-config-$(date +%Y%m%d).tar.gz .env compose.yml

# Data is typically backed up separately as it's large corpus data
```

### Log Management

```bash
# View logs
docker compose logs -f swedeb_api

# Rotate logs (configure in docker daemon or use logrotate)
# Add to /etc/logrotate.d/docker-compose
/opt/swedeb-api/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Image Pull Errors
```bash
# Error: pull access denied
# Solution: Ensure proper authentication
docker login ghcr.io -u username -p token

# Check image exists
docker pull ghcr.io/humlab-swedeb/swedeb-api:latest
```

#### 2. Data Mount Issues
```bash
# Error: Permission denied or file not found
# Solution: Check data paths and permissions
ls -la /data/swedeb/
sudo chown -R 1021:1021 /data/swedeb/

# Verify mount paths in .env match actual data location
```

#### 3. Port Conflicts
```bash
# Error: Port already in use
# Solution: Check for conflicting services
netstat -tulpn | grep :8092
docker ps --filter "publish=8092"

# Change SWEDEB_HOST_PORT in .env
```

#### 4. Container Won't Start
```bash
# Check container logs
docker compose logs swedeb_api

# Check resource usage
docker stats
df -h
free -m

# Verify configuration
docker compose config
```

#### 5. Application Not Responding
```bash
# Check if container is running
docker compose ps

# Check internal connectivity
docker compose exec swedeb_api curl localhost:8092/docs

# Check configuration loading
docker compose exec swedeb_api cat /app/config/config.yml
```

### Debug Commands

```bash
# Enter container for debugging
docker compose exec swedeb_api /bin/bash

# Check environment variables
docker compose exec swedeb_api env | grep SWEDEB

# Test configuration
docker compose exec swedeb_api python -c "from api_swedeb.core.configuration import ConfigStore; print(ConfigStore.default())"

# Check file permissions
docker compose exec swedeb_api ls -la /data/
```

### Performance Tuning

```bash
# Increase container resources if needed
# Add to compose.yml:
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
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] Server meets minimum requirements
- [ ] Data directory structure exists
- [ ] Proper permissions set on data directories
- [ ] Docker and Docker Compose installed
- [ ] Network connectivity verified
- [ ] Backup of existing configuration (if updating)

### Deployment
- [ ] Environment file configured correctly
- [ ] Docker login successful
- [ ] Image pull successful
- [ ] Container starts without errors
- [ ] Application responds to health checks
- [ ] All required endpoints accessible

### Post-Deployment
- [ ] Application functionality tested
- [ ] Performance monitoring configured
- [ ] Log rotation configured
- [ ] Backup procedures implemented
- [ ] Documentation updated
- [ ] Team notified of deployment

## 🔗 Related Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Runlike Tool](https://github.com/lavie/runlike)
- [Act - Local GitHub Actions](https://github.com/nektos/act)
- [Release Setup Documentation](./RELEASE_SETUP.md)

---

*This deployment guide is maintained alongside the CI/CD pipeline and updated with each release.*