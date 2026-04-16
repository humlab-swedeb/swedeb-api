
# Backend API for Swedeb

This repository contains the backend API for the Swedeb project. It is a Python application built with the FastAPI framework, designed to serve data to the frontend and handle complex queries.

## 📚 Documentation

### For Developers
- **[Developer Guide](docs/DEVELOPER.md)** - Complete developer workflow, branching strategy, commit conventions, and CI/CD architecture
- **[AI Coding Agent Instructions](.github/copilot-instructions.md)** - Essential guide for AI assistants working with this codebase

### For Deployment & Operations
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Complete deployment guide covering all environments (test, staging, production)
- **[Podman Quadlet Deployment](docs/DEPLOY_PODMAN.md)** - Detailed Podman systemd deployment procedures (recommended for production)
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions for deployment problems

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

## Quick Start

### Prerequisites
- Python 3.11+ (3.12 recommended)
- Poetry (dependency management)
- Docker (optional, for containerized development)
- CWB (Corpus Workbench) data files (see [sample-data repository](https://github.com/humlab-swedeb/sample-data))

### Local Development Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/humlab-swedeb/swedeb-api.git
    cd swedeb-api
    ```

2.  **Install Poetry:**
    Follow the [official installation instructions](https://python-poetry.org/docs/#installation).

3.  **Install Dependencies:**
    ```bash
    poetry install
    ```
4. **Configure Environment:**
    ```bash
    cp .env_example .env
    # Edit .env with your data paths
    ```

5.  **Run the Development Server:**
6.  **View API Documentation:**
    - Swagger UI: `http://127.0.0.1:8000/docs`
    - ReDoc: `http://127.0.0.1:8000/redoc`

### Common Development Commands

```bash
# Run tests
poetry run pytest tests/

# Code formatting (required before commits)
make tidy                        # Format with black + isort
make black                       # Format with black only
make isort                       # Sort imports only

# Code quality
make pylint                      # Lint code
make notes                       # Find FIXME/TODO comments

# Coverage
make coverage                    # Run tests with coverage report

# Performance profiling
make profile-kwic-pyinstrument  # Profile KWIC queries
```
poetry run uvicorn main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

5.  **View API Documentation:**
    - Swagger UI: `http://127.0.0.1:8000/docs`
    - ReDoc: `http://127.0.0.1:8000/redoc`

## Contributing

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning and changelog generation.

**Quick reference:**
- `feat:` - New feature (minor version bump: 0.6.0 → 0.7.0)
- `fix:` - Bug fix (patch version bump: 0.6.0 → 0.6.1)
- `BREAKING CHANGE:` - Breaking change (major version bump: 0.6.0 → 1.0.0)
- `docs:`, `chore:` - No version bump

**Example:**
```bash
git commit -m "feat: add user authentication endpoint"
git commit -m "fix: resolve database connection timeout"
git commit -m "feat!: redesign API

BREAKING CHANGE: All endpoints now use /v2/ prefix"
```

**Workflow:** Create feature branch from `dev` → PR to `dev` → After merge: `dev` → `test` → `staging` → `main`

See the [Developer Guide](docs/DEVELOPER.md) for complete workflow, branching strategy, and CI/CD details.

## Deployment & Release

This project uses automated CI/CD with semantic versioning and a four-branch workflow:

**Branch Flow**: `dev` → `test` → `staging` → `main`

### Automated Deployments

- **Push to `test` branch** → Builds test environment images (`:test`, `:test-latest`)
- **Push to `staging` branch** → Builds staging environment images (`:staging`)  
- **Push to `main` branch** → Triggers semantic-release:
  - Analyzes commits to determine version bump (major/minor/patch)
  - Updates CHANGELOG.md
  - Creates GitHub Release with Python wheel artifacts
  - Builds and publishes production Docker images (`:latest`, `:production`, versioned tags)
  - Commits version updates back to main

### Frontend Version Auto-Detection

Backend containers automatically detect which frontend version to download based on the git branch:
- **main/master** → Downloads `latest` frontend
- **staging** → Downloads `staging` frontend
- **test** → Downloads `test` frontend

You can override this by setting the `FRONTEND_VERSION` environment variable.

### Quick Deploy

```bash
# Production deployment (Podman Quadlet recommended)
# See docs/DEPLOY_PODMAN.md for full setup

# Pull latest image
podman pull ghcr.io/humlab-swedeb/swedeb-api:0.7.0

# Start container (systemd service)
systemctl --user restart swedeb-api-production

# Verify deployment
systemctl --user status swedeb-api-production
journalctl --user -u swedeb-api-production -n 100
```

**Complete guides:**
- [Deployment Guide](docs/DEPLOYMENT.md) - Full deployment instructions
- [Developer Guide](docs/DEVELOPER.md) - Workflow and contribution guidelines

## Testing CI/CD Locally with `act`

To test GitHub Actions workflows locally:

1.  **Install `act`:** Follow the [official installation instructions](https://github.com/nektos/act#installation).

2.  **Create a Personal Access Token (PAT):**
    - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
    - Generate token with scopes: `repo`, `workflow`, `write:packages`
    - Save to `~/.ghcr_token`

3.  **Run workflows locally:**
    ```bash
    # Test the release workflow
    act -j release -s GITHUB_TOKEN="$(cat ~/.ghcr_token)"
    ```

## Environment Variables

Key environment variables for build and runtime configuration:

| Variable | Description | Phase |
|----------|-------------|-------|
| `SWEDEB_ENVIRONMENT` | Environment (test/staging/production) | Build & Runtime |
| `SWEDEB_IMAGE_TAG` | Docker image tag | Build & Runtime |
| `SWEDEB_PORT` | Container port | Build & Runtime |
| `SWEDEB_HOST_PORT` | Host port mapping | Build & Runtime |
| `SWEDEB_DATA_FOLDER` | Corpus data path | Runtime |
| `METADATA_VERSION` | Metadata version | Runtime |
| `CORPUS_VERSION` | Corpus version | Runtime |

See [Deployment Guide](docs/DEPLOYMENT.md) for complete variable reference.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Humlab, Umeå University
