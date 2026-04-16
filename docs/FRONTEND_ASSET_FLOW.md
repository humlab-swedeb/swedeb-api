# Frontend Asset Download Flow

## Overview

The backend downloads frontend assets at container startup from GitHub releases instead of bundling them at build time. This allows independent deployment of frontend and backend components.

## Frontend Release Structure

### Main Branch (Production)
- **Release Tag**: `v{VERSION}` (e.g., `v1.2.3`)
- **Tarball Name**: `frontend-{VERSION}.tar.gz` (e.g., `frontend-1.2.3.tar.gz`)
- **Release Type**: Full release (marked as latest)
- **Created By**: semantic-release + GitHub Actions workflow

### Staging Branch
- **Release Tag**: `staging`
- **Tarball Name**: `frontend-{VERSION}-staging.tar.gz` (e.g., `frontend-1.2.3-staging.tar.gz`)
- **Release Type**: Pre-release
- **Created By**: GitHub Actions workflow

### Test Branch
- **Release Tag**: `test`
- **Tarball Name**: `frontend-{VERSION}-test.tar.gz` (e.g., `frontend-1.2.3-test.tar.gz`)
- **Release Type**: Pre-release
- **Created By**: GitHub Actions workflow

## Backend Download Logic

### Environment Variable: `FRONTEND_VERSION`

The backend supports the following values:

#### `FRONTEND_VERSION=latest` (default)
- Queries GitHub API for latest release
- Gets release tag (e.g., `v1.2.3`)
- Strips 'v' prefix to construct tarball name: `frontend-1.2.3.tar.gz`
- Downloads from: `https://github.com/humlab-swedeb/swedeb_frontend/releases/download/v1.2.3/frontend-1.2.3.tar.gz`
- Caches version `1.2.3` in `/app/public/.frontend_version`

#### `FRONTEND_VERSION=staging`
- Fetches `staging` pre-release
- Dynamically discovers tarball name from release assets
- Downloads: `frontend-{VERSION}-staging.tar.gz`
- Caches version `staging` in `/app/public/.frontend_version`

#### `FRONTEND_VERSION=test`
- Fetches `test` pre-release
- Dynamically discovers tarball name from release assets
- Downloads: `frontend-{VERSION}-test.tar.gz`
- Caches version `test` in `/app/public/.frontend_version`

#### `FRONTEND_VERSION=1.2.3` (specific version)
- Constructs release tag: `v1.2.3`
- Constructs tarball name: `frontend-1.2.3.tar.gz`
- Downloads from: `https://github.com/humlab-swedeb/swedeb_frontend/releases/download/v1.2.3/frontend-1.2.3.tar.gz`
- Caches version `1.2.3` in `/app/public/.frontend_version`

#### `FRONTEND_VERSION=v1.2.3` (with 'v' prefix)
- Strips 'v' prefix for internal processing
- Works exactly like `1.2.3` above

## Script Flow

### 1. entrypoint.sh (Container Startup)

**Purpose**: Orchestrates frontend asset download and starts API server

**Logic**:
1. Check if frontend assets already exist
2. Compare cached version with requested version (normalized by stripping 'v')
3. Download if:
   - Assets directory is empty
   - Version file is missing
   - Requested version doesn't match cached version
   - **Exception**: `latest` is cached forever (no re-check on restart)
4. Verify `index.html` exists
5. Start API server

### 2. download-frontend.sh (Asset Downloader)

**Purpose**: Download and extract frontend assets from GitHub releases

**Logic**:
1. Parse `FRONTEND_VERSION` environment variable
2. Determine download URL and tarball name based on version type
3. Download tarball with retry logic (3 attempts, 5s delay)
4. Verify download succeeded (file exists and not empty)
5. Extract to `/app/public`
6. Write version to `/app/public/.frontend_version`
7. Log success with file count

## Version Normalization

To handle cases where users specify versions with or without 'v' prefix:

- **Storage**: Versions are stored in `.frontend_version` without 'v' prefix (e.g., `1.2.3`)
- **Comparison**: Both cached and requested versions have 'v' stripped before comparison
- **Downloads**: Release tags use 'v' prefix (e.g., `v1.2.3`), but tarballs don't (e.g., `frontend-1.2.3.tar.gz`)

## Caching Behavior

### Persistent Storage
- Assets stored in `/app/public`
- Version tracked in `/app/public/.frontend_version`
- Survives container restarts if volume is mounted

### Cache Invalidation
- Triggered when requested version differs from cached version
- **Important**: `FRONTEND_VERSION=latest` does NOT re-check GitHub on restart
  - Once downloaded, "latest" is cached until manually cleared or version is specified
  - To force update: delete `/app/public` or specify exact version

### Recommendations
- **Production**: Use specific versions (e.g., `1.2.3`) for reproducible deployments
- **Staging**: Use `staging` for automatic updates from staging branch
- **Testing**: Use `test` for automatic updates from test branch
- **Development**: Use `latest` for most recent stable release (cached)

## Error Handling

### Retry Logic
- All GitHub API calls and downloads retry up to 3 times
- 5-second delay between retries
- Logs attempt number and final failure

### Validation
- Verifies downloaded file is not empty
- Verifies extraction produced files
- Warns if `index.html` is missing after extraction
- Fails with descriptive error messages

## Example Deployment Configurations

### Docker Compose - Production
```yaml
services:
  api:
    image: ghcr.io/humlab-swedeb/swedeb-api:latest
    environment:
      - FRONTEND_VERSION=1.2.3  # Pin to specific version
    volumes:
      - frontend-assets:/app/public  # Persist across restarts
```

### Docker Compose - Staging
```yaml
services:
  api:
    image: ghcr.io/humlab-swedeb/swedeb-api:staging
    environment:
      - FRONTEND_VERSION=staging  # Always use latest staging build
    # No volume - download fresh on each deploy
```

### Docker Compose - Development
```yaml
services:
  api:
    image: ghcr.io/humlab-swedeb/swedeb-api:latest
    environment:
      - FRONTEND_VERSION=latest
    volumes:
      - frontend-assets:/app/public
```

## Troubleshooting

### Frontend not updating
- **Check**: Is volume mounted? Assets are cached in `/app/public`
- **Solution**: Remove volume or exec into container and `rm -rf /app/public/*`

### "Failed to find staging/test tarball"
- **Check**: Does the pre-release exist on GitHub?
- **Solution**: Push to staging/test branch to trigger asset build

### "Failed to determine latest version"
- **Check**: GitHub API rate limit or network issue?
- **Solution**: Check `curl -s https://api.github.com/repos/humlab-swedeb/swedeb_frontend/releases/latest`

### Version mismatch not triggering download
- **Check**: Are you using `FRONTEND_VERSION=latest`?
- **Solution**: Specify exact version to force update, or clear `/app/public`

## Migration from Old Docker Image Pattern

### Before
```dockerfile
ARG FRONTEND_VERSION=latest
FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
COPY --from=frontend-dist /app/public ./public
```

### After
```dockerfile
# No frontend image copy at build time
# Assets downloaded at runtime via entrypoint.sh
```

### Benefits
- No Docker image dependency at build time
- Smaller backend images
- Frontend can be updated without backend rebuild
- Better separation of concerns
