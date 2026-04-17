SHELL := /bin/bash

.DEFAULT_GOAL := help

ROOT_DIR := $(abspath ..)
LOCAL_BUILD_SCRIPT := ./build-local-image.sh
CI_BUILD_SCRIPT := ../.github/scripts/build-and-push-image.sh
COMPOSE_FILE := ./compose.yml

-include ./.env
export

ENVIRONMENT ?= $(if $(BUILD_ENV),$(BUILD_ENV),$(if $(SWEDEB_ENVIRONMENT),$(SWEDEB_ENVIRONMENT),staging))
VERSION ?= $(shell cd "$(ROOT_DIR)" && uv version | awk '{print $$NF}')
IMAGE_NAME ?= $(if $(SWEDEB_IMAGE_NAME),$(SWEDEB_IMAGE_NAME),ghcr.io/humlab-swedeb/swedeb-api)
GITHUB_REPOSITORY ?= $(patsubst ghcr.io/%,%,$(IMAGE_NAME))
CONTAINER_NAME ?= $(if $(SWEDEB_CONTAINER_NAME),$(SWEDEB_CONTAINER_NAME),swedeb-api)-$(ENVIRONMENT)
SKIP_PUSH ?= 1

.PHONY: help
help:
	@echo "Usage: make [target] [ENVIRONMENT=test|staging|production]"
	@echo ""
	@echo "Build targets:"
	@echo "  image             - Build locally using docker/build-local-image.sh"
	@echo "  ci-image          - Build using the shared CI script (SKIP_PUSH=$(SKIP_PUSH) by default)"
	@echo "  push-image        - Build and push using the shared CI script"
	@echo "  ghcr-image        - Alias for ci-image"
	@echo ""
	@echo "Convenience targets:"
	@echo "  image-test        - Local test image build"
	@echo "  image-staging     - Local staging image build"
	@echo "  ci-image-test     - Shared CI-script build for test"
	@echo "  ci-image-staging  - Shared CI-script build for staging"
	@echo "  ci-image-production - Shared CI-script build for production"
	@echo ""
	@echo "Runtime targets:"
	@echo "  up                - Start the compose stack"
	@echo "  down              - Stop the compose stack"
	@echo "  restart           - Restart the compose stack"
	@echo "  logs              - Follow container logs"
	@echo "  bash              - Open a shell in the running container"
	@echo ""
	@echo "Local testing targets:"
	@echo "  test-local        - Build and test container locally (full test)"
	@echo "  test-local-podman - Test with Podman instead of Docker"
	@echo "  test-local-skip-build - Test existing image without rebuilding"
	@echo "  test-local-fallback - Test with local fallback tarball"
	@echo "  test-local-mount-public - Test with writable /app/public mount"
	@echo "  test-local-podman-fallback - Test Podman with fallback"
	@echo "  test-help         - Show test script help"
	@echo "  test-clean        - Clean up test artifacts and images"
	@echo ""
	@echo "Current values:"
	@echo "  ENVIRONMENT=$(ENVIRONMENT)"
	@echo "  VERSION=$(VERSION)"
	@echo "  IMAGE_NAME=$(IMAGE_NAME)"
	@echo "  GITHUB_REPOSITORY=$(GITHUB_REPOSITORY)"
	@echo "  CONTAINER_NAME=$(CONTAINER_NAME)"
	@echo "  SKIP_PUSH=$(SKIP_PUSH)"

.PHONY: validate-environment
validate-environment:
	@case "$(ENVIRONMENT)" in \
		test|staging|production) ;; \
		*) echo "ENVIRONMENT must be one of: test, staging, production" >&2; exit 1 ;; \
	esac

.PHONY: image
image: validate-environment
	@if [ "$(ENVIRONMENT)" = "production" ]; then \
		echo "Production builds use the shared CI script in no-push mode."; \
		SKIP_PUSH=1 IMAGE_NAME_OVERRIDE="$(IMAGE_NAME)" GITHUB_REPOSITORY="$(GITHUB_REPOSITORY)" \
			bash "$(CI_BUILD_SCRIPT)" "$(VERSION)" "$(ENVIRONMENT)"; \
	else \
		IMAGE_NAME_OVERRIDE="$(IMAGE_NAME)" bash "$(LOCAL_BUILD_SCRIPT)" "$(ENVIRONMENT)"; \
	fi

.PHONY: image-test
image-test:
	@$(MAKE) image ENVIRONMENT=test

.PHONY: image-staging
image-staging:
	@$(MAKE) image ENVIRONMENT=staging

.PHONY: ci-image ghcr-image
ci-image ghcr-image: validate-environment
	@SKIP_PUSH="$(SKIP_PUSH)" IMAGE_NAME_OVERRIDE="$(IMAGE_NAME)" GITHUB_REPOSITORY="$(GITHUB_REPOSITORY)" \
		bash "$(CI_BUILD_SCRIPT)" "$(VERSION)" "$(ENVIRONMENT)"

.PHONY: ci-image-test
ci-image-test:
	@$(MAKE) ci-image ENVIRONMENT=test

.PHONY: ci-image-staging
ci-image-staging:
	@$(MAKE) ci-image ENVIRONMENT=staging

.PHONY: ci-image-production
ci-image-production:
	@$(MAKE) ci-image ENVIRONMENT=production

.PHONY: push-image
push-image: validate-environment
	@SKIP_PUSH=0 IMAGE_NAME_OVERRIDE="$(IMAGE_NAME)" GITHUB_REPOSITORY="$(GITHUB_REPOSITORY)" \
		bash "$(CI_BUILD_SCRIPT)" "$(VERSION)" "$(ENVIRONMENT)"

.PHONY: up
up:
	@docker compose --env-file ./.env -f "$(COMPOSE_FILE)" up -d

.PHONY: down
down:
	@docker compose --env-file ./.env -f "$(COMPOSE_FILE)" down

.PHONY: restart
restart: down up

.PHONY: logs
logs:
	@docker logs --follow "$(CONTAINER_NAME)"

.PHONY: bash
bash:
	@docker exec -it "$(CONTAINER_NAME)" /bin/bash

# ====================
# Local Testing Targets
# ====================

.PHONY: test-local
test-local:
	@echo "Building and testing container locally..."
	@./test-local.sh

.PHONY: test-local-podman
test-local-podman:
	@echo "Building and testing container with Podman..."
	@CONTAINER_TOOL=podman ./test-local.sh

.PHONY: test-local-skip-build
test-local-skip-build:
	@echo "Testing existing local image..."
	@./test-local.sh --skip-build

.PHONY: test-local-fallback
test-local-fallback:
	@echo "Testing with local fallback tarball..."
	@./test-local.sh --use-fallback

.PHONY: test-local-mount-public
test-local-mount-public:
	@echo "Testing with writable /app/public mount..."
	@./test-local.sh --mount-public

.PHONY: test-local-podman-fallback
test-local-podman-fallback:
	@echo "Testing Podman with fallback..."
	@CONTAINER_TOOL=podman ./test-local.sh --use-fallback

.PHONY: test-help
test-help:
	@./test-local.sh --help

.PHONY: test-clean
test-clean:
	@echo "Cleaning up test artifacts..."
	@rm -rf test-data/
	@docker rmi -f swedeb-api:local-test 2>/dev/null || true
	@echo "Test cleanup complete"
