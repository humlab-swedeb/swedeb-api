#!/usr/bin/env bash
set -euo pipefail

usage() {
  local message="${1:-}"

  if [[ "$message" != "" ]]; then
    echo "error: $message" >&2
  fi
  cat >&2 <<USAGE
usage: $(basename "$0") <target environment> [options]

Deploys the swedeb-api container to the specified environment by:
  - Pulling the specified image from GHCR
  - Reinstalling the quadlet (systemd user container) deployment
  - Restarting the service under the environment-specific service user

By default, the script connects to the deployment host over SSH and runs the deployment there.
With --local-deploy, it runs the same steps locally (useful when already on the server).

arguments:
  <target environment>   staging | production

options:
  --image-tag <tag>      Image tag to deploy (defaults to environment name)
                         Required for production deployments
  --local-deploy         Run deployment locally instead of via SSH

requirements:
  - Environment file: ~/.vault/.swedeb-<env>.env
  - Required variables:
      SWEDEB_DEPLOY_HOST
      SWEDEB_DEPLOY_SUDO_SECRET
      SWEDEB_DEPLOY_USER (optional)
      SWEDEB_DEPLOY_SERVICE_USER (optional)
  - Env file must have permissions: 600

examples:
  $(basename "$0") staging
  $(basename "$0") production --image-tag v1.2.3
  $(basename "$0") staging --local-deploy

notes:
  - This script does NOT deploy new configuration files or containers definitions.
    It only pulls a new image and recreates the existing quadlet setup.
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
    usage "Invalid target environment: $g_target_environment"
    ;;
esac

g_image_tag=""
g_local_deploy=false

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
    --local-deploy)
      g_local_deploy=true
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
g_deploy_service_user="swedeb_$g_target_environment"

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

if [[ "$g_local_deploy" == true ]]; then
  g_host="$(hostname -f 2>/dev/null || hostname)"
  g_deploy_user="${USER:?Missing local USER}"
else
  g_host="${SWEDEB_DEPLOY_HOST:-${g_host:-}}"
  g_deploy_user="${SWEDEB_DEPLOY_USER:-${g_deploy_user:-${USER:?Missing local USER}}}"
fi

g_deploy_service_user="${SWEDEB_DEPLOY_SERVICE_USER:-${g_deploy_service_user:-swedeb_staging}}"
g_secret="${SWEDEB_DEPLOY_SUDO_SECRET:-${g_secret:-}}"

: "${g_host:?Missing deployment host}"
: "${g_secret:?Missing sudo secret}"
: "${g_deploy_service_user:?Missing deploy service user}"

echo "info: deploying image tag '$g_image_tag' to $g_target_environment..."
echo "note: new container files or configuration changes are not deployed..."

g_remote_script="$(cat <<REMOTE_SCRIPT
set -euo pipefail

deploy_user="$g_deploy_service_user"
deploy_uid="\$(id -u "\$deploy_user")"
runtime_dir="/run/user/\$deploy_uid"

cd "/srv/\$deploy_user"

sudo -n -u "\$deploy_user" \\
  XDG_RUNTIME_DIR="\$runtime_dir" \\
  DBUS_SESSION_BUS_ADDRESS="unix:path=\$runtime_dir/bus" \\
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
)"

if [[ "$g_local_deploy" == true ]]; then
  printf '%s\n%s\n' "$g_secret" "$g_remote_script" |
    sudo -S -p "" bash -s
else
  printf '%s\n%s\n' "$g_secret" "$g_remote_script" |
    ssh \
      -T \
      -o BatchMode=yes \
      -o ConnectTimeout=10 \
      "$g_deploy_user@$g_host" \
      'sudo -S -p "" bash -s'
fi