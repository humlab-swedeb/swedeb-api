IMAGE_NAME=ghcr.io/humlab-swedeb/swedeb-api
IMAGE_TAG=staging
DOCKERFILE=Dockerfile

BACKEND_BRANCH=dev
BACKEND_REPO=https://github.com/humlab-swedeb/swedeb-api.git
BACKEND_COMMIT=$(shell \
	GIT_TERMINAL_PROMPT=0 \
	git ls-remote "$(BACKEND_REPO)" "refs/heads/$(BACKEND_BRANCH)" | cut -f1 \
)

FRONTEND_BRANCH=staging
FRONTEND_REPO=https://github.com/humlab-swedeb/swedeb_frontend.git
FRONTEND_COMMIT=$(shell \
	GIT_TERMINAL_PROMPT=0 \
	git ls-remote "$(FRONTEND_REPO)" "refs/heads/$(FRONTEND_BRANCH)" | cut -f1 \
)
.PHONY: image
image:
	@echo "Building image using podman"
	@podman build --no-cache \
		--build-arg BACKEND_BRANCH="$(BACKEND_BRANCH)" \
		--build-arg FRONTEND_BRANCH="$(FRONTEND_BRANCH)" \
		--build-arg FRONTEND_COMMIT="$(FRONTEND_COMMIT)" \
		--build-arg BACKEND_COMMIT="$(BACKEND_COMMIT)" \
		-t "$(IMAGE_NAME):$(IMAGE_TAG)" \
		-f "$(DOCKERFILE)" .

.PHONY: info
info:
	@echo "Backend commit: $(BACKEND_COMMIT)"
	@echo "Frontend commit: $(FRONTEND_COMMIT)"
