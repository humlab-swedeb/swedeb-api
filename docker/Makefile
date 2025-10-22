SHELL := /bin/bash

###################################################################################################
# Detect whether to use podman or docker
###################################################################################################
ifeq (, $(shell command -v podman 2>/dev/null))
  CONTAINER_CMD := docker
else
  CONTAINER_CMD := podman
endif
$(info Using container command: $(CONTAINER_CMD))

###################################################################################################
# BUILD_ENV check (must be 'production' or 'staging')
###################################################################################################

ifeq ($(filter help apa tools,$(MAKECMDGOALS)),)
  ifeq ($(BUILD_ENV),production)
    $(info SWEDEB_ENVIRONMENT set to production)
  else ifeq ($(BUILD_ENV),staging)
    $(info SWEDEB_ENVIRONMENT set to staging)
  else
    $(info usage: make -e BUILD_ENV=staging|production.)
    $(error BUILD_ENV must be set to either 'staging' or 'production')
  endif
  ifeq (,$(wildcard ./compose/$(BUILD_ENV)/.env))
    $(error ./compose/$(BUILD_ENV)/.env not found!)
  endif
  include ./compose/$(BUILD_ENV)/.env
  export
  ifndef SWEDEB_BACKEND_TAG
    $(error SWEDEB_BACKEND_TAG is undefined)
  endif
  ifndef SWEDEB_FRONTEND_TAG
    $(error SWEDEB_FRONTEND_TAG is undefined)
  endif
else
BUILD_ENV:=staging
endif

include ./.env
export

###################################################################################################
# Publish the image to the GHCR registry
###################################################################################################
.PHONY: ghcr-image
ghcr-image: backend
	@echo "Building image $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG) for GHCR…"
	@$(CONTAINER_CMD) build \
		--build-arg SWEDEB_PORT=$(SWEDEB_PORT) \
		--build-arg SWEDEB_BACKEND_TAG=$(SWEDEB_BACKEND_TAG) \
		--build-arg SWEDEB_FRONTEND_TAG=$(SWEDEB_FRONTEND_TAG) \
		-t $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG) \
		-f ./Dockerfile .

###################################################################################################
# Backend build target (development target)
###################################################################################################
.ONESHELL: backend
.PHONY: backend
backend:
	@echo "Determining backend build method for $(SWEDEB_BACKEND_TAG)..."
	@if [ "$(SWEDEB_BACKEND_SOURCE)" == "workdir" ]; then \
		echo "Building backend API using $(SWEDEB_BACKEND_TAG) from workdir..."; \
		poetry build --directory .. --output docker/dist ; \
	elif [ "$(SWEDEB_BACKEND_SOURCE)" == "pypi" ]; then \
		echo "Using backend from PyPi api_swedeb-$(SWEDEB_BACKEND_TAG)-py3-none-any.whl"; \
	elif [ "$(SWEDEB_BACKEND_SOURCE)" == "git" ]; then \
		echo "Building backend API using git tag $(SWEDEB_BACKEND_TAG)..."; \
		pushd . > /dev/null && \
		mkdir -p $(TMPDIR_BUILD) && cd $(TMPDIR_BUILD) && \
		git clone $(BACKEND_REPO) --branch $(SWEDEB_BACKEND_TAG) --depth 1 && \
		cd swedeb-api && \
		poetry build && \
		popd > /dev/null && \
		rm -rf dist && \
		mv -f $(TMPDIR_BUILD)/swedeb-api/dist dist && \
		rm -rf $(TMPDIR_BUILD); \
	fi

