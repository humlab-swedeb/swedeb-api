#!/bin/bash
set -ex

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Version argument is missing!"
  exit 1
fi

# Example: ghcr.io/humlab-swedeb/swedeb-api
IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}"
FRONTEND_IMAGE_BASE="ghcr.io/humlab-swedeb/swedeb_frontend"
FRONTEND_VERSION=${FRONTEND_VERSION_TAG:-latest}

echo "Logging into GitHub Container Registry..."
echo "${DOCKER_PASSWORD}" | docker login ghcr.io -u "${DOCKER_USERNAME}" --password-stdin

echo "Building and pushing Docker image for version ${VERSION}..."
echo "Using frontend image: ${FRONTEND_IMAGE_BASE}:${FRONTEND_VERSION}"

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

echo "Docker image published successfully."
