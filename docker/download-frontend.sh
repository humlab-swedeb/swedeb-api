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

# Check if assets already exist and are current
if [ -f "$ASSETS_DIR/.frontend_version" ]; then
    CURRENT_VERSION=$(cat "$ASSETS_DIR/.frontend_version" 2>/dev/null || echo "")
    if [ "$CURRENT_VERSION" = "$VERSION" ]; then
        log "Frontend assets already up-to-date (version: $VERSION)"
        exit 0
    else
        log "Version mismatch detected (current: $CURRENT_VERSION, requested: $VERSION)"
        log "Cleaning existing assets before downloading new version..."
        if [ -z "$ASSETS_DIR" ] || [ "$ASSETS_DIR" = "/" ]; then error_exit "Invalid ASSETS_DIR"; fi
        rm -rf "${ASSETS_DIR:?}"/*
    fi
fi

# Create assets directory
log "Creating assets directory: $ASSETS_DIR"
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

log "Extracting frontend assets to $ASSETS_DIR"
tar -xzf "$TMP_FILE" -C "$ASSETS_DIR" || error_exit "Failed to extract tarball"

# Verify extraction
if [ ! "$(ls -A "$ASSETS_DIR")" ]; then
    error_exit "Assets directory is empty after extraction"
fi

# Mark version
echo "$VERSION" > "$ASSETS_DIR/.frontend_version"

log "Frontend assets successfully downloaded and extracted"
log "Version: $VERSION"
log "Location: $ASSETS_DIR"
log "Files: $(find "$ASSETS_DIR" -type f | wc -l) files"