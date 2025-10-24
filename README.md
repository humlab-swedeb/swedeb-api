
# Backend API for Swedeb

This repository contains the backend API for the Swedeb project. It is a Python application built with the FastAPI framework, designed to serve data to the frontend and handle complex queries.

## 📚 Documentation

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Complete deployment instructions for all environments (Docker Compose & Podman)
- **[Workflow Guide](docs/WORKFLOW_GUIDE.md)** - Developer workflow, branching strategy, and commit conventions
- **[Workflow Architecture](docs/WORKFLOW_ARCHITECTURE.md)** - CI/CD pipeline architecture and technical details
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
- Python 3.12+
- Poetry
- Docker (optional, for containerized development)

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

4.  **Run the Development Server:**
    ```bash
    poetry run uvicorn api_swedeb.main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

5.  **View API Documentation:**
    - Swagger UI: `http://127.0.0.1:8000/docs`
    - ReDoc: `http://127.0.0.1:8000/redoc`

## Contributing

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning and changelog generation.

**Format:**
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Common types:**
- `feat:` - New feature (triggers minor version bump)
- `fix:` - Bug fix (triggers patch version bump)
- `docs:` - Documentation changes (no release)
- `chore:` - Maintenance tasks (no release)
- `BREAKING CHANGE:` - Breaking changes (triggers major version bump)

**Examples:**
```bash
# New feature
git commit -m "feat: add user authentication endpoint"

# Bug fix
git commit -m "fix: resolve database connection timeout"

# Documentation
git commit -m "docs: update API usage examples"

# Breaking change
git commit -m "feat!: redesign API response format

BREAKING CHANGE: All endpoints now return JSON instead of XML"
```

### Development Workflow

1. Create a feature branch from `dev`
2. Make changes and commit using conventional commits
3. Open a Pull Request to `dev`
4. After review and merge, changes flow through: `dev` → `test` → `staging` → `main`

See the [Workflow Guide](docs/WORKFLOW_GUIDE.md) for detailed information.

## Automated Release & Deployment

This project uses a fully automated CI/CD pipeline with semantic versioning:

- **Push to `test` branch** → Builds test environment images
- **Push to `staging` branch** → Builds staging environment images  
- **Push to `main` branch** → Triggers semantic-release:
  - Analyzes commits to determine version bump
  - Updates CHANGELOG.md
  - Creates GitHub Release with artifacts
  - Builds and publishes production Docker images
  - Commits version updates back to main

See the [Deployment Guide](docs/DEPLOYMENT.md) for complete deployment instructions.

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

[Add your license here]
