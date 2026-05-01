IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
IMAGE_TAG=staging
DOCKERFILE=Dockerfile
BACKEND_BRANCH=dev
FRONTEND_BRANCH=staging

.PHONY: image
image:
	@echo "Building image using podman"
	@podman build \
		--build-arg BACKEND_BRANCH="$(BACKEND_BRANCH)" \
		--build-arg FRONTEND_BRANCH="$(FRONTEND_BRANCH)" \
		-t "$(IMAGE_NAME):$(IMAGE_TAG)" \
		-f "$(DOCKERFILE)" .