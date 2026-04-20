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
FRONTEND_DIR=""
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
        --frontend-dir)
            FRONTEND_DIR="$2"
            shift 2
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
            echo "  --skip-build       Skip building the image"
            echo "  --skip-frontend    Skip frontend asset download (for testing other issues)"
            echo "  --use-fallback     Pre-populate fallback tarball for testing (deprecated)"
            echo "  --mount-public     Mount /app/public as writable volume (deprecated)"
            echo "  --frontend-dir DIR Mount local frontend build directory (for REPL)"
            echo "  --podman           Use podman instead of docker"
            echo "  --docker           Use docker (default)"
            echo "  -h, --help         Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                                          # Full build with baked-in frontend"
            echo "  $0 --skip-build                             # Just run existing image"
            echo "  $0 --frontend-dir ../swedeb_frontend/dist   # Mount local frontend (REPL)"
            echo "  $0 --podman --skip-build                    # Quick test with Podman"
            echo ""
            echo "Note: --use-fallback and --mount-public are deprecated since frontend"
            echo "      is now baked into the image during build. Use --frontend-dir for"
            echo "      local development with hot-reload of frontend changes."
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

# Setup test data directories (for sample data, not frontend)
log "Setting up test data directories..."
mkdir -p test-data

# Prepare volume mounts
VOLUME_ARGS=()

# Mount local frontend directory if specified (for REPL development)
if [ -n "$FRONTEND_DIR" ]; then
    if [ ! -d "$FRONTEND_DIR" ]; then
        log_error "Frontend directory not found: $FRONTEND_DIR"
        exit 1
    fi
    if [ ! -f "$FRONTEND_DIR/index.html" ]; then
        log_warning "Frontend directory exists but index.html not found"
        log_warning "Make sure to build the frontend first!"
    fi
    log "Mounting local frontend directory: $FRONTEND_DIR"
    VOLUME_ARGS+=(-v "$(realpath "$FRONTEND_DIR"):/app/public:Z")
fi

# Legacy fallback support (deprecated)
if [ "$USE_FALLBACK" = true ]; then
    log_warning "--use-fallback is deprecated (frontend now baked into image)"
fi

if [ "$MOUNT_PUBLIC" = true ]; then
    log_warning "--mount-public is deprecated (use --frontend-dir instead)"
    if [ -z "$FRONTEND_DIR" ]; then
        chmod 755 test-data/public 2>/dev/null || true
        VOLUME_ARGS+=(-v "$(pwd)/test-data/public:/app/public:Z")
    fi
fi

# Prepare environment variables
ENV_ARGS=()
ENV_ARGS+=(-e "CORPUS_REGISTRY=/data/registry")

# Note: FRONTEND_VERSION no longer needed since frontend is baked into image

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
