#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Download frontend assets if not already present or if version mismatch
log "Checking frontend assets..."

# Auto-detect frontend version based on backend branch if not explicitly set
if [ -z "${FRONTEND_VERSION:-}" ]; then
    # Use GIT_BRANCH build arg if available, otherwise try to detect
    BRANCH="${GIT_BRANCH:-}"
    
    # If GIT_BRANCH not set, try to detect from git repo
    if [ -z "$BRANCH" ] && command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    fi
    
    # Map branch to frontend version
    case "${BRANCH:-main}" in
        main|master)
            FRONTEND_VERSION="latest"
            ;;
        staging|test)
            FRONTEND_VERSION="${BRANCH}"
            ;;
        *)
            log "Unknown branch '${BRANCH}', defaulting to latest frontend"
            FRONTEND_VERSION="latest"
            ;;
    esac
    
    log "Auto-detected frontend version from branch '${BRANCH}': ${FRONTEND_VERSION}"
else
    log "Using explicit FRONTEND_VERSION: ${FRONTEND_VERSION}"
fi

export FRONTEND_VERSION

# Check if we need to download frontend assets
NEEDS_DOWNLOAD=false

if [ ! -d "/app/public" ] || [ ! "$(ls -A /app/public)" ]; then
    log "Frontend assets directory is empty, download required"
    NEEDS_DOWNLOAD=true
elif [ ! -f "/app/public/.frontend_version" ]; then
    log "Frontend version file missing, download required"
    NEEDS_DOWNLOAD=true
else
    # For staging/test/latest (rolling releases), check SHA256 to detect updates
    if [ "$FRONTEND_VERSION" = "staging" ] || [ "$FRONTEND_VERSION" = "test" ] || [ "$FRONTEND_VERSION" = "latest" ]; then
        log "Checking for updates to ${FRONTEND_VERSION} release..."
        # Trigger download which will check SHA256 and skip if unchanged
        NEEDS_DOWNLOAD=true
    else
        # For pinned versions, check version number
        CURRENT_VERSION=$(cat /app/public/.frontend_version 2>/dev/null || echo "")
        # Normalize version strings by stripping 'v' prefix for comparison
        REQUESTED_VERSION=${FRONTEND_VERSION#v}
        CACHED_VERSION=${CURRENT_VERSION#v}
        
        if [ "$CACHED_VERSION" != "$REQUESTED_VERSION" ]; then
            log "Frontend version mismatch (current: $CURRENT_VERSION, requested: $FRONTEND_VERSION), download required"
            NEEDS_DOWNLOAD=true
        fi
    fi
fi

if [ "$NEEDS_DOWNLOAD" = "true" ]; then
    log "Downloading frontend assets..."
    ./download-frontend.sh
else
    CURRENT_VERSION=$(cat /app/public/.frontend_version 2>/dev/null || echo "unknown")
    log "Frontend assets up-to-date (version: $CURRENT_VERSION)"
fi

# Verify assets are present
if [ ! -f "/app/public/index.html" ]; then
    log "WARNING: Frontend assets may not be properly installed (index.html missing)"
fi

log "Starting application server on port $SWEDEB_PORT"
exec uvicorn main:app --host 0.0.0.0 --port $SWEDEB_PORT