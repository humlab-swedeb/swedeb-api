#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
SHARED_BUILD_SCRIPT="${REPO_ROOT}/.github/scripts/build-and-push-image.sh"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

cd "${REPO_ROOT}"

VERSION=$(uv version | awk '{print $NF}')
ENVIRONMENT=${1:-staging}

if [[ ! "$ENVIRONMENT" =~ ^(test|staging|production)$ ]]; then
  log "ERROR: Environment must be 'test', 'staging', or 'production'. Got: $ENVIRONMENT"
  exit 1
fi

IMAGE_NAME_OVERRIDE=${IMAGE_NAME_OVERRIDE:-swedeb-api}

exec env \
  SKIP_PUSH=1 \
  IMAGE_NAME_OVERRIDE="${IMAGE_NAME_OVERRIDE}" \
  bash "${SHARED_BUILD_SCRIPT}" "${VERSION}" "${ENVIRONMENT}"
