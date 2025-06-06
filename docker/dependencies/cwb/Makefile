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

include .env
export

CWB_VERSION ?= 3.5.0
IMAGE_NAME ?= swedeb/cwb
IMAGE_TAG ?= $(CWB_VERSION)

ifeq (,$(GHCR_TOKEN)) 
GHCR_TOKEN=$(shell cat ~/.ghcr_token)
endif
ifeq (,$(GHCR_USERNAME))
$(error GHCR_USERNAME is not set. Please set it in .env or export it in your shell.)
endif

###################################################################################################
# Publish the image to the GHCR registry
###################################################################################################

.PHONY: ghcr-login ghcr-publish
ghcr-login:
	@cat ~/.ghcr_token | $(CONTAINER_CMD) login ghcr.io --username "$(GHCR_USERNAME)" --password-stdin

ghcr-publish: ghcr-login image
	@echo "Publishing image $(IMAGE_NAME):$(CWB_VERSION) to GHCR…"
	@$(CONTAINER_CMD) tag $(IMAGE_NAME):$(CWB_VERSION) ghcr.io/$(GHCR_USERNAME)/$(IMAGE_NAME):$(CWB_VERSION)
	@$(CONTAINER_CMD) push ghcr.io/$(GHCR_USERNAME)/$(IMAGE_NAME):$(CWB_VERSION)
	@echo "Done publishing image $(IMAGE_NAME):$(CWB_VERSION) to GHCR"

###################################################################################################
# Build & tag the container image
###################################################################################################
.PHONY: image
.ONESHELL: image
image:
	@$(CONTAINER_CMD) build \
		-t $(IMAGE_NAME):latest \
		-t $(IMAGE_NAME):$(CWB_VERSION) \
		-f ./Dockerfile .
	@echo "Done building image $(IMAGE_NAME):$(CWB_VERSION)"
