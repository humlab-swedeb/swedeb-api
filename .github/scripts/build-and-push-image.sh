#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
DOCKER_DIR="${REPO_ROOT}/docker"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

cd "${REPO_ROOT}"

VERSION=$1
if [ -z "$VERSION" ]; then
  log "ERROR: Version argument is missing!"
  exit 1
fi

ENVIRONMENT=${2:-production}
if [[ ! "$ENVIRONMENT" =~ ^(test|staging|production)$ ]]; then
  log "ERROR: Environment must be 'test', 'staging', or 'production'. Got: $ENVIRONMENT"
  exit 1
fi

SKIP_PUSH=${SKIP_PUSH:-0}

# Detect Git branch for auto-detection of frontend version
# Priority: GITHUB_REF_NAME (CI), git command (local), ENVIRONMENT fallback
if [ -n "${GITHUB_REF_NAME:-}" ]; then
  GIT_BRANCH="${GITHUB_REF_NAME}"
elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
else
  # Fallback: derive from environment
  case "$ENVIRONMENT" in
    test) GIT_BRANCH="test" ;;
    staging) GIT_BRANCH="staging" ;;
    production) GIT_BRANCH="main" ;;
    *) GIT_BRANCH="main" ;;
  esac
fi

log "Detected Git branch: ${GIT_BRANCH}"

if [ -n "${IMAGE_NAME_OVERRIDE:-}" ]; then
  IMAGE_NAME="${IMAGE_NAME_OVERRIDE}"
elif [ -n "${GITHUB_REPOSITORY:-}" ]; then
  IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"
elif [ "$SKIP_PUSH" = "1" ]; then
  IMAGE_NAME="swedeb-api"
else
  log "ERROR: GITHUB_REPOSITORY is required unless IMAGE_NAME_OVERRIDE is set or SKIP_PUSH=1"
  exit 1
fi

log "Building ${ENVIRONMENT} image for version ${VERSION}"
log "Note: Frontend assets will be downloaded at container runtime from GitHub releases"
if [ "$SKIP_PUSH" = "1" ]; then
  log "SKIP_PUSH=1, skipping registry login and image push"
else
  log "Logging into GitHub Container Registry..."

  if [ -n "${CWB_REGISTRY_TOKEN:-}" ]; then
    log "Using cross-org registry token for build and push..."
    echo "${CWB_REGISTRY_TOKEN}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
  else
    log "Using standard GitHub token..."
    echo "${DOCKER_PASSWORD}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
  fi
fi

# Build wheel in docker/wheels directory
log "Building Python wheel..."
mkdir -p "${DOCKER_DIR}/wheels"
uv build --wheel --out-dir "${DOCKER_DIR}/wheels"

pushd "${DOCKER_DIR}" > /dev/null

# Extract version components
MAJOR_VERSION=$(echo ${VERSION} | cut -d. -f1)
MINOR_VERSION=$(echo ${VERSION} | cut -d. -f1-2)

# Build with environment-specific tags
if [ "$ENVIRONMENT" = "test" ]; then
  log "Building test image with tags: ${VERSION}-test, test, test-latest"
  docker build \
    --build-arg GIT_BRANCH="${GIT_BRANCH}" \
    --tag "${IMAGE_NAME}:${VERSION}-test" \
    --tag "${IMAGE_NAME}:test" \
    --tag "${IMAGE_NAME}:test-latest" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}-test, test, test-latest"
elif [ "$ENVIRONMENT" = "staging" ]; then
  log "Building staging image with tags: ${VERSION}-staging, staging"
  docker build \
    --build-arg GIT_BRANCH="${GIT_BRANCH}" \
    --tag "${IMAGE_NAME}:${VERSION}-staging" \
    --tag "${IMAGE_NAME}:staging" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}-staging, staging"
else
  log "Building production image with tags: ${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
  docker build \
    --build-arg GIT_BRANCH="${GIT_BRANCH}" \
    --tag "${IMAGE_NAME}:${VERSION}" \
    --tag "${IMAGE_NAME}:${MAJOR_VERSION}" \
    --tag "${IMAGE_NAME}:${MINOR_VERSION}" \
    --tag "${IMAGE_NAME}:latest" \
    --tag "${IMAGE_NAME}:production" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
fi

popd > /dev/null

# Clean up wheel directory
rm -rf "${DOCKER_DIR}/wheels"

if [ "$SKIP_PUSH" = "1" ]; then
  log "✅ Successfully built tags without pushing: ${TAGS}"
  exit 0
fi

# Push all tags
docker push --all-tags "${IMAGE_NAME}"

log "✅ Successfully pushed tags: ${TAGS}"
