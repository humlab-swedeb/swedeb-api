
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
*   **[humlab-tagger](https://github.com/humlab/humlab-tagger)**: A tool for annotating and tagging SWERIK parliamentary data.

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

