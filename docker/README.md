# Environment Management and Deployment Strategy

This project utilizes Docker and Docker Compose to manage different environments: Development, Staging, and Production. This document outlines the setup and deployment process for each.

## Core Principles

*   **Consistency:** The Docker build process aims to be as consistent as possible across all environments.
*   **Configuration via Environment Variables:** Application behavior, connection strings, image tags, and network names are primarily controlled by environment variables, managed through XYX.envXYX files specific to each environment.
*   **Single XYXdocker-compose.ymlXYX:** We use a single XYXdocker-compose.ymlXYX file that is parameterized by environment variables.

## Environment Setup

### 1. Environment Files (XYX.envXYX files)

Environment-specific configurations are managed using XYX.envXYX files. You will need to create these based on the provided examples. These files are typically gitignored to prevent committing sensitive or environment-specific data.

*   XYX.env.developmentXYX: For local development.
*   XYX.env.stagingXYX: For the staging environment.
*   XYX.env.productionXYX: For the production environment.

**Example structure of an environment file (e.g., XYX.env.developmentXYX):**
XYZXYZXYZdotenv
# Environment identifier
SWEDEB_ENVIRONMENT=development

# Docker Image Configuration
SWEDEB_IMAGE_NAME=your-repo/swedeb-api # Or just swedeb-api if building locally
SWEDEB_IMAGE_TAG=dev-latest
SWEDEB_BACKEND_TAG=dev-latest # Build arg for Dockerfile
SWEDEB_FRONTEND_TAG=dev     # Build arg for Dockerfile
# NODE_VERSION=20           # Build arg for Dockerfile, if needed

# Docker Compose Runtime Configuration
SWEDEB_CONTAINER_NAME=swedeb_api
SWEDEB_HOST_PORT=8094      # Port on the host machine
SWEDEB_PORT=8092           # Port the application listens on inside the container
SWEDEB_NETWORK_NAME=swedeb_development_network # Actual Docker network name

# Application Specific Configuration
SWEDEB_CONFIG_PATH=config/config_development.yml
SWEDEB_DATA_FOLDER=./data_dev # Local path for development data
SWEDEB_METADATA_FILENAME=./metadata/dev_metadata.db # Example
METADATA_VERSION=dev # Example
# ... other application-specific variables
XYZXYZXYZ
*(Ensure you have corresponding XYX.env.stagingXYX and XYX.env.productionXYX files with appropriate values.)*

### 2. XYXdocker-compose.ymlXYX

Our XYXdocker-compose.ymlXYX is designed to read variables from an environment-specific XYX.envXYX file determined by the XYXSWEDEB_ENVIRONMENTXYX variable.

Key parts of XYXdocker-compose.ymlXYX:
XYZXYZXYZyaml
# docker-compose.yml (snippet)
version: '3.8'

services:
  swedeb_api:
    build:
      context: .
      args: # Populated from the loaded .env.<environment> file
        SWEDEB_PORT: "${SWEDEB_PORT}"
        SWEDEB_BACKEND_TAG: "${SWEDEB_BACKEND_TAG}"
        # ... other build args
    image: "${SWEDEB_IMAGE_NAME}:${SWEDEB_IMAGE_TAG}"
    container_name: "${SWEDEB_CONTAINER_NAME}-${SWEDEB_ENVIRONMENT}"
    env_file:
      - ".env.${SWEDEB_ENVIRONMENT}" # Loads the specific .env file
    # ... other service configurations
    networks:
      - swedeb_app_network

networks:
  swedeb_app_network:
    name: "${SWEDEB_NETWORK_NAME}" # Actual network name from .env.<environment>
    driver: bridge
XYZXYZXYZ

## Deployment Workflows

### A. Development Environment

Typically run on a developer's local machine.

1.  **Prerequisites:**
    *   Git, Docker, and Docker Compose installed.
    *   Repository cloned.
2.  **Setup:**
    *   Create or copy the XYX.env.developmentXYX file in the project root.
    *   Populate it with your local development settings (e.g., local paths for XYXSWEDEB_DATA_FOLDERXYX).
3.  **Running:**
    XYZXYZXYZbash
    # Set the environment context
    export SWEDEB_ENVIRONMENT=development

    # Build (if needed) and start services
    docker-compose up --build -d

    # To stop
    docker-compose down
    XYZXYZXYZ
    Alternatively, use a Makefile target:
    XYZXYZXYZbash
    make up-dev
    XYZXYZXYZ

