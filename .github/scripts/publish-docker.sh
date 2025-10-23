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

# Example: ghcr.io/humlab-swedeb/swedeb-api
IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"
FRONTEND_IMAGE_BASE="ghcr.io/humlab-swedeb/swedeb_frontend"
FRONTEND_VERSION=${FRONTEND_VERSION_TAG:-latest}

log "Logging into GitHub Container Registry..."

# Use CWB_REGISTRY_TOKEN if available (has cross-org read access), otherwise use DOCKER_PASSWORD
if [ -n "${CWB_REGISTRY_TOKEN}" ]; then
  log "Using cross-org registry token for build and push..."
  echo "${CWB_REGISTRY_TOKEN}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
else
  log "Using standard GitHub token..."
  echo "${DOCKER_PASSWORD}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin
fi

log "Building and pushing Docker image for version ${VERSION}..."
log "Using frontend image: ${FRONTEND_IMAGE_BASE}:${FRONTEND_VERSION}"

pushd docker > /dev/null

docker build \
  --build-arg "FRONTEND_VERSION=${FRONTEND_VERSION}" \
  --tag "${IMAGE_NAME}:${VERSION}" \
  --tag "${IMAGE_NAME}:latest" \
  --tag "${IMAGE_NAME}:$(echo ${VERSION} | cut -d. -f1-2)" \
  --tag "${IMAGE_NAME}:$(echo ${VERSION} | cut -d. -f1)" \
    -f ./Dockerfile .

popd > /dev/null

docker push --all-tags "${IMAGE_NAME}"

log "Successfully pushed tags: ${VERSION}, ${MAJOR_VERSION}, ${MINOR_VERSION}, latest, production"
