SHELL:=/bin/bash


# .DEFAULT_GOAL=info

ifeq (,$(wildcard .env))
    $(error .env does not found!)
endif

include ./.env
export

ifndef SWEDEB_BACKEND_TAG
	$(error SWEDEB_BACKEND_TAG is undefined)
endif

ifndef SWEDEB_FRONTEND_TAG
	$(error SWEDEB_FRONTEND_TAG is undefined)
endif

.PHONY: build build-frontend build-backend create-tmpdir

TMPDIR_BUILD=/tmp/swedeb-src

.ONESHELL: build-frontend
build-frontend: create-tmpdir
	@echo "Building frontend using $(SWEDEB_FRONTEND_TAG)..." \
		&& pushd . > /dev/null \
		&& cd $(TMPDIR_BUILD) \
		&& git clone https://github.com/humlab-swedeb/swedeb_frontend.git --branch $(SWEDEB_FRONTEND_TAG) --depth 1 \
		&& cd swedeb_frontend \
		&& pnpm install \
		&& pnpm build \
		&& popd > /dev/null \
		&& rm -rf public \
		&& mv -f $(TMPDIR_BUILD)/swedeb_frontend/dist/spa public \
		&& rm -rf $(TMPDIR_BUILD)

.ONESHELL: build-backend
build-backend: create-tmpdir
	@echo "Building backend API using $(SWEDEB_BACKEND_TAG)..." \
		&& pushd . > /dev/null \
		&& mkdir -p $(TMPDIR_BUILD) && cd $(TMPDIR_BUILD) \
		&& git clone https://github.com/humlab-swedeb/swedeb-api.git --branch $(SWEDEB_BACKEND_TAG) --depth 1 \
		&& cd swedeb-api \
		&& poetry build \
		&& popd > /dev/null \
		&& rm -rf dist \
		&& mv -f $(TMPDIR_BUILD)/swedeb-api/dist dist \
		&& rm -rf $(TMPDIR_BUILD)

.ONESHELL: build-image
build-image:
	@echo "Building image using $(SWEDEB_BACKEND_TAG)..."
	@docker build \
		--build-arg SWEDEB_PORT=$(SWEDEB_PORT) \
		-t $(SWEDEB_IMAGE_NAME):$(SWEDEB_IMAGE_TAG) \
		-t $(SWEDEB_IMAGE_NAME):$(SWEDEB_BACKEND_TAG) \
		-f ./Dockerfile .

.ONESHELL: build-image
build: build-frontend build-backend build-image
	@echo "Done building $(SWEDEB_BACKEND_TAG)!"

.PHONY: create-tmpdir
create-tmpdir:
	@echo "Cleaning build..."
	@rm -rf $(TMPDIR_BUILD) && mkdir -p $(TMPDIR_BUILD)

.PHONY: bash
bash:
	@docker run -it --rm \
	  --volume "${HOST_CWB_DATA_FOLDER}:/data/cwb/data" \
      --volume "${HOST_METADATA_FOLDER}:/data/metadata" \
      --volume "${HOST_DTM_FOLDER}:/data/corpus/dtm" \
      --volume "${HOST_TAGGED_CORPUS_FOLDER}:/data/corpus/tagged_frames" \
	  --env-file .env \
	  swedeb-api:latest /bin/bash


.PHONY: tools
tools:
	@ curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
	@ wget -qO- https://get.pnpm.io/install.sh | sh -
	@ source ~/.bashrc
	@ nvm install node