### B. Staging Environment

Deployed to a dedicated staging server for testing and validation before production.

1.  **Trigger:**
    *   Deployment to staging is typically initiated manually via a GitHub Actions XYXworkflow_dispatchXYX trigger or automatically on pushes/merges to a specific staging branch (e.g., XYXrelease/*XYX or a dedicated XYXstagingXYX branch).
2.  **Process (GitHub Action XYXstaging-deploy.ymlXYX):**
    *   The GitHub Action workflow is triggered.
    *   It checks out the specified commit/branch.
    *   It builds the Docker image, tagging it appropriately for staging (e.g., XYXyour-ghcr-repo/swedeb-api:staging-latestXYX or XYXyour-ghcr-repo/swedeb-api:staging-<commit-sha>XYX).
    *   It pushes the image to GitHub Container Registry (GHCR).
    *   It connects to the staging server via SSH (using secrets for credentials).
    *   On the staging server, it:
        *   Ensures the XYXdocker-compose.ymlXYX is up-to-date.
        *   Ensures an XYX.env.stagingXYX file is present and correctly configured (this file might be managed on the server or its content injected via GitHub Actions secrets).
        *   Sets the XYXSWEDEB_ENVIRONMENT=stagingXYX variable.
        *   Pulls the new Docker image from GHCR.
        *   Runs XYXdocker-compose -f docker-compose.yml --env-file .env.staging up -d --remove-orphansXYX (or similar, ensuring it reads the XYX.env.stagingXYX by setting XYXSWEDEB_ENVIRONMENTXYX before the compose command).
3.  **Manual Fallback (if needed):**
    *   SSH into the staging server.
    *   Set XYXexport SWEDEB_ENVIRONMENT=stagingXYX.
    *   Pull the latest image: XYXdocker pull your-ghcr-repo/swedeb-api:staging-tagXYX.
    *   Update XYXSWEDEB_IMAGE_TAGXYX in XYX.env.stagingXYX if necessary.
    *   Run XYXdocker-compose up -dXYX.

### C. Production Environment

Deployed to the live production server.

1.  **Trigger:**
    *   Deployment to production is typically automated and triggered by:
        *   Pushing a new Git tag (e.g., XYXv1.0.0XYX).
        *   Merging changes into the XYXmainXYX branch.
2.  **Process (GitHub Action XYXproduction-deploy.ymlXYX or XYXrelease.ymlXYX):**
    *   The GitHub Action workflow is triggered.
    *   It checks out the specific tag/commit from the XYXmainXYX branch.
    *   It builds the Docker image, tagging it with the version and XYXlatestXYX (e.g., XYXyour-ghcr-repo/swedeb-api:v1.0.0XYX and XYXyour-ghcr-repo/swedeb-api:prod-latestXYX).
    *   It pushes the image(s) to GHCR.
    *   It connects to the production server(s) via SSH.
    *   On the production server, it performs a similar sequence to staging:
        *   Ensures XYXdocker-compose.ymlXYX and XYX.env.productionXYX are correct.
        *   Sets XYXSWEDEB_ENVIRONMENT=productionXYX.
        *   Pulls the new production-tagged Docker image.
        *   Runs XYXdocker-compose -f docker-compose.yml --env-file .env.production up -d --remove-orphansXYX.
        *   May include additional steps like database migrations, health checks, or rolling updates if applicable.

## Managing Configuration Files on Servers

*   **XYXdocker-compose.ymlXYX**: Can be checked into Git and pulled onto the server, or copied via XYXscpXYX during deployment.
*   **XYX.env.<environment>XYX files**:
    *   **Option 1 (Recommended for security):** Do not commit these to Git if they contain secrets.
        *   Create them manually on the server.
        *   Or, use a secrets management system (like HashiCorp Vault, or GitHub Actions encrypted secrets for CI/CD) to inject their content during deployment. For GitHub Actions, you can store the *content* of the XYX.envXYX file as a secret and write it to the server.
    *   **Option 2 (If no sensitive data):** Commit template/example files (XYX.env.exampleXYX) and copy/rename them on the server, then populate values.

This strategy provides a clear path for code from development to production, leveraging Docker for consistency and GitHub Actions for automation where appropriate.