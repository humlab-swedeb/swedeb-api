#!/bin/bash
set -euo pipefail

# Local test script for debugging container startup issues
# This builds the image locally and runs it with detailed logging

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
}

# Parse arguments
SKIP_BUILD=false
SKIP_FRONTEND=false
USE_FALLBACK=false
MOUNT_PUBLIC=false
CONTAINER_TOOL="${CONTAINER_TOOL:-docker}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --use-fallback)
            USE_FALLBACK=true
            shift
            ;;
        --mount-public)
            MOUNT_PUBLIC=true
            shift
            ;;
        --podman)
            CONTAINER_TOOL=podman
            shift
            ;;
        --docker)
            CONTAINER_TOOL=docker
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-build      Skip building the image"
            echo "  --skip-frontend   Skip frontend asset download (for testing other issues)"
            echo "  --use-fallback    Pre-populate fallback tarball for testing"
            echo "  --mount-public    Mount /app/public as writable volume"
            echo "  --podman          Use podman instead of docker"
            echo "  --docker          Use docker (default)"
            echo "  -h, --help        Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Full build and test"
            echo "  $0 --skip-build                       # Just run existing image"
            echo "  $0 --use-fallback                     # Test fallback mechanism"
            echo "  $0 --mount-public                     # Test with writable /app/public"
            echo "  $0 --podman --use-fallback            # Test fallback with Podman"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

log "Starting local container test with $CONTAINER_TOOL"
echo ""

# Clean up old container if exists
CONTAINER_NAME="swedeb-api-local-test"
if $CONTAINER_TOOL ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "Removing existing container: $CONTAINER_NAME"
    $CONTAINER_TOOL rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# Build image if not skipping
if [ "$SKIP_BUILD" = false ]; then
    log "Building local image..."
    cd ..
    
    # Build wheel first
    log "Building Python wheel..."
    mkdir -p wheels
    if uv build --wheel --out-dir wheels 2>&1 | tee /tmp/wheel-build.log | grep -q "Successfully built"; then
        log_success "Wheel built successfully"
    else
        log_error "Wheel build failed - see /tmp/wheel-build.log"
        cat /tmp/wheel-build.log
        exit 1
    fi
    
    # Build Docker image
    log "Building Docker image..."
    BUILD_CMD="$CONTAINER_TOOL build -t swedeb-api:local-test -f docker/Dockerfile \
        --build-arg GIT_BRANCH=dev \
        --build-arg FRONTEND_VERSION=staging \
        ."
    
    if $BUILD_CMD 2>&1 | tee /tmp/docker-build.log; then
        log_success "Image built successfully"
    else
        log_error "Image build failed - see /tmp/docker-build.log"
        tail -50 /tmp/docker-build.log
        exit 1
    fi
    
    cd docker
else
    log_warning "Skipping build (using existing swedeb-api:local-test image)"
fi

echo ""

# Setup test data directories
log "Setting up test data directories..."
mkdir -p test-data/dist test-data/public

# Download fallback tarball if requested
if [ "$USE_FALLBACK" = true ]; then
    FALLBACK_FILE="test-data/dist/frontend-staging.tar.gz"
    if [ ! -f "$FALLBACK_FILE" ]; then
        log "Downloading frontend tarball for fallback testing..."
        if curl -L --fail --progress-bar \
            "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/staging/frontend-staging.tar.gz" \
            -o "$FALLBACK_FILE"; then
            log_success "Fallback tarball downloaded: $FALLBACK_FILE"
        else
            log_error "Failed to download fallback tarball"
            log_error "You can manually download it to: $FALLBACK_FILE"
            log_error "Or skip fallback with: make test-local-podman"
            exit 1
        fi
    else
        log_success "Using existing fallback tarball: $FALLBACK_FILE"
    fi
fi

# Prepare volume mounts
VOLUME_ARGS=()
VOLUME_ARGS+=(-v "$(pwd)/test-data/dist:/data/dist:Z,ro")

if [ "$MOUNT_PUBLIC" = true ]; then
    log "Mounting /app/public as writable volume"
    chmod 755 test-data/public
    VOLUME_ARGS+=(-v "$(pwd)/test-data/public:/app/public:Z")
fi

# Prepare environment variables
ENV_ARGS=()
ENV_ARGS+=(-e "FRONTEND_VERSION=staging")
ENV_ARGS+=(-e "CORPUS_REGISTRY=/data/registry")

if [ "$SKIP_FRONTEND" = true ]; then
    log_warning "Frontend download will be skipped (not implemented yet)"
fi

echo ""
log "Starting container..."
log "Container name: $CONTAINER_NAME"
log "Image: swedeb-api:local-test"
log "Volumes:"
for vol in "${VOLUME_ARGS[@]}"; do
    echo "  $vol"
done
echo ""

# Run container
RUN_CMD="$CONTAINER_TOOL run --rm --name $CONTAINER_NAME \
    -p 8092:8092 \
    ${VOLUME_ARGS[@]} \
    ${ENV_ARGS[@]} \
    swedeb-api:local-test"

log "Executing: $RUN_CMD"
echo ""
echo "=========================================="
echo "Container Output:"
echo "=========================================="
echo ""

# Run and capture output
if $RUN_CMD 2>&1; then
    log_success "Container ran successfully"
    exit 0
else
    EXIT_CODE=$?
    echo ""
    log_error "Container exited with code: $EXIT_CODE"
    exit $EXIT_CODE
fi