###################################################################################################
# Help target
###################################################################################################
.DEFAULT_GOAL := help
.PHONY: help
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Primary targets:"
	@echo "  help              - Show this help"
	@echo "  image             - Build frontend, backend and image"
	@echo ""
	@echo "Secondary targets:"
	@echo "  frontend          - Build frontend application and copy dist to ./public folder"
	@echo "  backend           - Build backend if SWEDEB_BACKEND_TAG isn't a semver version, and not 'workdir' or branch or tag"
	@echo "  run-bash          - Run bash in container"
	@echo "  bash              - Exec bash in running container"
	@echo "  logs              - Follow logs of running container"
	@echo "  add-host-user     - Add host user 'swedeb'"
	@echo "  tools             - Install development tools (nvm, pnpm, etc.)"
	@echo "  up                - Bring up services via compose"
	@echo "  down              - Tear down services via compose"
	@echo "  restart           - Restart services (down → up)"
	@echo "  install-systemd   - Install systemd unit (Podman only)"
	@echo ""
	@echo "Environment variables:"
	@echo "  SWEDEB_ENVIRONMENT: the current environment (staging, production)"
	@echo "  SWEDEB_BACKEND_TAG: the backend version to deploy (branch, tag, commit, or 'workdir')"
	@echo "  SWEDEB_BACKEND_SOURCE: where to get backend ('workdir', 'pypi', or 'git')"
	@echo "  SWEDEB_FRONTEND_TAG: the frontend version to deploy (branch, tag, commit, or 'workdir')"
	@echo "  SWEDEB_IMAGE_NAME: the base image name"
	@echo "  SWEDEB_CONTAINER_NAME: the running container name (SWEDEB_ENVIRONMENT will be appended)"
	@echo "  SWEDEB_IMAGE_TAG: the target image tag (staging or backend-tag)"
	@echo "  SWEDEB_PORT: the port to expose the container on (inside)"
	@echo "  SWEDEB_HOST_PORT: the host port to expose the container on"
	@echo "  SWEDEB_SUBNET: the subnet to use for the container network"
	@echo "  SWEDEB_DATA_FOLDER: the data folder to mount into the container"
	@echo "  SWEDEB_CONFIG_PATH: the config file to mount into the container"
	@echo ""
	@echo "Current environment values:"
	@echo "  BUILD_ENV=$(BUILD_ENV)"
	@echo "  SWEDEB_ENVIRONMENT=$${SWEDEB_ENVIRONMENT}"
	@echo "  SWEDEB_BACKEND_TAG=$${SWEDEB_BACKEND_TAG}"
	@echo "  SWEDEB_BACKEND_SOURCE=$${SWEDEB_BACKEND_SOURCE}"
	@echo "  SWEDEB_FRONTEND_TAG=$${SWEDEB_FRONTEND_TAG}"
	@echo "  SWEDEB_IMAGE_NAME=$${SWEDEB_IMAGE_NAME}"
	@echo "  SWEDEB_CONTAINER_NAME=$${SWEDEB_CONTAINER_NAME}"
	@echo "  SWEDEB_IMAGE_TAG=$${SWEDEB_IMAGE_TAG}"
	@echo "  SWEDEB_PORT=$${SWEDEB_PORT}"
	@echo "  SWEDEB_HOST_PORT=$${SWEDEB_HOST_PORT}"
	@echo "  SWEDEB_SUBNET=$${SWEDEB_SUBNET}"
	@echo "  SWEDEB_DATA_FOLDER=$${SWEDEB_DATA_FOLDER}"
	@echo "  SWEDEB_CONFIG_PATH=$${SWEDEB_CONFIG_PATH}"


###################################################################################################
# Guard against production without confirmation
###################################################################################################
.PHONY: guard-production
guard-production:
	@if [ "$(SWEDEB_ENVIRONMENT)" == "production" ]; then \
		read -p "You are about to deploy to PRODUCTION. Are you sure? (y/n) " confirm; \
		if [[ $$confirm == [yY] ]]; then \
			echo "Proceeding..."; \
		else \
			echo "Aborted by user."; \
			exit 1; \
		fi \
	fi

###################################################################################################
# Create temporary build directory
###################################################################################################
.PHONY: create-tmpdir
create-tmpdir:
	@rm -rf $(TMPDIR_BUILD) && mkdir -p $(TMPDIR_BUILD)

