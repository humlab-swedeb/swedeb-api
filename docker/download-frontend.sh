#!/bin/bash
set -euo pipefail

# Frontend Asset Download Script
# Downloads frontend assets from GitHub releases or uses local fallback
#
# This script attempts to download frontend assets from GitHub releases.
# If GitHub is unreachable (e.g., network connectivity issues in container),
# it falls back to a local tarball if available.
#
# Fallback location: /data/dist/frontend-${FRONTEND_VERSION}.tar.gz
# To use fallback, place tarball on host at: ${SWEDEB_DATA_FOLDER}/dist/
#
# The script also implements SHA256 caching to avoid re-extracting
# the same version if it's already deployed.

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
    VERSION_TAG=$(retry_command "curl -s --fail https://api.github.com/repos/${GITHUB_REPO}/releases/latest" | \
                  grep '"tag_name"' | cut -d '"' -f 4)
    [ -z "$VERSION_TAG" ] && error_exit "Failed to determine latest version"
    log "Latest release tag: $VERSION_TAG"
    
    # Strip 'v' prefix from tag to get version number (v1.2.3 -> 1.2.3)
    VERSION=${VERSION_TAG#v}
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION_TAG}"
    TARBALL="frontend-${VERSION}.tar.gz"
    
elif [ "$FRONTEND_VERSION" = "staging" ] || [ "$FRONTEND_VERSION" = "test" ]; then
    log "Fetching ${FRONTEND_VERSION} version information..."
    # For staging/test, the release tag is the branch name
    VERSION="${FRONTEND_VERSION}"
    # Tarball name is simply frontend-{staging|test}.tar.gz
    TARBALL="frontend-${FRONTEND_VERSION}.tar.gz"
    log "${FRONTEND_VERSION^} tarball: $TARBALL"
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${FRONTEND_VERSION}"
    
else
    # Specific version provided
    log "Using specified version: $FRONTEND_VERSION"
    # Strip 'v' prefix if present (v1.2.3 -> 1.2.3)
    VERSION=${FRONTEND_VERSION#v}
    # Determine if it's a version tag or branch tag
    if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        # Looks like a semantic version
        VERSION_TAG="v${VERSION}"
        TARBALL="frontend-${VERSION}.tar.gz"
    else
        # Treat as branch/tag name
        VERSION_TAG="$FRONTEND_VERSION"
        TARBALL="frontend-${FRONTEND_VERSION}.tar.gz"
    fi
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION_TAG}"
fi

# Create assets directory
log "Creating assets directory if needed: $ASSETS_DIR"
mkdir -p "$ASSETS_DIR"

# Check if assets directory is writable
if [ ! -w "$ASSETS_DIR" ]; then
    error_exit "Assets directory is not writable: $ASSETS_DIR (check permissions and volume mounts)"
fi

# Test write access with a temporary file
TEST_FILE="${ASSETS_DIR}/.write_test"
if ! touch "$TEST_FILE" 2>/dev/null; then
    error_exit "Cannot write to assets directory: $ASSETS_DIR (read-only filesystem or permission denied)"
fi
rm -f "$TEST_FILE"

log "Assets directory is writable"

# Check for local fallback tarball
FALLBACK_TARBALL="/data/dist/${TARBALL}"
HAS_FALLBACK=false
if [ -f "$FALLBACK_TARBALL" ]; then
    log "Found local fallback tarball: $FALLBACK_TARBALL"
    HAS_FALLBACK=true
fi

# Download and extract frontend assets
TMP_FILE=$(mktemp)
trap "rm -f $TMP_FILE" EXIT

# Try GitHub download with retries
DOWNLOAD_SUCCESS=false
log "Downloading ${TARBALL} from ${DOWNLOAD_URL}"
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -L --fail --progress-bar "${DOWNLOAD_URL}/${TARBALL}" -o "$TMP_FILE" 2>&1; then
        DOWNLOAD_SUCCESS=true
        log "Successfully downloaded from GitHub"
        break
    fi
    
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -lt $MAX_RETRIES ]; then
        log "Download failed, retrying in ${RETRY_DELAY}s (attempt $RETRIES/$MAX_RETRIES)..."
        sleep $RETRY_DELAY
    fi
done

# Fall back to local tarball if GitHub download failed
if [ "$DOWNLOAD_SUCCESS" = false ]; then
    log "GitHub download failed after $MAX_RETRIES attempts"
    
    if [ "$HAS_FALLBACK" = true ]; then
        log "Falling back to local tarball: $FALLBACK_TARBALL"
        cp "$FALLBACK_TARBALL" "$TMP_FILE"
        if [ -s "$TMP_FILE" ]; then
            DOWNLOAD_SUCCESS=true
            log "Successfully copied from local fallback"
        else
            error_exit "Local fallback tarball is empty"
        fi
    else
        error_exit "GitHub download failed and no local fallback found at $FALLBACK_TARBALL"
    fi
fi

# Verify download/fallback
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

# Additional diagnostics for read-only filesystem issues
log "Checking filesystem and permissions..."
log "  Current user: $(whoami) (UID: $(id -u), GID: $(id -g))"
log "  Directory owner: $(stat -c '%U:%G (%u:%g)' "$ASSETS_DIR" 2>/dev/null || echo 'unknown')"
log "  Directory permissions: $(stat -c '%a' "$ASSETS_DIR" 2>/dev/null || echo 'unknown')"
log "  Mount info: $(mount | grep "$(df "$ASSETS_DIR" | tail -1 | awk '{print $1}')" || echo 'unknown')"

# Try extraction
if ! tar -xzf "$TMP_FILE" -C "$ASSETS_DIR" 2>&1; then
    log "ERROR: Failed to extract tarball to $ASSETS_DIR"
    log "This may be due to:"
    log "  1. Read-only filesystem (check: mount | grep $(df $ASSETS_DIR | tail -1 | awk '{print \$1}'))"
    log "  2. SELinux/AppArmor restrictions"
    log "  3. Permission issues"
    log "  4. Podman security settings"
    log ""
    log "Attempting workaround: extract to /tmp and copy..."
    
    # Try extracting to /tmp first, then copying
    TMP_EXTRACT=$(mktemp -d)
    trap "rm -rf $TMP_EXTRACT $TMP_FILE" EXIT
    
    if tar -xzf "$TMP_FILE" -C "$TMP_EXTRACT"; then
        log "Successfully extracted to temporary directory"
        log "Copying files to $ASSETS_DIR..."
        
        if cp -r "$TMP_EXTRACT"/* "$ASSETS_DIR/" 2>/dev/null; then
            log "Successfully copied files to $ASSETS_DIR"
        else
            log "ERROR: Failed to copy files to $ASSETS_DIR"
            error_exit "Cannot write to assets directory - filesystem may be read-only or permissions issue"
        fi
    else
        error_exit "Failed to extract tarball even to temporary directory"
    fi
fi

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