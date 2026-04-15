#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

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

IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"

log "Building ${ENVIRONMENT} image for version ${VERSION}"
log "Note: Frontend assets will be downloaded at container runtime from GitHub releases"
log "Logging into GitHub Container Registry..."

if [ -n "${CWB_REGISTRY_TOKEN:-}" ]; then
  log "Using cross-org registry token for build and push..."
  echo "${CWB_REGISTRY_TOKEN}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
else
  log "Using standard GitHub token..."
  echo "${DOCKER_PASSWORD}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
fi

# Build wheel in docker/wheels directory
log "Building Python wheel..."
mkdir -p docker/wheels
uv build --wheel --out-dir docker/wheels

pushd docker > /dev/null

# Extract version components
MAJOR_VERSION=$(echo ${VERSION} | cut -d. -f1)
MINOR_VERSION=$(echo ${VERSION} | cut -d. -f1-2)

# Build with environment-specific tags
if [ "$ENVIRONMENT" = "test" ]; then
  log "Building test image with tags: ${VERSION}-test, test, test-latest"
  docker build \
    --tag "${IMAGE_NAME}:${VERSION}-test" \
    --tag "${IMAGE_NAME}:test" \
    --tag "${IMAGE_NAME}:test-latest" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}-test, test, test-latest"
elif [ "$ENVIRONMENT" = "staging" ]; then
  log "Building staging image with tags: ${VERSION}-staging, staging"
  docker build \
    --tag "${IMAGE_NAME}:${VERSION}-staging" \
    --tag "${IMAGE_NAME}:staging" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}-staging, staging"
else
  log "Building production image with tags: ${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
  docker build \
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
rm -rf docker/wheels

# Push all tags
docker push --all-tags "${IMAGE_NAME}"

log "✅ Successfully pushed tags: ${TAGS}"
