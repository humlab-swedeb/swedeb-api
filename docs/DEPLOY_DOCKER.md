# Docker Compose Deployment Guide

This guide covers deploying the Swedeb API using Docker Compose across all environments (test, staging, production).

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Access to GitHub Container Registry (GHCR)
- Required corpus data and metadata files

## Authentication

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin

# Or using Personal Access Token (PAT)
docker login ghcr.io -u your-username
# Enter PAT when prompted
```

---

## Test Environment

### Purpose
QA validation and integration testing before promoting to staging.

### Step 1: Prepare Test Server

```bash
# Create deployment directory
sudo mkdir -p /opt/swedeb-api-test
cd /opt/swedeb-api-test

# Download compose configuration
curl -O https://raw.githubusercontent.com/humlab-swedeb/swedeb-api/test/docker/compose.test.yml
```

### Step 2: Configure Environment

Create `.env` file:

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

### Step 4: Deploy

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

---

## Staging Environment

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

Create `.env` file:

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

### Step 3: Deploy

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

---

## Production Environment

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

Create `.env` file:

```bash
# Production Environment Configuration
SWEDEB_ENVIRONMENT=production
SWEDEB_IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
SWEDEB_IMAGE_TAG=0.6.1                     # Pin specific version (RECOMMENDED)
# SWEDEB_IMAGE_TAG=production              # Or use 'production' tag for auto-updates
SWEDEB_PORT=8092
SWEDEB_HOST_PORT=8092                      # Production port

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

## Updating Deployments

### Test/Staging (auto-update tags)

```bash
cd /opt/swedeb-api-test  # or staging
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d
```

### Production (pinned version)

```bash
cd /opt/swedeb-api

# Update .env with new version
sed -i 's/SWEDEB_IMAGE_TAG=0.6.0/SWEDEB_IMAGE_TAG=0.6.1/' .env

# Pull and deploy
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d
```

---

## Rollback Procedures

### Test Environment

```bash
cd /opt/swedeb-api-test

# Stop current deployment
docker compose -f compose.test.yml down

# Option 1: Update to specific version
sed -i 's/SWEDEB_IMAGE_TAG=test/SWEDEB_IMAGE_TAG=0.6.0-test/' .env
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d

# Option 2: Re-pull previous test image (if still tagged as 'test')
docker compose -f compose.test.yml pull
docker compose -f compose.test.yml up -d
```

### Staging Environment

```bash
cd /opt/swedeb-api-staging

# Rollback to specific staging version
docker compose -f compose.staging.yml down
sed -i 's/SWEDEB_IMAGE_TAG=staging/SWEDEB_IMAGE_TAG=0.6.0-staging/' .env
docker compose -f compose.staging.yml pull
docker compose -f compose.staging.yml up -d
```

### Production Environment

```bash
cd /opt/swedeb-api

# Rollback to specific version
docker compose -f compose.production.yml down
sed -i 's/SWEDEB_IMAGE_TAG=0.6.1/SWEDEB_IMAGE_TAG=0.6.0/' .env
docker compose -f compose.production.yml pull
docker compose -f compose.production.yml up -d

# Verify rollback
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=50
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check API endpoints
curl http://localhost:8092/docs
curl http://localhost:8092/health

# Check container status
docker compose -f compose.production.yml ps

# View logs
docker compose -f compose.production.yml logs -f
docker compose -f compose.production.yml logs --tail=100
```

### Resource Monitoring

```bash
# Check container resources
docker stats

# Check specific service
docker compose -f compose.production.yml top

# Check disk usage
docker system df
```

### Logs

```bash
# View logs
docker compose -f compose.production.yml logs -f

# Tail recent logs
docker compose -f compose.production.yml logs --tail=100

# Filter by service
docker compose -f compose.production.yml logs swedeb_api

# Export logs
docker compose -f compose.production.yml logs --no-color > deployment.log
```

### Cleanup

```bash
# Remove old images
docker image prune -a

# Clean up system
docker system prune -a

# Remove specific old images
docker rmi ghcr.io/humlab-swedeb/swedeb-api:0.5.0
```

---

## Best Practices

1. **Pin versions in production** - Use specific tags (e.g., `0.6.1`) not `latest`
2. **Test before deploying** - Always validate in test environment first
3. **Regular backups** - Backup configuration files and `.env` files
4. **Monitor resources** - Track CPU, memory, disk usage
5. **Log rotation** - Configure log management to prevent disk fill
6. **Security updates** - Keep Docker and base images updated

---

## Related Resources

- [Main Deployment Guide](./DEPLOYMENT.md) - Overview and CI/CD information
- [Podman Deployment Guide](./DEPLOY_PODMAN.md) - Alternative deployment method
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions

---

*For additional support, see the main [README](../README.md) or open an issue on GitHub.*
