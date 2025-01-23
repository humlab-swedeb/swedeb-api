# Project Build and Deployment

This folder contains a Makefile and configuration files for building and deploying production and staging versions of Swedeb.


## Usage

To use the Makefile, you first need to select a target deploy environment (staging or production) and then building the image.
The system will ask for confirmation if you try to build a new image that targets the production environment.

### Switch to environment that targets DEVELOPMENT

```sh
make setup-staging
```

### Switch to environment that targets PRODUCTION

```sh
make setup-production
```

### Make image

```sh
make image
```


## Primary targets
  help              - Show this help
  setup-production  - Setup .env for production deployment 
  setup-staging     - Setup .env for staging deployment
  image             - Build frontend, backend and image

## Secondary targets

  frontend          - Build frontend application and copy dist to ./public folder
  backend           - Build backend if SWEDEB_BACKEND_TAG isn't a semver version, and not 'workdir' or branch or tag
  bash              - Run bash in container
  add-host-user     - Add host user
  tools             - Install tools

## Environment Variables

 - SWEDEB_ENVIRONMENT: The current environment (development, staging, production).
 - SWEDEB_BACKEND_TAG: The backend version to deploy (branch, tag, commit, or 'workdir').
 - SWEDEB_FRONTEND_TAG: The frontend version to deploy (branch, tag, commit).
 - SWEDEB_IMAGE_NAME: The base image name.
 - SWEDEB_CONTAINER_NAME: The running container name (SWEDEB_ENVIRONMENT will be appended).
 - SWEDEB_IMAGE_TAG: The target Docker image tag (staging or latest).
 - SWEDEB_PORT: The port to expose the container on.
 - SWEDEB_HOST_PORT: The host port to expose the container on.
 - SWEDEB_SUBNET: The subnet to use for the container.
 - SWEDEB_DATA_FOLDER: The data folder to mount into the container.
 - SWEDEB_CONFIG_PATH: The config file to mount into the container.

