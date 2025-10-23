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

IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"
FRONTEND_IMAGE_BASE="ghcr.io/humlab-swedeb/swedeb_frontend"
FRONTEND_VERSION=${FRONTEND_VERSION_TAG:-latest}

log "Building ${ENVIRONMENT} image for version ${VERSION}"
log "Logging into GitHub Container Registry..."

if [ -n "${CWB_REGISTRY_TOKEN:-}" ]; then
  log "Using cross-org registry token for build and push..."
  echo "${CWB_REGISTRY_TOKEN}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
else
  log "Using standard GitHub token..."
  echo "${DOCKER_PASSWORD}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
fi

log "Using frontend image: ${FRONTEND_IMAGE_BASE}:${FRONTEND_VERSION}"

pushd docker > /dev/null

# Extract version components
MAJOR_VERSION=$(echo ${VERSION} | cut -d. -f1)
MINOR_VERSION=$(echo ${VERSION} | cut -d. -f1-2)

# Build with environment-specific tags
if [ "$ENVIRONMENT" = "staging" ]; then
  log "Building staging image with tags: ${VERSION}-staging, staging, dev-latest"
  docker build \
    --build-arg "FRONTEND_VERSION=${FRONTEND_VERSION}" \
    --tag "${IMAGE_NAME}:${VERSION}-staging" \
    --tag "${IMAGE_NAME}:staging" \
    --tag "${IMAGE_NAME}:dev-latest" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}-staging, staging, dev-latest"
else
  log "Building production image with tags: ${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
  docker build \
    --build-arg "FRONTEND_VERSION=${FRONTEND_VERSION}" \
    --tag "${IMAGE_NAME}:${VERSION}" \
    --tag "${IMAGE_NAME}:${MAJOR_VERSION}" \
    --tag "${IMAGE_NAME}:${MINOR_VERSION}" \
    --tag "${IMAGE_NAME}:latest" \
    --tag "${IMAGE_NAME}:production" \
    -f ./Dockerfile .
  
  TAGS="${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
fi

popd > /dev/null

# Push all tags
docker push --all-tags "${IMAGE_NAME}"

log "✅ Successfully pushed tags: ${TAGS}"
