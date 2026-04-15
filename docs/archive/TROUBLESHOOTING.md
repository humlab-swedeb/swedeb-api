# Troubleshooting Guide

This guide covers common issues and solutions when deploying and running the Swedeb API.

## Table of Contents

- [Common Issues](#common-issues)
  - [Docker-Specific Issues](#docker-specific-issues)
  - [Podman-Specific Issues](#podman-specific-issues)
- [Debug Commands](#debug-commands)
- [Performance Tuning](#performance-tuning)

## Common Issues

### Docker-Specific Issues

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
docker compose -f compose.production.yml exec swedeb_api curl -f http://localhost:8000/health

# Check logs for errors
docker compose -f compose.production.yml logs --tail=100

# Restart service
docker compose -f compose.production.yml restart swedeb_api
```

#### 7. High Memory Usage

```bash
# Check memory consumption
docker stats --no-stream

# Identify memory-heavy processes
docker compose -f compose.production.yml exec swedeb_api ps aux --sort=-%mem | head

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

#### Docker

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

#### Podman

```bash
# Enter container for debugging
podman exec -it swedeb-api-production /bin/bash

# Check Python environment
podman exec swedeb-api-production python --version
podman exec swedeb-api-production pip list

# Test configuration
podman exec swedeb-api-production python -c \
  "from api_swedeb.core.configuration import ConfigStore; print(ConfigStore.default())"

# Check file permissions
podman exec swedeb-api-production ls -la /app/
podman exec swedeb-api-production ls -la /data/

# Check network connectivity
podman exec swedeb-api-production ping -c 3 ghcr.io
podman exec swedeb-api-production curl -I https://ghcr.io

# Check volume mounts
podman inspect swedeb-api-production | jq '.[0].Mounts'

# Test CWB tools
podman exec swedeb-api-production cwb-describe-corpus

# Check systemd service
systemctl --user status swedeb-api-production.service
journalctl --user -u swedeb-api-production.service --no-pager | tail -100
```

---

### Podman-Specific Issues

#### 1. Rootless Port Binding (<1024)

```bash
# Error: Cannot bind to privileged ports as rootless user

# Solution 1: Use port mapping (8092:8000 instead of 80:8000)
# Already done in examples above

# Solution 2: Enable rootless port binding
sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80
# Make permanent:
echo 'net.ipv4.ip_unprivileged_port_start=80' | sudo tee /etc/sysctl.d/50-rootless-ports.conf
sudo sysctl --system

# Solution 3: Use rootful Podman (not recommended)
sudo podman ...
```

#### 2. SELinux Permission Denied

```bash
# Error: Permission denied accessing volumes

# Solution: Add :Z flag to volume mounts in Quadlet
Volume=/data/swedeb:/data/swedeb:Z

# Or relabel manually
sudo chcon -R -t container_file_t /data/swedeb/

# Or disable SELinux (not recommended for production)
sudo setenforce 0
```

#### 3. Systemd Service Won't Start After Reboot

```bash
# Error: Service doesn't start automatically

# Solution: Enable user lingering
sudo loginctl enable-linger $USER

# Verify
loginctl show-user $USER | grep Linger

# Check if service is enabled
systemctl --user is-enabled swedeb-api-production.service

# Enable if not
systemctl --user enable swedeb-api-production.service
```

#### 4. Quadlet File Not Detected

```bash
# Quadlet file isn't generating systemd service

# Check Quadlet file location
ls -la ~/.config/containers/systemd/

# Ensure correct extension (.container)
mv swedeb-api.conf swedeb-api.container

# Reload systemd
systemctl --user daemon-reload

# Check for errors
journalctl --user -xe | grep -i quadlet

# List generated services
systemctl --user list-units 'swedeb-api*'
```

#### 5. Image Pull Fails in Rootless Mode

```bash
# Error: Failed to pull image

# Check registry authentication
cat ${XDG_RUNTIME_DIR}/containers/auth.json
# or
cat ~/.config/containers/auth.json

# Re-authenticate
podman login ghcr.io -u username

# Pull manually to debug
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.6.1

# Check for proxy issues
env | grep -i proxy
```

#### 6. Volume Mount Permission Issues

```bash
# Error: Permission denied reading from volume

# Check ownership
ls -la /data/swedeb/

# For rootless Podman, user ID mapping is used
# Inside container, user may map to different UID outside

# Solution 1: Ensure volume has correct permissions
chmod -R u+rX /data/swedeb/

# Solution 2: Use :U flag for automatic UID/GID mapping
Volume=/data/swedeb:/data/swedeb:U

# Solution 3: Check subuid/subgid mappings
cat /etc/subuid
cat /etc/subgid
```

#### 7. Container Can't Resolve DNS

```bash
# Error: Network resolution failed

# Check DNS in container
podman exec swedeb-api-production cat /etc/resolv.conf

# Solution 1: Configure DNS in Quadlet
[Container]
DNS=8.8.8.8
DNS=8.8.4.4

# Solution 2: Use host network (less secure)
[Container]
Network=host

# Solution 3: Check systemd-resolved
systemctl status systemd-resolved
```

## Performance Tuning

### Docker Performance Optimization

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

# Restart Docker daemon
sudo systemctl restart docker
```

### Resource Limits

```bash
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

### Podman Performance

```bash
# Check resource usage
podman stats swedeb-api-production

# Monitor systemd resource control
systemctl --user show swedeb-api-production.service | grep -E "Memory|CPU"

# Adjust limits in Quadlet file
[Container]
Memory=16G
MemorySwap=16G
CPUQuota=800%
PidsLimit=4096
```

---

## Related Resources

- [Deployment Guide](./DEPLOYMENT.md) - Complete deployment instructions
- [Workflow Guide](./WORKFLOW_GUIDE.md) - Developer workflow
- [Workflow Architecture](./WORKFLOW_ARCHITECTURE.md) - CI/CD architecture

---

*For additional support, consult the main [README](../README.md) or open an issue on GitHub.*
