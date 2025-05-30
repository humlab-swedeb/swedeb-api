SHELL:=/bin/bash

#BUILD_ENV ?= staging

# check if BUILD_ENV is production or staging
ifeq ($(BUILD_ENV),production)
$(info SWEDEB_ENVIRONMENT set to production)
else ifeq ($(BUILD_ENV),staging)
$(info SWEDEB_ENVIRONMENT set to staging)
else
$(info usage: make -e BUILD_ENV=staging|production.)
$(error BUILD_ENV must be set to either 'staging' or 'production')
endif

# check if file "./compose/$(BUILD_ENV)/.env" exists
ifeq (,$(wildcard ./compose/$(BUILD_ENV)/.env))
$(error ./compose/$(BUILD_ENV)/.env not found!)
endif

include ./compose/$(BUILD_ENV)/.env
export

.DEFAULT_GOAL=help

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Primary targets:"
	@echo "  help              - Show this help"
	@echo "  image             - Build frontend, backend and image"
	@echo "Secondary targets:"
	@echo "  frontend          - Build frontend application and copy dist to ./public folder"
	@echo "  backend           - Build backend if SWEDEB_BACKEND_TAG isn't a semver version, and not 'workdir' or branch or tag"
	@echo "  bash              - Run bash in container"
	@echo "  add-host-user     - Add host user"
	@echo "  tools             - Install tools"
	@echo ""
	@echo "Environment variables:"
	@echo "  SWEDEB_ENVIRONMENT: the current environment (development, staging, production)"
	@echo "  SWEDEB_BACKEND_TAG: the backend version to deploy (branch, tag, commit, or 'workdir')"
	@echo "  SWEDEB_FRONTEND_TAG: the frontend to version deploy (branch, tag, commit)"
	@echo "  SWEDEB_IMAGE_NAME: the base image name"
	@echo "  SWEDEB_CONTAINER_NAME: the running container name (SWEDEB_ENVIRONMENT will be appended)"
	@echo "  SWEDEB_IMAGE_TAG: the target docker image tag (staging or latest)"
	@echo "  SWEDEB_PORT: the port to expose the container on"
	@echo "  SWEDEB_HOST_PORT: the host port to expose the container on"
	@echo "  SWEDEB_SUBNET: the subnet to use for the container"
	@echo "  SWEDEB_DATA_FOLDER: the data folder to mount into the container"
	@echo "  SWEDEB_CONFIG_PATH: the config file to mount into the container"
	@echo ""
	@echo "Current environment values:"
	@echo "  SWEDEB_ENVIRONMENT=$${SWEDEB_ENVIRONMENT}"
	@echo "  SWEDEB_BACKEND_TAG=$${SWEDEB_BACKEND_TAG}"
	@echo "  SWEDEB_FRONTEND_TAG=$${SWEDEB_FRONTEND_TAG}"
	@echo "  SWEDEB_IMAGE_NAME=$${SWEDEB_IMAGE_NAME}"
	@echo "  SWEDEB_CONTAINER_NAME=$${SWEDEB_CONTAINER_NAME}"
	@echo "  SWEDEB_IMAGE_TAG=$${SWEDEB_IMAGE_TAG}"
	@echo "  SWEDEB_PORT=$${SWEDEB_PORT}"
	@echo "  SWEDEB_HOST_PORT=$${SWEDEB_HOST_PORT}"
	@echo "  SWEDEB_SUBNET=$${SWEDEB_SUBNET}"
	@echo "  SWEDEB_DATA_FOLDER=$${SWEDEB_DATA_FOLDER}"
	@echo "  SWEDEB_CONFIG_PATH=$${SWEDEB_CONFIG_PATH}"


ifndef SWEDEB_BACKEND_TAG
 $(error SWEDEB_BACKEND_TAG is undefined)
endif

ifndef SWEDEB_FRONTEND_TAG
 $(error SWEDEB_FRONTEND_TAG is undefined)
endif

.PHONY: build frontend backend create-tmpdir

SHA_FILE = public/.frontend_last_built_sha
FRONTEND_REPO = https://github.com/humlab-swedeb/swedeb_frontend.git
BACKEND_REPO = https://github.com/humlab-swedeb/swedeb-api.git
TMPDIR_BUILD := /tmp/swedeb-build-${USER}