###################################################################################################
# Run a one-off bash shell in the container (without starting it)
###################################################################################################
.PHONY: run-bash
run-bash:
	@$(CONTAINER_CMD) run -it --rm \
	  --volume "$(HOST_DATA_FOLDER):/data$(shell [ "$$(getenforce 2>/dev/null)" = "Enforcing" ] && echo ":Z")" \
	  --volume "$(CONFIG_FILENAME):/data/config/config.yml$(shell [ "$$(getenforce 2>/dev/null)" = "Enforcing" ] && echo ":Z")" \
	  --env-file ./compose/$(BUILD_ENV)/.env \
	  --entrypoint /bin/bash \
	  $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG)

###################################################################################################
# Exec bash inside running container
###################################################################################################
.PHONY: bash
bash:
	@$(CONTAINER_CMD) exec -it $(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT) /bin/bash

###################################################################################################
# Follow container logs
###################################################################################################
.PHONY: logs
logs:
	@$(CONTAINER_CMD) logs $(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT) --follow

###################################################################################################
# Add host user 'swedeb' if it doesn't exist
###################################################################################################
.PHONY: add-host-user
add-host-user:
	@if [ "$$(getent passwd swedeb && echo FOO)" != "FOO" ]; then \
		sudo addgroup --gid 2021 swedeb && \
		sudo adduser --no-create-home --disabled-login --gecos '' --uid 2021 --gid 2021 swedeb && \
		echo "info: user 'swedeb' created."; \
	fi

###################################################################################################
# Install development tools (nvm, pnpm, node)
###################################################################################################
.PHONY: tools
tools:
	@curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
	@wget -qO- https://get.pnpm.io/install.sh | sh -
	@source ~/.bashrc
	@nvm install node

###################################################################################################
# Bring up services via Docker/Podman Compose
###################################################################################################
.PHONY: up
up: guard-production
	@$(CONTAINER_CMD) compose -f ./compose/$(BUILD_ENV)/compose.yml up -d

###################################################################################################
# Tear down services via Docker/Podman Compose
###################################################################################################
.PHONY: down
down: guard-production
	@$(CONTAINER_CMD) compose -f ./compose/$(BUILD_ENV)/compose.yml down

###################################################################################################
# Restart services (down → up)
###################################################################################################
.PHONY: restart
restart: guard-production down up
	@echo "Daemon restarted."

###################################################################################################
# Systemd integration (Podman only)
###################################################################################################
SYSTEMD_USER_DIR    := $(HOME)/.config/systemd/user
FULL_CONTAINER_NAME := $(SWEDEB_CONTAINER_NAME)-$(SWEDEB_ENVIRONMENT)
UNIT_NAME           := $(FULL_CONTAINER_NAME).service

.PHONY: install-systemd
install-systemd:
ifeq ($(CONTAINER_CMD),podman)
	@echo "→ Generating systemd unit for container '$(FULL_CONTAINER_NAME)'"
	@mkdir -p "$(SYSTEMD_USER_DIR)"
	@podman generate systemd --new --name "$(FULL_CONTAINER_NAME)" \
	  | sed "s/^# \\(Description=.*\\)/# \\1\n# Autogenerated by Makefile/" \
	  > "$(SYSTEMD_USER_DIR)/$(UNIT_NAME)" \
	  && echo "   → Unit written to $(SYSTEMD_USER_DIR)/$(UNIT_NAME)"
	@echo "→ Reloading user systemd daemon"
	@systemctl --user daemon-reload
	@echo "→ Enabling unit: $(UNIT_NAME)"
	@systemctl --user enable "$(UNIT_NAME)"
	@echo "→ Starting unit: $(UNIT_NAME)"
	@systemctl --user start  "$(UNIT_NAME)"
	@if [ "$(ENABLE_LINGER)" != "no" ]; then \
		echo "→ Enabling lingering for user $$(id -u)"; \
		sudo loginctl enable-linger $$(id -u) || echo "   (lingering may already be enabled)"; \
	fi
	@echo "✔ systemd integration installed. Run 'systemctl --user status $(UNIT_NAME)' to verify."
else
	@echo "install-systemd is only supported when using Podman. Current command: $(CONTAINER_CMD)"
endif

