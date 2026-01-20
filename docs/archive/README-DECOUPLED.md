# Decoupled Frontend/Backend Architecture

## Overview

This architecture eliminates the container dependency between frontend and backend by downloading frontend assets at runtime from GitHub releases.

## Benefits

- ✅ **Podman Compatible**: No shared volumes or complex mount configurations
- ✅ **Security First**: Self-contained containers without external dependencies
- ✅ **Decoupled**: Backend can be built independently of frontend
- ✅ **Flexible Versioning**: Support for latest, specific versions, or branches
- ✅ **Failure Resilient**: Retry logic and graceful degradation
- ✅ **Cache Friendly**: Avoids re-downloading when version hasn't changed

## How It Works

1. **Build Time**: Backend container is built with frontend download script
2. **Startup Time**: Container downloads and extracts frontend assets
3. **Runtime**: Application serves frontend assets from local filesystem
4. **Updates**: New frontend versions are automatically downloaded on restart

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_VERSION` | `latest` | Frontend version to download (`latest`, `staging`, or specific version like `v0.10.1`) |
| `ASSETS_DIR` | `/app/public` | Directory to extract frontend assets |

## Frontend Release Types

| Version | Release Type | Description | Tarball Format |
|---------|--------------|-------------|----------------|
| `latest` | Production | Latest stable release from `main` branch | `frontend-v{version}.tar.gz` |
| `staging` | Pre-release | Latest build from `staging` branch (floating) | `frontend-{version}-staging.tar.gz` |
| `v0.10.1` | Production | Specific versioned release | `frontend-v0.10.1.tar.gz` |

## Usage

### Basic Usage
```bash
# Latest production release
podman run -e FRONTEND_VERSION=latest ghcr.io/humlab-swedeb/swedeb-api:latest

# Latest staging build
podman run -e FRONTEND_VERSION=staging ghcr.io/humlab-swedeb/swedeb-api:latest

# Specific production version (recommended)
podman run -e FRONTEND_VERSION=v1.2.3 ghcr.io/humlab-swedeb/swedeb-api:latest
```

### With Compose
```yaml
environment:
  - FRONTEND_VERSION=${FRONTEND_VERSION:-latest}
```

### Environment-Specific Recommendations

| Environment | Recommended Setting | Rationale |
|-------------|-------------------|-----------|
| **Development** | `latest` or `staging` | Get latest features |
| **Test** | `latest` | Test with latest production release |
| **Staging** | `staging` | Validate pre-release builds |
| **Production** | `v0.10.1` (pinned) | Stability and predictability |

## File Structure

```
docker/
├── Dockerfile                 # Updated to remove frontend dependency
├── entrypoint.sh             # Downloads assets on startup
├── download-frontend.sh      # Asset download logic
├── healthcheck.sh           # Health check including asset verification
└── deployment/
    └── example-decoupled.env # Environment configuration example
```

## Security Considerations

- No shared volumes between containers
- Assets downloaded over HTTPS
- Retry logic with exponential backoff
- Proper error handling and logging
- Non-root user execution

## Troubleshooting

### Frontend Assets Not Loading
1. Check container logs for download errors
2. Verify GitHub releases contain the expected tarball format:
   - Production: `frontend-v{version}.tar.gz`
   - Staging: `frontend-{version}-staging.tar.gz`
3. Ensure network connectivity to GitHub

### Version Mismatch
1. Check `.frontend_version` file in container
2. Update `FRONTEND_VERSION` environment variable
3. Restart container to trigger re-download

### Staging Release Not Found
1. Verify staging workflow has run successfully
2. Check that `staging` release exists in GitHub releases
3. Confirm release is marked as pre-release
4. Verify tarball follows naming: `frontend-*-staging.tar.gz`

### Download Failures
1. Check network connectivity
2. Verify GitHub API rate limits
3. Check release asset naming conventions
4. For staging, ensure release tag is exactly "staging"