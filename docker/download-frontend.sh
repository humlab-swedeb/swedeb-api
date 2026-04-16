#!/bin/bash
set -euo pipefail

# Configuration
FRONTEND_VERSION=${FRONTEND_VERSION:-latest}
ASSETS_DIR=${ASSETS_DIR:-/app/public}
GITHUB_REPO="humlab-swedeb/swedeb_frontend"
MAX_RETRIES=3
RETRY_DELAY=5

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error_exit() {
    log "ERROR: $1" >&2
    exit 1
}

retry_command() {
    local cmd="$1"
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if eval "$cmd"; then
            return 0
        fi
        
        retries=$((retries + 1))
        if [ $retries -lt $MAX_RETRIES ]; then
            log "Command failed, retrying in ${RETRY_DELAY}s (attempt $retries/$MAX_RETRIES)..."
            sleep $RETRY_DELAY
        fi
    done
    
    error_exit "Command failed after $MAX_RETRIES attempts: $cmd"
}

# Validate environment
command -v curl >/dev/null 2>&1 || error_exit "curl is required but not installed"
command -v tar >/dev/null 2>&1 || error_exit "tar is required but not installed"
command -v sha256sum >/dev/null 2>&1 || error_exit "sha256sum is required but not installed"

log "Starting frontend asset download for version: ${FRONTEND_VERSION}"

# Determine version and download URL
if [ "$FRONTEND_VERSION" = "latest" ]; then
    log "Fetching latest version information..."
    VERSION=$(retry_command "curl -s --fail https://api.github.com/repos/${GITHUB_REPO}/releases/latest" | \
              grep '"tag_name"' | cut -d '"' -f 4)
    [ -z "$VERSION" ] && error_exit "Failed to determine latest version"
    log "Latest version: $VERSION"
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}"
    TARBALL="frontend-${VERSION}.tar.gz"
elif [ "$FRONTEND_VERSION" = "staging" ]; then
    log "Fetching staging version information..."
    # For staging, the release tag is always "staging"
    VERSION="staging"
    # Get the actual version from the release assets
    RELEASE_INFO=$(retry_command "curl -s --fail https://api.github.com/repos/${GITHUB_REPO}/releases/tags/staging")
    # Extract the first asset name that matches frontend-*-staging.tar.gz
    TARBALL=$(echo "$RELEASE_INFO" | grep -o 'frontend-[^"]*-staging\.tar\.gz' | head -n 1)
    [ -z "$TARBALL" ] && error_exit "Failed to find staging tarball in release"
    log "Staging tarball: $TARBALL"
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/staging"
else
    VERSION="$FRONTEND_VERSION"
    log "Using specified version: $VERSION"
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}"
    TARBALL="frontend-${VERSION}.tar.gz"
fi

# Create assets directory
log "Creating assets directory if needed: $ASSETS_DIR"
mkdir -p "$ASSETS_DIR"

# Download and extract frontend assets
log "Downloading ${TARBALL} from ${DOWNLOAD_URL}"
TMP_FILE=$(mktemp)
trap "rm -f $TMP_FILE" EXIT

retry_command "curl -L --fail --progress-bar '${DOWNLOAD_URL}/${TARBALL}' -o '$TMP_FILE'"

# Verify download
if [ ! -s "$TMP_FILE" ]; then
    error_exit "Downloaded file is empty or does not exist"
fi

# Compute SHA256 of downloaded tarball
log "Computing SHA256 checksum..."
DOWNLOADED_SHA256=$(sha256sum "$TMP_FILE" | cut -d' ' -f1)
log "Downloaded tarball SHA256: $DOWNLOADED_SHA256"

# Check if we already have this exact version cached
if [ -f "$ASSETS_DIR/.frontend_sha256" ]; then
    CACHED_SHA256=$(cat "$ASSETS_DIR/.frontend_sha256" 2>/dev/null || echo "")
    if [ "$CACHED_SHA256" = "$DOWNLOADED_SHA256" ]; then
        log "Frontend assets are already up-to-date (SHA256 match)"
        log "Skipping extraction"
        exit 0
    else
        log "SHA256 mismatch - new version detected"
        log "Cached:     $CACHED_SHA256"
        log "Downloaded: $DOWNLOADED_SHA256"
        log "Cleaning existing assets before extracting new version..."
        if [ -z "$ASSETS_DIR" ] || [ "$ASSETS_DIR" = "/" ]; then error_exit "Invalid ASSETS_DIR"; fi
        rm -rf "${ASSETS_DIR:?}"/*
        mkdir -p "$ASSETS_DIR"
    fi
else
    log "No cached SHA256 found, proceeding with extraction"
fi

log "Extracting frontend assets to $ASSETS_DIR"
tar -xzf "$TMP_FILE" -C "$ASSETS_DIR" || error_exit "Failed to extract tarball"

# Verify extraction
if [ ! "$(ls -A "$ASSETS_DIR")" ]; then
    error_exit "Assets directory is empty after extraction"
fi

# Mark version and save SHA256 checksum
echo "$VERSION" > "$ASSETS_DIR/.frontend_version"
echo "$DOWNLOADED_SHA256" > "$ASSETS_DIR/.frontend_sha256"

log "Frontend assets successfully downloaded and extracted"
log "Version: $VERSION"
log "SHA256:  $DOWNLOADED_SHA256"
log "Location: $ASSETS_DIR"
log "Files: $(find "$ASSETS_DIR" -type f | wc -l) files"