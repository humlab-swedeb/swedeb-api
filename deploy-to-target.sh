#!/usr/bin/env bash
set -euo pipefail

usage() {
  local message="${1:-}"

  if [[ "$message" != "" ]]; then
    echo "error: $message" >&2
  fi
  cat >&2 <<USAGE
usage: $(basename "$0") <target environment> [--image-tag <tag>]

target environment must be one of: staging, production
production deployments require --image-tag
USAGE
  exit 2
}

if [[ $# -lt 1 ]]; then
  usage "Missing target environment"
fi

g_target_environment="$1"
shift

case "$g_target_environment" in
  staging | production) ;;
  *)
    usage "Invalid target environment: $g_target_environment" >&2
    ;;
esac

g_image_tag=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-tag)
      if [[ $# -lt 2 || "$2" == "" ]]; then
        usage "Missing value for --image-tag"
      fi
      g_image_tag="$2"
      shift 2
      ;;
    --image-tag=*)
      g_image_tag="${1#--image-tag=}"
      if [[ "$g_image_tag" == "" ]]; then
        usage "Missing value for --image-tag"
      fi
      shift
      ;;
    *)
      usage "Unexpected argument: $1"
      ;;
  esac
done

if [[ "$g_target_environment" == "production" && "$g_image_tag" == "" ]]; then
  usage "Production deployments require --image-tag"
fi

if [[ "$g_image_tag" == "" ]]; then
  g_image_tag="$g_target_environment"
fi

if [[ ! "$g_image_tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  usage "Invalid image tag: $g_image_tag"
fi

echo "Deploying $g_target_environment..."

g_env_file="${HOME}/.vault/.swedeb-$g_target_environment.env"
g_deploy_service_user=swedeb_$g_target_environment

if [[ ! -f "$g_env_file" ]]; then
  echo "Missing $g_target_environment env file: $g_env_file" >&2
  echo "Expected variables: SWEDEB_DEPLOY_HOST and SWEDEB_DEPLOY_SUDO_SECRET" >&2
  exit 1
fi

if [[ "$(stat -c %a "$g_env_file")" != "600" ]]; then
  echo "$g_target_environment env file must be readable only by you: chmod 600 $g_env_file" >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$g_env_file"
set +a

g_host="${SWEDEB_DEPLOY_HOST:-${g_host:-}}"
g_deploy_user="${SWEDEB_DEPLOY_USER:-${g_deploy_user:-${USER:?Missing local USER}}}"
g_deploy_service_user="${SWEDEB_DEPLOY_SERVICE_USER:-${g_deploy_service_user:-swedeb_staging}}"
g_secret="${SWEDEB_DEPLOY_SUDO_SECRET:-${g_secret:-}}"

: "${g_host:?Missing deployment host}"
: "${g_secret:?Missing sudo secret}"
: "${g_deploy_service_user:?Missing deploy service user}"

echo "info: deploying image tag '$g_image_tag' to $g_target_environment..."
echo "note: new container files or configuration changes are not deployed..."

{
  printf '%s\n' "$g_secret"

  cat <<REMOTE_SCRIPT
set -euo pipefail

deploy_user="$g_deploy_service_user"
deploy_uid="\$(id -u "\$deploy_user")"
runtime_dir="/run/user/\$deploy_uid"

cd "/srv/\$deploy_user"

sudo -n -u "\$deploy_user" \
  XDG_RUNTIME_DIR="\$runtime_dir" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=\$runtime_dir/bus" \
  bash -lc '
set -euo pipefail

echo "Pulling $g_target_environment image..."
podman pull ghcr.io/humlab-swedeb/swedeb-api:$g_image_tag

echo "Recreating quadlet deployment..."
printf "y" | manage-quadlet remove
manage-quadlet install

echo "Done."
'
REMOTE_SCRIPT
} | ssh \
  -T \
  -o BatchMode=yes \
  -o ConnectTimeout=10 \
  "$g_deploy_user@$g_host" \
  'sudo -S -p "" bash -s'
