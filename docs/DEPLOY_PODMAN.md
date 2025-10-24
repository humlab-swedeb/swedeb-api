# Podman Quadlet Deployment Guide

This guide covers deploying the Swedeb API using Podman with Quadlet (systemd integration) across all environments. This is the **recommended approach for production** due to its rootless security, native systemd integration, and declarative configuration.

## Why Podman + Quadlet?

- **Rootless by default** - Better security isolation
- **Native systemd integration** - Automatic startup, logging, resource control
- **Declarative configuration** - `.container` files version controlled
- **Drop-in Docker replacement** - Compatible with Docker images
- **Better resource isolation** - cgroups v2 support
- **Auto-updates** - Can be configured with systemd timers

## Prerequisites

- Podman 4.0+
- systemd
- Access to GitHub Container Registry (GHCR)
- Required corpus data and metadata files

## Installation

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

## Authentication

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

## Quadlet Basics

### File Locations

Quadlet files can be placed in different locations:

```bash
# System-wide (requires root)
/etc/containers/systemd/

# User-specific (rootless, recommended)
~/.config/containers/systemd/

# Runtime directory
${XDG_RUNTIME_DIR}/containers/systemd/
```

For this guide, we use **user-specific rootless deployments**.

### File Format

Quadlet uses `.container` files that look similar to systemd units:

```ini
[Unit]
Description=Service Description
After=network-online.target

[Container]
Image=ghcr.io/org/image:tag
ContainerName=container-name
PublishPort=8000:8000
Volume=/host/path:/container/path:Z
Environment=KEY=value

[Service]
Restart=always

[Install]
WantedBy=default.target
```

---

## Test Environment

### Purpose
QA validation and integration testing before promoting to staging.

### Step 1: Create Quadlet Directory

```bash
# Create user systemd directory
mkdir -p ~/.config/containers/systemd
cd ~/.config/containers/systemd
```

### Step 2: Create Container File

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

### Step 3: Verify Data Permissions

```bash
# Ensure corpus data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/riksprot_metadata.v1.1.3.db

# Verify permissions (important for rootless Podman)
# For rootless, ensure your user can read the data
chmod -R u+rX /data/swedeb/
```

### Step 4: Reload systemd and Start Service

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

### Step 5: Validate

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

### Step 6: Manage Service

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

---

## Staging Environment

### Purpose
Pre-production environment mirroring production configuration for final validation.

### Step 1: Create Container File

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

### Step 2: Deploy

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

### Step 3: Validate

```bash
# Check API
curl http://localhost:8002/docs

# Monitor resource usage
podman stats swedeb-api-staging
```

---

## Production Environment

### Purpose
Production deployment serving end users.

### Step 1: Create Container File

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

### Step 2: Create Environment File (Optional)

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

### Step 3: Verify Data and Permissions

```bash
# Ensure data exists
ls -la /data/swedeb/v1.4.1/
ls -la /data/swedeb/metadata/

# For rootless Podman, ensure user has read access
chmod -R u+rX /data/swedeb/

# Create config directory if needed
mkdir -p /opt/swedeb-api/config
```

### Step 4: Deploy Production Service

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

### Step 5: Configure Reverse Proxy

Same nginx configuration as Docker Compose:

```nginx
# /etc/nginx/sites-available/swedeb-api
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8092;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable nginx:
```bash
sudo ln -s /etc/nginx/sites-available/swedeb-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: Production Monitoring

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

---

## Updating Deployments

### Test/Staging (auto-update tags)

```bash
# Pull new image
podman pull ghcr.io/humlab-swedeb/swedeb-api:test

# Restart service (systemd will use new image)
systemctl --user restart swedeb-api-test.service

# Or for staging
podman pull ghcr.io/humlab-swedeb/swedeb-api:staging
systemctl --user restart swedeb-api-staging.service
```

### Production (pinned version)

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

---

## Rollback Procedures

### Test/Staging Rollback

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

### Production Rollback

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

### Emergency Rollback (Keep Running)

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

---

## Auto-Update Configuration (Optional)

Create a systemd timer to automatically check for and pull new images:

### Create Update Service

`~/.config/systemd/user/swedeb-api-update.service`:
```ini
[Unit]
Description=Update Swedeb API Production Image
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.1
ExecStartPost=/usr/bin/systemctl --user try-restart swedeb-api-production.service
```

### Create Timer

`~/.config/systemd/user/swedeb-api-update.timer`:
```ini
[Unit]
Description=Check for Swedeb API updates daily

[Timer]
# Check daily at 3 AM
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Enable Timer

```bash
systemctl --user daemon-reload
systemctl --user enable --now swedeb-api-update.timer

# Check timer status
systemctl --user list-timers
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check service status
systemctl --user status swedeb-api-production.service

# Check container status
podman ps
podman inspect swedeb-api-production

# Health check status (if configured in Quadlet)
podman healthcheck run swedeb-api-production
```

### Logs

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

### Resource Monitoring

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

### Image Management

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

### Backup

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

---

## Best Practices

1. **Use rootless mode** - Better security isolation
2. **Enable lingering** - Ensure services survive logout (`loginctl enable-linger`)
3. **Pin versions in Quadlet** - Explicitly set image tags in production
4. **Use SELinux** - Add `:Z` to volume mounts for proper labeling
5. **Monitor via journald** - Centralized logging with `journalctl`
6. **Test Quadlet changes** - Validate with `systemctl --user daemon-reload`
7. **Auto-update carefully** - Use systemd timers with notification on failure
8. **Resource limits** - Set Memory, CPU limits in Quadlet files
9. **Health checks** - Configure health checks in container definitions
10. **Backup Quadlet files** - Keep versioned copies of `.container` files

---

## Related Resources

- [Main Deployment Guide](./DEPLOYMENT.md) - Overview and CI/CD information
- [Docker Compose Deployment](./DEPLOY_DOCKER.md) - Alternative deployment method
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common Podman-specific issues
- [Quadlet Documentation](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [Podman Documentation](https://docs.podman.io/)

---

*For additional support, see the main [README](../README.md) or open an issue on GitHub.*
