# Makefile Overview

This Makefile automates building, testing, and deploying the **SwedeB API** (and its frontend) using either **Podman** or **Docker**, and provides optional systemd integration for rootless Podman. It supports two environments: **staging** and **production**.

---

## Table of Contents

- [Makefile Overview](#makefile-overview)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Environment \& Configuration](#environment--configuration)
  - [Selecting Podman or Docker](#selecting-podman-or-docker)
  - [Available Targets](#available-targets)
    - [help](#help)
    - [frontend](#frontend)
    - [backend](#backend)
    - [guard-production](#guard-production)
    - [image](#image)
    - [run-bash](#run-bash)
    - [bash](#bash)
    - [logs](#logs)
    - [add-host-user](#add-host-user)
    - [tools](#tools)
    - [up](#up)
    - [down](#down)
    - [restart](#restart)
    - [publish](#publish)
    - [install-systemd](#install-systemd)
  - [Usage Examples](#usage-examples)
  - [Best-Practice Deployment](#best-practice-deployment)
  - [License \& Acknowledgements](#license--acknowledgements)

---

## Prerequisites

1. **Make** (GNU Make ≥ 4.0)
2. **Podman 4+** (or Docker) installed and in `$PATH`
3. **Git**, **Node.js**, **pnpm**, and **Poetry** available (for frontend/backend builds)
4. A working `compose/<environment>/.env` file (see [Environment & Configuration](#environment--configuration))
5. (Optional for systemd integration) A user-level `systemd --user` environment with lingering enabled

---

## Environment & Configuration

1. **BUILD\_ENV**

   * Must be set to `staging` or `production`.
   * The Makefile will source `./compose/$(BUILD_ENV)/.env`.

2. **compose/\$(BUILD\_ENV)/.env**
   Required variables in this file include (but are not limited to):

   ```
   SWEDEB_ENVIRONMENT      # e.g. "staging" or "production"
   SWEDEB_BACKEND_TAG      # git branch, tag, commit, or "workdir"
   SWEDEB_BACKEND_SOURCE   # one of "workdir", "pypi", or "git"
   SWEDEB_FRONTEND_TAG     # git branch, tag, commit, or "workdir-dist"/"workdir"
   SWEDEB_IMAGE_NAME       # e.g. "registry.local:5000/swedeb-api"
   SWEDEB_IMAGE_TAG        # image tag (e.g. "staging" or backend-specific)
   SWEDEB_PORT             # container port (e.g. 8092)
   SWEDEB_HOST_PORT        # host port (e.g. 8092)
   SWEDEB_SUBNET           # (optional) subnet for container network
   SWEDEB_DATA_FOLDER      # host folder to mount at /data
   SWEDEB_CONFIG_PATH      # host config file to mount (e.g. /etc/swedeb/config.yml)
   ```

   * Variables such as `SWEDEB_CONTAINER_NAME`, `SWEDEB_FRONTEND_TAG`, etc. are also expected.

3. **HOST\_DATA\_FOLDER & CONFIG\_FILENAME**

   * Used in the `run-bash` target to mount host volumes.
   * Define them in your environment or pass via `make` invocation.

---

## Selecting Podman or Docker

Upon invocation, the Makefile checks for `podman` in `$PATH`.

* If `podman` is found, all container commands (`build`, `run`, `exec`, `logs`, `compose`) use **Podman**.
* Otherwise, it falls back to **Docker**.

```makefile
ifeq (, $(shell command -v podman 2>/dev/null))
    CONTAINER_CMD := docker
else
    CONTAINER_CMD := podman
endif
$(info Using container command: $(CONTAINER_CMD))
```

As a result, you write containers commands once—prefixed by `$(CONTAINER_CMD)`—and the Makefile will automatically use the available engine.

---

## Available Targets

Below is a brief description of each Makefile target, in the order they typically appear.

### help

```
make -e BUILD_ENV=staging help
```

* Prints usage information, lists primary and secondary targets, and echoes the current environment variable values.

---

### frontend

```
make -e BUILD_ENV=staging frontend
```

* **Purpose**: Clone or use the local SwedeB frontend, build it (via `pnpm`), and place its static files under `./public`.
* **Behavior**:

  1. If `SWEDEB_FRONTEND_TAG == "workdir-dist"`, it reuses an existing `public/` folder.
  2. If `SWEDEB_FRONTEND_TAG == "workdir"`, it finds a local `swedeb_frontend` repo under `$HOME`, runs `pnpm install && pnpm build`, then moves the `dist/spa` folder to `public/`.
  3. Otherwise, it checks the latest remote SHA on `refs/heads/$(SWEDEB_FRONTEND_TAG)`.

     * If no `public/.frontend_last_built_sha` exists, or if the SHA differs, it clones `$(FRONTEND_REPO)` at `--depth 1` and builds.
     * On successful build, it writes the latest SHA to `public/.frontend_last_built_sha`.

---

### backend

```
make -e BUILD_ENV=staging backend
```

* **Purpose**: Build the backend package (Python) according to `SWEDEB_BACKEND_SOURCE`.
* **Behavior**:

  1. If `SWEDEB_BACKEND_SOURCE == "workdir"`, runs `poetry build` in the parent directory.
  2. If `SWEDEB_BACKEND_SOURCE == "pypi"`, does nothing (expects a wheel on PyPI).
  3. If `SWEDEB_BACKEND_SOURCE == "git"`, clones `$(BACKEND_REPO)` at `--depth 1`, runs `poetry build`, and moves the resulting `dist/` folder to the repo root.

---

### guard-production

```
make -e BUILD_ENV=staging guard-production
```

* **Purpose**: Prompt for confirmation if `SWEDEB_ENVIRONMENT == "production"`.
* Prevents accidental production deploys: it reads a `y/n` prompt, and aborts (`exit 1`) if the answer is not “y” or “Y”.

---

### image

```
make -e BUILD_ENV=staging image
```

* **Dependencies**: `guard-production`, `backend`, `frontend`.
* **Purpose**: Build and tag the container image using `CONTAINER_CMD build`.
* **Behavior**:

  1. Prompts if `BUILD_ENV == production`.
  2. Builds:

     ```bash
     $(CONTAINER_CMD) build \
       --build-arg SWEDEB_PORT=$(SWEDEB_PORT) \
       --build-arg SWEDEB_BACKEND_TAG=$(SWEDEB_BACKEND_TAG) \
       -t $(SWEDEB_IMAGE_NAME):$(SWEDEB_IMAGE_TAG) \
       -t $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG) \
       -f ./Dockerfile .
     ```
  3. Tags the image twice:

     * `${IMAGE_NAME}:${IMAGE_TAG}` (e.g. `swedeb-api:staging`)
     * `${IMAGE_NAME}:${BACKEND_TAG}` (e.g. `swedeb-api:v1.2.3`)

---

### run-bash

```
make -e BUILD_ENV=staging run-bash
```

* **Purpose**: Launch an interactive Bash shell in a new container (one-off), then remove it on exit.
* Uses `CONTAINER_CMD run -it --rm` with bind mounts for data/config and `--env-file`.
* Detects SELinux enforcement and appends `:Z` to volume flags if needed.
* **Note**: Prints and runs the actual command (no echo suppression). Adjust `HOST_DATA_FOLDER` and `CONFIG_FILENAME` as necessary.

---

### bash

```
make -e BUILD_ENV=staging bash
```

* **Purpose**: Attach an interactive shell to a **running** container named `$(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT)`.
* Uses `CONTAINER_CMD exec -it <container> /bin/bash`.

---

### logs

```
make -e BUILD_ENV=staging logs
```

* **Purpose**: Follow (`–follow`) the logs of the running container named `$(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT)`.
* Uses `CONTAINER_CMD logs --follow <container>`.

---

### add-host-user

```
make -e BUILD_ENV=staging add-host-user
```

* **Purpose**: Create a system user & group named `swedeb` (UID 2021, GID 2021) if it does not already exist.
* Uses `getent passwd swedeb` to check. If missing, runs:

  ```bash
  sudo addgroup --gid 2021 swedeb
  sudo adduser --no-create-home --disabled-login --gecos '' --uid 2021 --gid 2021 swedeb
  ```

---

### tools

```
make -e BUILD_ENV=staging tools
```

* **Purpose**: Install development tools used by `frontend` (Node, pnpm) via the recommended scripts.
* Steps:

  1. Install NVM (Node Version Manager).
  2. Install `pnpm`.
  3. Source `~/.bashrc` and use `nvm install node` to get the latest Node LTS.

---

### up

```
make -e BUILD_ENV=staging up
```

* **Dependencies**: `guard-production`
* **Purpose**: Launch all services defined in `./compose/$(BUILD_ENV)/compose.yml` in detached mode.
* Uses `CONTAINER_CMD compose -f … up -d`.
* If `CONTAINER_CMD == podman`, this invokes `podman compose` (Podman 4+). Otherwise, it runs `docker compose`.

---

### down

```
make -e BUILD_ENV=staging down
```

* **Dependencies**: `guard-production`
* **Purpose**: Stop and remove services defined in `compose/$(BUILD_ENV)/compose.yml`.
* Uses `CONTAINER_CMD compose -f … down`.

---

### restart

```
make -e BUILD_ENV=staging restart
```

* **Dependencies**: `guard-production`, `down`, `up`
* **Purpose**: Perform a full restart:

  1. Tear down existing services (`make down`)
  2. Bring them up again (`make up`)

---

### publish

```
make -e BUILD_ENV=staging publish
```

* **Dependencies**: `image`, .env.ghcr
* **Purpose**: Builds and pushes a new image to Github Container repository (GHCR)

  1. Build new image (`make image`)
  2. Publish new image to GHCR

The `.env.ghcr` file must contain a username and Github access token with privileges set to read/write/delete images in `humlab-swedeb` Github organization.

```.env
GHCR_USERNAME=<your-github-account>
GHCR_ACCESS_TOKEN=<your-access-token>
```

---

### install-systemd

```
make -e BUILD_ENV=staging install-systemd
```

* **Purpose**: Generate and install a systemd user-unit for the running container (Podman only).
* **Preconditions**:

  1. `CONTAINER_CMD == podman` (otherwise it prints a warning and does nothing).
  2. The container `$(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT)` must already exist (created by `make up` or `make image && podman run`).
* **Steps**:

  1. Create `$HOME/.config/systemd/user` if missing.
  2. Run:

     ```bash
     podman generate systemd --new --name $(FULL_CONTAINER_NAME)
     ```

     which prints an autogenerated unit. This is redirected to:

     ```
     ~/.config/systemd/user/$(FULL_CONTAINER_NAME).service
     ```
  3. Reload the user-level systemd daemon:

     ```bash
     systemctl --user daemon-reload
     ```
  4. Enable the new unit:

     ```bash
     systemctl --user enable $(FULL_CONTAINER_NAME).service
     ```
  5. Start the unit immediately:

     ```bash
     systemctl --user start $(FULL_CONTAINER_NAME).service
     ```
  6. (Optional) Enable lingering (if `ENABLE_LINGER != no`):

     ```bash
     sudo loginctl enable-linger $(id -u)
     ```

     This keeps your `systemd --user` alive across logouts.

Afterwards, you can check the status of your container‐as‐a‐unit via:

```bash
systemctl --user status $(FULL_CONTAINER_NAME).service
```

---

## Usage Examples

1. **Show help**

   ```bash
   make help BUILD_ENV=staging
   ```

2. **Build only the frontend**

   ```bash
   make frontend BUILD_ENV=staging
   ```

3. **Build only the backend**

   ```bash
   make backend BUILD_ENV=staging
   ```

4. **Build and tag the container image**

   ```bash
   make image BUILD_ENV=staging
   ```

5. **Run a one-off Bash shell in a new container**

   ```bash
   make run-bash BUILD_ENV=staging HOST_DATA_FOLDER=/srv/data CONFIG_FILENAME=/srv/config/config.yml
   ```

6. **Attach to a running container**

   ```bash
   make bash BUILD_ENV=staging
   ```

7. **Follow container logs**

   ```bash
   make logs BUILD_ENV=staging
   ```

8. **Deploy services with compose**

   ```bash
   make up BUILD_ENV=staging
   ```

9. **Tear down compose services**

   ```bash
   make down BUILD_ENV=staging
   ```

10. **Restart all services**

    ```bash
    make restart BUILD_ENV=staging
    ```

11. **Install systemd unit (Podman only)**

    ```bash
    make install-systemd BUILD_ENV=staging
    ```

    * This creates and enables `~/.config/systemd/user/swedeb-api-staging.service`.

---

## Best-Practice Deployment

1. **Build & Tag in CI/CD**

   * Use a dedicated build environment (e.g., GitHub Actions, GitLab CI, Jenkins) to run:

     ```bash
     make image BUILD_ENV=staging
     podman (or docker) push registry.example.com/swedeb-api:release-1.2.3
     ```
   * Push to a private registry rather than building on the production host.

2. **Pull & Run on Production**
   On the production server (with Podman installed):

   ```bash
   podman pull registry.example.com/swedeb-api:release-1.2.3
   podman run -d \
     --name swedeb-api-production \
     -p 8092:8092 \
     -v /srv/data:/data:Z \
     -v /srv/config/config.yml:/data/config/config.yml:Z \
     registry.example.com/swedeb-api:release-1.2.3
   ```

3. **Systemd Launch on Boot/Logout**

   * After pulling & running your container once, install its systemd unit:

     ```bash
     make install-systemd BUILD_ENV=production
     ```
   * Enable lingering so the container stays alive across logins:

     ```bash
     sudo loginctl enable-linger $(id -u)
     ```

4. **Rollback & Versioned Tags**

   * Tag each release uniquely (`v1.2.3`, `production-2025-06-01`, etc.).
   * In case of an emergency, pull a previous tag and restart the systemd unit:

     ```bash
     podman pull registry.example.com/swedeb-api:v1.2.2
     podman stop swedeb-api-production
     podman rm swedeb-api-production
     podman run -d --name swedeb-api-production … registry.example.com/swedeb-api:v1.2.2
     ```

By building images off-host, tagging them immutably, and pulling them on production (combined with a user-level systemd unit), you maintain a repeatable, auditable, and resilient deployment pipeline.

---

## License & Acknowledgements

* This project’s Makefile was adapted to support both Podman and Docker, with optional systemd integration for rootless Podman users.
* Portions of the underlying application rely on the SwedeB API and frontend codebases maintained by HUMlab, Umeå University.
* Feel free to adapt this Makefile for similar containerized deployments.

  *End of README*