.ONESHELL: frontend
.PHONY: frontend
frontend: create-tmpdir
	@echo "Checking for updates on branch $(SWEDEB_FRONTEND_TAG)..."
	@LATEST_SHA=$$(git ls-remote $(FRONTEND_REPO) refs/heads/$(SWEDEB_FRONTEND_TAG) | awk '{print $$1}'); \
	if [ "$(SWEDEB_FRONTEND_TAG)" == "workdir" ]; then \
		frontend_folder=$(shell find "$$HOME" -type d -path '*/swedeb_frontend/.git' -printf '%h\n' 2>/dev/null); \
		echo "Using local swedeb_frontend at $$frontend_folder"; \
		pushd "$$frontend_folder" > /dev/null \
			&& pnpm install \
			&& pnpm build \
			&& popd > /dev/null \
			&& rm -rf public \
			&& mv -f $$frontend_folder/dist/spa public \
			&& rm -rf $(TMPDIR_BUILD); \
	elif [ ! -f $(SHA_FILE) ] || [ "$$(cat $(SHA_FILE))" != "$$LATEST_SHA" ]; then \
		echo "Changes detected on branch $(SWEDEB_FRONTEND_TAG). Building frontend..."; \
		pushd . > /dev/null && \
		cd $(TMPDIR_BUILD) && \
		git clone $(FRONTEND_REPO) --branch $(SWEDEB_FRONTEND_TAG) --depth 1 && \
		cd swedeb_frontend && \
		pnpm install && \
		pnpm build && \
		popd > /dev/null && \
		rm -rf public && \
		mv -f $(TMPDIR_BUILD)/swedeb_frontend/dist/spa public && \
		rm -rf $(TMPDIR_BUILD); \
		echo "$$LATEST_SHA" > $(SHA_FILE); \
	else \
		echo "No changes detected on branch $(SWEDEB_FRONTEND_TAG). Skipping frontend build."; \
	fi

.ONESHELL: backend
.PHONY: backend
backend:
	@echo "Determining backend build method for $(SWEDEB_BACKEND_TAG)..."
	@if [ "$(SWEDEB_BACKEND_TAG)" == "workdir" ]; then \
		echo "Building backend API using $(SWEDEB_BACKEND_TAG)..."; \
		cd .. && \
		poetry build && \
		rm -rf docker/dist && \
		mv -f dist docker/ && \
		cd docker; \
	elif echo "$(SWEDEB_BACKEND_TAG)" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Using backend from PyPi api_swedeb-$(SWEDEB_BACKEND_TAG)-py3-none-any.whl"; \
	else \
		echo "Building backend API using $(SWEDEB_BACKEND_TAG)..."; \
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

guard-production:
	@if [ "$(SWEDEB_ENVIRONMENT)" == "production" ]; then \
		read -p "You are about to deploy to PRODUCTION. Are you sure you want to proceed? (y/n) " confirm; \
		if [[ $$confirm == [yY] ]]; then \
			echo "Proceeding with the task..."; \
		else \
			echo "Build task aborted by user."; \
			exit 1; \
		fi \
	fi
	
.PHONY: image
.ONESHELL: image
image: guard-production backend frontend
	@echo "Building $${SWEDEB_ENVIRONMENT^^} image using $(SWEDEB_BACKEND_TAG)..."
	@docker build \
		--build-arg SWEDEB_PORT=$(SWEDEB_PORT) \
		--build-arg SWEDEB_BACKEND_TAG=$(SWEDEB_BACKEND_TAG) \
		-t $(SWEDEB_IMAGE_NAME):$(SWEDEB_IMAGE_TAG) \
		-t $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG) \
		-f ./Dockerfile .
	@echo "Done building image $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG)"

.PHONY: create-tmpdir
create-tmpdir:
	@rm -rf $(TMPDIR_BUILD) dist && mkdir -p $(TMPDIR_BUILD) dist

.PHONY: run-bash
run-bash:
	@echo docker run -it --rm \
	  --volume "$(HOST_DATA_FOLDER):/data" \
      --volume "$(CONFIG_FILENAME):/data/config/config.yml" \
	  --env-file ./compose/$(BUILD_ENV)/.env \
	  --entrypoint /bin/bash \
	  swedeb-api:$(SWEDEB_BACKEND_TAG)

.PHONY: bash
bash:
	@docker exec -it swedeb-api-$(SWEDEB_ENVIRONMENT) /bin/bash

.PHONY: logs
logs:
	@docker logs swedeb-api-$(SWEDEB_ENVIRONMENT) --follow

.PHONY: add-host-user
add-host-user:
	@if [ "$(shell getent passwd swedeb && echo FOO)" != "FOO" ]; then \
		sudo addgroup --gid 2021 swedeb \
		  && sudo adduser --no-create-home --disabled-login --gecos '' --uid 2021 --gid 1006 swedeb \
		  && echo "info: user swedeb created." ; \
	fi

.PHONY: tools
tools:
	@curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
	@wget -qO- https://get.pnpm.io/install.sh | sh -
	@source ~/.bashrc
	@nvm install node

.PHONY: up
up: guard-production
	@docker compose -f ./compose/$(BUILD_ENV)/docker-compose.yml up -d

.PHONY: down
down: guard-production
	@docker compose -f ./compose/$(BUILD_ENV)/docker-compose.yml down

.PHONY: restart
restart: guard-production down up
	@echo daemon started

