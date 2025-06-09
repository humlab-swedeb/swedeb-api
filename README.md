
# Backend API for Swedeb

This repository contains the backend API for the Swedeb project. It is a Python application built with the FastAPI framework, designed to serve data to the frontend and handle complex queries.

## Technology Stack

The backend is built on a containerized architecture, leveraging modern Python tooling and best practices.

*   **[Python 3.12](https://www.python.org/)**: The core programming language.
*   **[The IMS Open Corpus Workbench](https://sourceforge.net/projects/cwb/)**: Tools for managing and querying large text corpora.
*   **[FastAPI](https://fastapi.tiangolo.com/)**: A high-performance web framework for building APIs.
*   **[Docker](https://www.docker.com/)**: For containerizing the application, ensuring a consistent environment. The final image is built on a custom base image that includes CWB (Corpus Workbench) functionality.
*   **[GitHub Container Registry (GHCR)](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)**: For hosting the final Docker application image.

## Related Repositories
*   **[Swedeb Frontend](https://github.com/humlab-swedeb/swedeb-frontend)**: The frontend application for the Swedeb project, built with React.
*   **[Swedeb Sample Data](https://github.com/humlab-swedeb/sample-data)**: Produces data for the Swedeb infrastructure based on **[SWERIK](https://github.com/swerik)** data.
*   **[humlab-penelope](https://github.com/humlab/humlab-penelope)**: A tools package supporting text analysis using Python.
*   **[pyriksprot](https://github.com/humlab/pyriksprot)**: A Python package for reading and processing SWERIK parliamentary data.
*   **[pyriksprot-tagger](https://github.com/humlab/pyriksprot-tagger)**: A tool for annotating and tagging SWERIK parliamentary data.

## Other Used Packages
*   **[cwb-ccc](https://github.com/humlab/cwb-ccc)**: A Python package for working with the CWB (Corpus Workbench) command-line tools.
*   **[stanza](https://stanfordnlp.github.io/stanza/)**: A Python NLP library for tokenization, lemmatization, and part-of-speech tagging.
*   **[pydantic](https://pydantic-docs.helpmanual.io/)**: For data validation and settings management using Python type annotations.
*   **[uvicorn](https://www.uvicorn.org/)**: An ASGI server for running FastAPI applications.

## Dev Tools
*   **[Poetry](https://python-poetry.org/)**: For dependency management and packaging.
*   **[pytest](https://docs.pytest.org/en/stable/)**: For running tests.
*   **[black](https://black.readthedocs.io/en/stable/)**: A code formatter to ensure consistent code style.
*   **[isort](https://pycqa.github.io/isort/)**: For sorting imports in Python files.

## Automated Release Workflow

This project employs a fully automated release pipeline using **GitHub Actions** and **`semantic-release`**. This system handles versioning, building artifacts, and publishing releases without manual intervention, ensuring consistency and reliability.

### How It Works

The entire release process is triggered automatically whenever a commit is pushed to the `main` branch.

1.  **Commit Convention is Key:** The process relies entirely on the **[Conventional Commits specification](https://www.conventionalcommits.org/)**. The format of each commit message (e.g., `feat:`, `fix:`, `docs:`) dictates how the project is versioned.

2.  **Workflow Trigger:** A push to `main` starts the `Release Backend` workflow.

3.  **Version Calculation:** `semantic-release` analyzes all commits since the last release tag. It automatically determines the next version number based on the commit types:
    *   `fix:` -> **Patch** release (e.g., `1.2.0` -> `1.2.1`)
    *   `feat:` -> **Minor** release (e.g., `1.2.0` -> `1.3.0`)
    *   `BREAKING CHANGE:` -> **Major** release (e.g., `1.2.0` -> `2.0.0`)

4.  **Prepare Assets:**
    *   The workflow calls a script that bumps the version number in `pyproject.toml` (via `poetry version`) and synchronizes it with the `__version__` variable in `api_swedeb/__init__.py`.
    *   It then builds the Python package into a wheel (`.whl`) file inside the `dist/` directory.

5.  **Create GitHub Release:**
    *   A new **GitHub Release** is created with the new version tag (e.g., `v1.3.0`).
    *   A **changelog** is automatically generated from the commit messages and added to the release notes.
    *   The built Python wheel (`.whl`) is uploaded as an artifact to this release.

6.  **Build & Publish Docker Image:**
    *   The workflow builds a new Docker image for the application. This image uses the specified frontend version and installs the Python backend from the newly created wheel.
    *   The final image is tagged (e.g., as `v1.3.0`, `v1.3`, `v1`, and `latest`) and pushed to the **GitHub Container Registry (GHCR)**.

7.  **Finalize Commit:**
    *   To complete the cycle, `semantic-release` commits the updated `pyproject.toml` and `CHANGELOG.md` files back to the `main` branch and pushes the new version tag. This commit is marked with `[skip ci]` to prevent the workflow from re-triggering itself.

### How to Contribute and Trigger a Release

As a developer, your only responsibility is to write clear, conventional commit messages. The automation handles the rest.

1.  **Create a feature branch:**
    ```bash
    git checkout -b my-new-api-endpoint
    ```

2.  **Make your changes.**

3.  **Commit your work using the Conventional Commits specification.** This is the crucial step.

    *   For a new feature (triggers a **minor** release):
        ```bash
        git commit -m "feat: add endpoint for user authentication"
        ```

    *   For a bug fix (triggers a **patch** release):
        ```bash
        git commit -m "fix: resolve data race condition in corpus query"
        ```
        
    *   For changes that should **not** trigger a release (e.g., docs, tests, refactoring):
        ```bash
        git commit -m "docs: update API documentation for auth endpoint"
        git commit -m "refactor: improve performance of database queries"
        ```

    *   For a breaking change (triggers a **major** release):
        ```bash
        git commit -m "feat: switch from XML to JSON for API responses

        BREAKING CHANGE: The default API response format is now JSON. Clients expecting XML must update their headers to 'Accept: application/xml'."
        ```

4.  **Push your branch and open a Pull Request** to `main`.

5.  Once your PR is reviewed and **merged into `main`**, the release pipeline will automatically run.

---

## Local Development

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install Poetry:**
    Follow the [official installation instructions](https://python-poetry.org/docs/#installation) to install Poetry.

3.  **Install Dependencies:**
    This command creates a virtual environment and installs all dependencies from `pyproject.toml` and `poetry.lock`.
    ```bash
    poetry install
    ```

4.  **Run the Development Server:**
    Use `poetry run` to execute commands within the project's virtual environment.
    ```bash
    # Replace 'api_swedeb.main:app' with the correct path to your FastAPI app instance
    poetry run uvicorn api_swedeb.main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

### Local CI/CD Workflow Testing with `act`

Developers **do not** need to create any special tokens for the normal contribution process.

However, if you need to **test changes to the CI/CD workflow itself**, you can use [**act**](https://github.com/nektos/act) to run the workflow locally. This requires a **GitHub Personal Access Token (PAT)** to allow `act` to interact with the GitHub API.

#### Setup for `act`

1.  **Install `act`:** Follow the [official installation instructions](https://github.com/nektos/act#installation).

2.  **Create a Personal Access Token (PAT):**
    *   Go to your GitHub Settings -> [Developer settings](https://github.com/settings/developers) -> Personal access tokens -> **Tokens (classic)**.
    *   Generate a new token with the following scopes: **`repo`**, **`workflow`**, and **`write:packages`**.
    *   Copy the generated token (`ghp_...`) and save it securely, for example in a file at `~/.ghcr_token`.

3.  **Run the Release Workflow Locally:**
    Use the `-j` flag for the job ID and `-s` to provide your PAT as a secret.

    ```bash
    # This command simulates the release job in "dry-run" mode
    act -j release -s GITHUB_TOKEN="$(cat ~/.ghcr_token)"
    ```
    `act` will show you what `semantic-release` *would* do without actually publishing anything, which is perfect for testing.

## Environment Variables
This project uses several environment variables to configure the build and runtime behavior of the application. These variables can be set in your local environment or in your CI/CD pipeline.

| Variable Name              | Description                                                       | Phase           |
| -------------------------- | ----------------------------------------------------------------- | --------------- |
| `SWEDEB_BACKEND_SOURCE`    | The source of the backend (workdir or pypi)                       | Build Only      |
| `NODE_VERSION`             | The Node.js version to use for building the frontend              | Build Only      |
| `SWEDEB_ENVIRONMENT`       | The current environment (development, staging, production)        | Build & Runtime |
| `SWEDEB_BACKEND_TAG`       | The backend version to deploy (branch, tag, commit, or 'workdir') | Build & Runtime |
| `SWEDEB_FRONTEND_TAG`      | The frontend version to deploy (branch, tag, commit)              | Build & Runtime |
| `SWEDEB_IMAGE_NAME`        | The base image name                                               | Build & Runtime |
| `SWEDEB_CONTAINER_NAME`    | The running container name (SWEDEB_ENVIRONMENT will be appended)  | Build & Runtime |
| `SWEDEB_IMAGE_TAG`         | The target Docker image tag (staging or latest)                   | Build & Runtime |
| `SWEDEB_PORT`              | The port to expose the container on                               | Build & Runtime |
| `SWEDEB_HOST_PORT`         | The host port to expose the container on                          | Build & Runtime |
| `SWEDEB_SUBNET`            | The subnet to use for the container                               | Build & Runtime |
| `SWEDEB_DATA_FOLDER`       | The data folder to mount into the container                       | Build & Runtime |
| `SWEDEB_CONFIG_PATH`       | The config file to mount into the container                       | Build & Runtime |
| `METADATA_VERSION`         | The version of the metadata to use                                | Runtime Only    |
| `CORPUS_VERSION`           | The version of the corpus to use                                  | Runtime Only    |
| `SWEDEB_METADATA_FILENAME` | The path to the metadata file to mount into the container         | Runtime Only    |


# Environment Management and Deployment Strategy

This project utilizes Docker and Docker Compose to manage different environments: Development, Staging, and Production. This document outlines the setup and deployment process for each.

## Core Principles

*   **Consistency:** The Docker build process aims to be as consistent as possible across all environments.
*   **Configuration via Environment Variables:** Application behavior, connection strings, image tags, and network names are primarily controlled by environment variables, managed through `.env` files specific to each environment.
*   **Single `docker-compose.yml`:** We use a single `docker-compose.yml` file that is parameterized by environment variables.

## Environment Setup

### 1. Environment Files (`.env` files)

Environment-specific configurations are managed using `.env` files. You will need to create these based on the provided examples. These files are typically gitignored to prevent committing sensitive or environment-specific data.

*   `.env.development`: For local development.
*   `.env.staging`: For the staging environment.
*   `.env.production`: For the production environment.

**Example structure of an environment file (e.g., `.env.development`):**
```dotenv
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
```
*(Ensure you have corresponding `.env.staging` and `.env.production` files with appropriate values.)*

### 2. `docker-compose.yml`

Our `docker-compose.yml` is designed to read variables from an environment-specific `.env` file determined by the `SWEDEB_ENVIRONMENT` variable.

Key parts of `docker-compose.yml`:
```yaml
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
```

## Deployment Workflows

### A. Development Environment

Typically run on a developer's local machine.

1.  **Prerequisites:**
    *   Git, Docker, and Docker Compose installed.
    *   Repository cloned.
2.  **Setup:**
    *   Create or copy the `.env.development` file in the project root.
    *   Populate it with your local development settings (e.g., local paths for `SWEDEB_DATA_FOLDER`).
3.  **Running:**
    ```bash
    # Set the environment context
    export SWEDEB_ENVIRONMENT=development

    # Build (if needed) and start services
    docker-compose up --build -d

    # To stop
    docker-compose down
    ```
    Alternatively, use a Makefile target:
    ```bash
    make up-dev
    ```

### B. Staging Environment

Deployed to a dedicated staging server for testing and validation before production.

1.  **Trigger:**
    *   Deployment to staging is typically initiated manually via a GitHub Actions `workflow_dispatch` trigger or automatically on pushes/merges to a specific staging branch (e.g., `release/*` or a dedicated `staging` branch).
2.  **Process (GitHub Action `staging-deploy.yml`):**
    *   The GitHub Action workflow is triggered.
    *   It checks out the specified commit/branch.
    *   It builds the Docker image, tagging it appropriately for staging (e.g., `humlab-swedeb/swedeb-api:staging-latest` or `humlab-swedeb/swedeb-api:staging-<commit-sha>`).
    *   It pushes the image to GitHub Container Registry (GHCR).
    *   It connects to the staging server via SSH (using secrets for credentials).
    *   On the staging server, it:
        *   Ensures the `docker-compose.yml` is up-to-date.
        *   Ensures an `.env.staging` file is present and correctly configured (this file might be managed on the server or its content injected via GitHub Actions secrets).
        *   Sets the `SWEDEB_ENVIRONMENT=staging` variable.
        *   Pulls the new Docker image from GHCR.
        *   Runs `docker-compose -f docker-compose.yml --env-file .env.staging up -d --remove-orphans` (or similar, ensuring it reads the `.env.staging` by setting `SWEDEB_ENVIRONMENT` before the compose command).
3.  **Manual Fallback (if needed):**
    *   SSH into the staging server.
    *   Set `export SWEDEB_ENVIRONMENT=staging`.
    *   Pull the latest image: `docker pull humlab-swedeb/swedeb-api:staging-tag`.
    *   Update `SWEDEB_IMAGE_TAG` in `.env.staging` if necessary.
    *   Run `docker-compose up -d`.

### C. Production Environment

Deployed to the live production server.

1.  **Trigger:**
    *   Deployment to production is typically automated and triggered by:
        *   Pushing a new Git tag (e.g., `v1.0.0`).
        *   Merging changes into the `main` branch.
2.  **Process (GitHub Action `release.yml`):**
    *   The GitHub Action workflow is triggered.
    *   It checks out the specific tag/commit from the `main` branch.
    *   It builds the Docker image, tagging it with the version and `latest` (e.g., `humlab-swedeb/swedeb-api:v1.0.0` and `humlab-swedeb/swedeb-api:prod-latest`).
    *   It pushes the image(s) to GHCR.
    *   It connects to the production server(s) via SSH.
    *   On the production server, it performs a similar sequence to staging:
        *   Ensures `docker-compose.yml` and `.env.production` are correct.
        *   Sets `SWEDEB_ENVIRONMENT=production`.
        *   Pulls the new production-tagged Docker image.
        *   Runs `docker-compose -f docker-compose.yml --env-file .env.production up -d --remove-orphans`.
        *   May include additional steps like database migrations, health checks, or rolling updates if applicable.

## Managing Configuration Files on Servers

*   **`docker-compose.yml`**: Can be checked into Git and pulled onto the server, or copied via `scp` during deployment.
*   **`.env.<environment>` files**:
    *   **Option 1 (Recommended for security):** Do not commit these to Git if they contain secrets.
        *   Create them manually on the server.
        *   Or, use a secrets management system (like HashiCorp Vault, or GitHub Actions encrypted secrets for CI/CD) to inject their content during deployment. For GitHub Actions, you can store the *content* of the `.env` file as a secret and write it to the server.
    *   **Option 2 (If no sensitive data):** Commit template/example files (`.env.example`) and copy/rename them on the server, then populate values.

This strategy provides a clear path for code from development to production, leveraging Docker for consistency and GitHub Actions for automation where appropriate.
