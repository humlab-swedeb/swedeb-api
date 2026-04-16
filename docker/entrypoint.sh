#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Download frontend assets if not already present or if version mismatch
log "Checking frontend assets..."

# Set frontend version from environment or use latest
FRONTEND_VERSION=${FRONTEND_VERSION:-latest}
export FRONTEND_VERSION

# Check if we need to download frontend assets
NEEDS_DOWNLOAD=false

if [ ! -d "/app/public" ] || [ ! "$(ls -A /app/public)" ]; then
    log "Frontend assets directory is empty, download required"
    NEEDS_DOWNLOAD=true
elif [ ! -f "/app/public/.frontend_version" ]; then
    log "Frontend version file missing, download required"
    NEEDS_DOWNLOAD=true
elif [ "$FRONTEND_VERSION" != "latest" ]; then
    CURRENT_VERSION=$(cat /app/public/.frontend_version 2>/dev/null || echo "")
    # Normalize version strings by stripping 'v' prefix for comparison
    REQUESTED_VERSION=${FRONTEND_VERSION#v}
    CACHED_VERSION=${CURRENT_VERSION#v}
    
    if [ "$CACHED_VERSION" != "$REQUESTED_VERSION" ]; then
        log "Frontend version mismatch (current: $CURRENT_VERSION, requested: $FRONTEND_VERSION), download required"
        NEEDS_DOWNLOAD=true
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