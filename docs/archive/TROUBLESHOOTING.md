# Troubleshooting Guide

This guide covers common issues and their solutions when deploying and running the Swedeb API.

## Table of Contents

- [Container Issues](#container-issues)
  - [Network Connectivity](#network-connectivity)
  - [Frontend Download Failures](#frontend-download-failures)
- [Data Issues](#data-issues)
- [Performance Issues](#performance-issues)
- [Podman-Specific Issues](#podman-specific-issues)

---

## Container Issues

### Network Connectivity

**Symptom**: Container cannot reach external networks (GitHub, APIs, etc.)

**Common Error**:
```
curl: (7) Failed to connect to github.com port 443 after 2 ms: Couldn't connect to server
```

**Diagnosis**: Use the network troubleshooting script:

```bash
# Run inside the container
podman exec -it swedeb-api-production /app/docker/test-network.sh

# Or from the container:
/app/docker/test-network.sh
```

The script tests:
- DNS resolution (github.com, api.github.com, google.com)
- Network connectivity (ping tests)
- HTTP/HTTPS connectivity
- GitHub API access
- Frontend tarball download

**Common Causes and Solutions**:

#### 1. DNS Resolution Failure

**Cause**: Container can't resolve hostnames

**Solution**: Add DNS servers to your container configuration

For Quadlet (`.container` file):
```ini
[Container]
DNS=8.8.8.8
DNS=8.8.4.4
DNS=1.1.1.1
```

For Compose (docker/compose.yml):
```yaml
services:
  swedeb_api:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
```

System-wide Podman configuration (/etc/containers/containers.conf):
```toml
[network]
dns_servers = [
  "8.8.8.8",
  "8.8.4.4",
  "1.1.1.1"
]
```

#### 2. Firewall Blocking

**Cause**: Host firewall blocks container traffic

**Test**:
```bash
# Check firewall rules
sudo firewall-cmd --list-all

# Temporarily disable (testing only!)
sudo systemctl stop firewalld
```

**Solution**: Configure firewall to allow container traffic
```bash
# Allow specific ports
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Or add podman interface to trusted zone
sudo firewall-cmd --permanent --zone=trusted --add-interface=podman0
sudo firewall-cmd --reload
```

#### 3. SELinux Issues

**Cause**: SELinux prevents network access

**Test**:
```bash
# Check SELinux mode
getenforce

# Temporarily set to permissive (testing only!)
sudo setenforce 0
```

**Solution**: Configure SELinux policies or use appropriate labels
```bash
# For volume mounts, use :Z flag
Volume=/data:/data:Z

# Check audit logs
sudo ausearch -m AVC -ts recent
```

#### 4. Network Mode Issues

**Workaround**: Temporarily use host network for debugging
```yaml
# In compose.yml (testing only!)
network_mode: "host"
```

**Note**: This bypasses network isolation and should not be used in production.

---

### Frontend Download Failures

**Symptom**: Container fails to start due to frontend asset download failure

**Error**:
```
ERROR: GitHub download failed and no local fallback found
```

**Solution 1: Fix Network Connectivity**

See [Network Connectivity](#network-connectivity) section above.

**Solution 2: Use Local Fallback**

The container supports a local fallback tarball if GitHub is unreachable.

1. **Download the frontend tarball** on a machine with internet access:
   ```bash
   # For latest version
   VERSION=$(curl -s https://api.github.com/repos/humlab-swedeb/swedeb_frontend/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
   curl -L "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/${VERSION}/frontend-${VERSION#v}.tar.gz" \
     -o frontend-latest.tar.gz
   
   # For staging
   curl -L "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/staging/frontend-staging.tar.gz" \
     -o frontend-staging.tar.gz
   
   # For test
   curl -L "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/test/frontend-test.tar.gz" \
     -o frontend-test.tar.gz
   ```

2. **Copy the tarball to the data directory**:
   ```bash
   # Create dist directory
   mkdir -p ${SWEDEB_DATA_FOLDER}/dist
   
   # Copy tarball (use correct filename for your version)
   cp frontend-staging.tar.gz ${SWEDEB_DATA_FOLDER}/dist/
   ```

3. **Start the container**:
   The download script will automatically detect and use the local tarball if GitHub fails.

**Fallback Mechanism**:

The container looks for tarballs at:
```
/data/dist/frontend-${FRONTEND_VERSION}.tar.gz
```

Examples:
- `FRONTEND_VERSION=latest` → `/data/dist/frontend-latest.tar.gz`
- `FRONTEND_VERSION=staging` → `/data/dist/frontend-staging.tar.gz`
- `FRONTEND_VERSION=test` → `/data/dist/frontend-test.tar.gz`
- `FRONTEND_VERSION=1.2.3` → `/data/dist/frontend-1.2.3.tar.gz`

The script will:
1. Try to download from GitHub (with 3 retries)
2. If all retries fail, check for local fallback
3. Use local fallback if available
4. Fail with clear error if neither works

**Pre-download Strategy for Air-Gapped Deployments**:

For completely offline deployments:

```bash
# On internet-connected machine, download assets
./download-assets.sh staging

# Transfer to target machine
rsync -avz data/dist/ target-machine:/path/to/data/dist/

# Deploy on target machine (will use local fallback)
systemctl --user start swedeb-api-staging
```

---

## Data Issues

### Corpus Data Not Found

**Symptom**: API returns errors about missing corpus data

**Solution**: Verify data directory structure and mounts

```bash
# Check data directory structure
ls -la ${SWEDEB_DATA_FOLDER}

# Verify CWB corpus
ls -la ${SWEDEB_DATA_FOLDER}/v1.4.1/cwb/

# Check metadata database
ls -la ${SWEDEB_DATA_FOLDER}/metadata/
```

### Metadata Database Errors

**Symptom**: API fails to query metadata

**Solution**: Verify metadata database file and permissions

```bash
# Check database file
file ${SWEDEB_METADATA_FILENAME}

# Test database
sqlite3 ${SWEDEB_METADATA_FILENAME} "SELECT COUNT(*) FROM person;"

# Check permissions
chmod 644 ${SWEDEB_METADATA_FILENAME}
```

---

## Performance Issues

### Slow KWIC Queries

**Symptom**: Search queries take too long

**Diagnosis**: Profile KWIC performance
```bash
make profile-kwic-pyinstrument
```

**Solutions**:
- Reduce query complexity
- Use more specific filters (dates, parties, etc.)
- Check CWB index integrity
- Monitor memory usage

### High Memory Usage

**Symptom**: Container uses excessive memory

**Diagnosis**: Check memory usage
```bash
# Container memory stats
podman stats swedeb-api-production

# Inside container
free -h
```

**Solutions**:
- Set memory limits in container config
- Optimize corpus loading
- Check for memory leaks in logs

---

## Podman-Specific Issues

### Permission Denied Errors

**Symptom**: Volume mounts fail with permission errors, or "Read-only file system" errors

**Cause**: UID/GID mismatch, SELinux, or filesystem mount options

**Common Scenarios**:

#### 1. Read-only /app/public directory

**Error**:
```
tar: ./index.html: Cannot open: Read-only file system
```

**Diagnosis**:
```bash
# Check container filesystem
podman exec -it <container> stat /app/public
podman exec -it <container> mount | grep overlay

# Check if container is running with read-only root
podman inspect <container> | grep -i readonly
```

**Solutions**:

**Option A**: Ensure /app/public is not mounted as read-only
```bash
# Check Quadlet file - ensure no :ro flag on /app or /app/public
# Should NOT have:
Volume=/app/public:/app/public:ro
```

**Option B**: Use SELinux volume labels
```bash
# Use :Z flag for SELinux context
Volume=/data:/data:Z

# Or use :U flag for UID/GID mapping (Podman 4.3+)
Volume=/data:/data:U
```

**Option C**: Fix ownership in container
```dockerfile
# In Dockerfile, ensure proper ownership
RUN mkdir -p /app/public && \
    chown ${APP_USER}:${APP_USER} /app/public && \
    chmod 755 /app/public
```

**Option D**: Use temporary extraction (automatic fallback)

The download script now automatically tries to extract to /tmp first if /app/public is read-only, then copies the files. Check logs for:
```
Attempting workaround: extract to /tmp and copy...
```

#### 2. Volume mount permission issues
```bash
# Use :Z flag for SELinux context
Volume=/data:/data:Z

# Or use :U flag for UID/GID mapping
Volume=/data:/data:U

# Check ownership
ls -lan /path/to/data
```

### Container Won't Start

**Symptom**: `systemctl --user start` fails

**Diagnosis**:
```bash
# Check status
systemctl --user status swedeb-api-production

# View logs
journalctl --user -u swedeb-api-production -n 50

# Check Quadlet file
podman systemctl status swedeb-api-production
```

### Image Pull Failures

**Symptom**: Cannot pull image from GHCR

**Solution**:
```bash
# Re-authenticate
echo $GITHUB_TOKEN | podman login ghcr.io -u $GITHUB_USERNAME --password-stdin

# Test pull manually
podman pull ghcr.io/humlab-swedeb/swedeb-api:latest

# Check credentials
cat ${XDG_RUNTIME_DIR}/containers/auth.json
```

---

## Getting Help

If you're still experiencing issues:

1. **Collect diagnostic information**:
   ```bash
   # Network diagnostics
   podman exec -it <container> /app/docker/test-network.sh > network-diag.txt
   
   # Container logs
   journalctl --user -u <service-name> -n 200 > container-logs.txt
   
   # System info
   podman info > podman-info.txt
   podman version > podman-version.txt
   ```

2. **Check documentation**:
   - [Deployment Guide](./DEPLOYMENT.md)
   - [Podman Deployment](./archive/DEPLOY_PODMAN.md) (archived)
   - [Developer Guide](./DEVELOPER.md)

3. **Report issues**:
   - Include all diagnostic output
   - Describe steps to reproduce
   - Specify environment (OS, Podman version, etc.)
   - Open issue at: https://github.com/humlab-swedeb/swedeb-api/issues
