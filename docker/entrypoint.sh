#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Verify frontend assets are present (baked into image during build)
if [ -f "/app/public/.frontend_version" ]; then
    FRONTEND_VERSION=$(cat /app/public/.frontend_version)
    log "Frontend version: ${FRONTEND_VERSION}"
else
    log "WARNING: Frontend version file missing"
fi

if [ ! -f "/app/public/index.html" ]; then
    log "ERROR: Frontend assets not found! Image may not have been built correctly."
    log "Expected frontend to be baked into image during build."
    exit 1
fi

FILE_COUNT=$(ls -1 /app/public | wc -l)
log "Frontend assets present: ${FILE_COUNT} files"

log "Starting application server on port ${SWEDEB_PORT}"
exec uvicorn main:app --host 0.0.0.0 --port ${SWEDEB_PORT}