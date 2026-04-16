
# Backend API for Swedeb

This repository contains the backend API for the Swedeb project. It is a Python application built with the FastAPI framework, designed to serve data to the frontend and handle complex queries over Swedish parliamentary debates (1867-2022).

## Features

- **Full-text corpus search** - CWB-based KWIC (keyword-in-context) queries with advanced filtering
- **Word trends analysis** - Track word frequency over time periods and demographic groups
- **N-gram extraction** - Extract and analyze n-grams from speeches with frequency statistics
- **Metadata queries** - Search speakers, parties, offices, and parliamentary periods
- **Speech retrieval** - Access individual speeches with full metadata enrichment
- **Statistical aggregations** - Frequency distributions and temporal analysis
- **REST API** - FastAPI-powered endpoints with automatic OpenAPI documentation
- **High performance** - Optimized CWB queries with caching and lazy loading

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

## Architecture

- **FastAPI** - Modern async web framework for API endpoints with automatic OpenAPI docs
- **CWB (Corpus Workbench)** - High-performance corpus queries via cwb-ccc Python wrapper
- **Service Layer** - Business logic in dedicated services (SearchService, KWICService, WordTrendsService, etc.)
- **Direct Injection** - Services injected via FastAPI `Depends()` for clean separation of concerns
- **Pydantic** - Request/response validation with type safety and automatic serialization
- **Feather/Arrow Storage** - Fast columnar storage for speech indexes and metadata
- **Docker + Auto-detection** - Containerized deployment with automatic frontend version detection

## Related Repositories
*   **[Swedeb Frontend](https://github.com/humlab-swedeb/swedeb_frontend)**: The frontend application for the Swedeb project, built with Vue.js and Quasar.
*   **[Swedeb Sample Data](https://github.com/humlab-swedeb/sample-data)**: Produces data for the Swedeb infrastructure based on **[SWERIK](https://github.com/swerik)** data.
*   **[humlab-penelope](https://github.com/humlab/humlab-penelope)**: A tools package supporting text analysis using Python.
*   **[pyriksprot](https://github.com/humlab/pyriksprot)**: A Python package for reading and processing SWERIK parliamentary data.
*   **[pyriksprot-tagger](https://github.com/humlab/pyriksprot-tagger)**: A tool for annotating and tagging SWERIK parliamentary data.

## Dependencies

Built with **FastAPI**, **CWB (Corpus Workbench)** via cwb-ccc, **Pydantic** for validation, **NumPy/SciPy** for numerical processing, and **Penelope** for corpus analysis. Development uses **uv** for dependency management, **pytest** for testing, and **Black/isort** for code formatting.

See [pyproject.toml](pyproject.toml) for the complete dependency list.

## Getting Started

### Prerequisites

- **Python** 3.13+
- **uv** for dependency management
- **Docker** (optional, for containerized development)
- **CWB data** - Corpus files from [sample-data repository](https://github.com/humlab-swedeb/sample-data)
- **Metadata database** - SQLite database with speaker/party information

### Local Development Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/humlab-swedeb/swedeb-api.git
    cd swedeb-api
    ```

2.  **Install dependencies:**
    ```bash
    uv pip install -e .
    ```

3. **Configure environment:**
    ```bash
    cp config/config_example.yml config/config.yml
    # Edit config.yml with your data paths and versions
    ```

4.  **Run the development server:**
    ```bash
    uv run uvicorn main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

5.  **View API documentation:**
    - **Swagger UI**: http://127.0.0.1:8000/docs (interactive API explorer)
    - **ReDoc**: http://127.0.0.1:8000/redoc (alternative documentation view)

### Project Structure

```
api_swedeb/
├── api/
│   ├── v1/endpoints/     # API route handlers
│   ├── services/         # Business logic layer
│   └── dependencies.py   # Dependency injection setup
├── core/                 # Core functionality (CWB, config, corpus loading)
├── schemas/              # Pydantic request/response models
├── mappers/              # Data transformation layer
├── workflows/            # Offline processing pipelines
└── legacy/               # Archived fallback runtime (debug only)
tests/
├── api_swedeb/           # Active runtime tests
├── integration/          # Integration tests
└── legacy/               # Legacy runtime tests
```

### Common Development Commands

```bash
# Run server
uv run uvicorn main:app --reload

# Run tests
uv run pytest tests/

# Code formatting (required before commits)
make tidy                        # Format with black + isort

# Coverage
make coverage                    # Run tests with coverage report

# Performance profiling
make profile-kwic-pyinstrument   # Profile KWIC queries
```

## Testing

Run the full test suite:
```bash
uv run pytest tests/
```

With coverage report:
```bash
make coverage
```

Profile KWIC performance:
```bash
make profile-kwic-pyinstrument
```

See [DEVELOPER.md](docs/DEVELOPER.md) for testing best practices and patterns.

## API Documentation

Once the server is running, explore the interactive API documentation:

- **Swagger UI**: http://127.0.0.1:8000/docs
  - Interactive API explorer with request/response examples
  - Try out endpoints directly from the browser
  - View request schemas and validation rules

- **ReDoc**: http://127.0.0.1:8000/redoc
  - Clean, readable alternative documentation view
  - Better for browsing and understanding the full API surface

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

### Quick Deploy of API & Frontend (staging)

```bash
# enter swedeb staging shell
λ sudo su 
λ cd /srv/swedeb_staging
λ manage-quadlet shell

# pull latest staging
λ podman image pull ghcr.io/humlab-swedeb/swedeb-api:staging

# complete reinstall
λ manage-quadlet remove && manage-quadlet install

# view status
λ manage-quadlet status
```

### Quick Deploy of Front-end Only (staging)

Push new PR to `staging` -> triggers a new release being built on Github. Check that the asset was built successfully at [swedeb_frontend/releases] (https://github.com/humlab-swedeb/swedeb_frontend/releases).

The enter swedeb_staging (as above) and restart ontinaer
```bash
λ podman compose restart 
# ...or...
λ podman compose down && podman compose up -d

```

**Complete guides:**
- [Deployment Guide](docs/DEPLOYMENT.md) - Full deployment instructions
- [Developer Guide](docs/DEVELOPER.md) - Workflow and contribution guidelines

## Environment Variables

Key environment variables for build and runtime configuration:

| Variable             | Description                           | Phase           |
|----------------------|---------------------------------------|-----------------|
| `SWEDEB_ENVIRONMENT` | Environment (test/staging/production) | Build & Runtime |
| `SWEDEB_IMAGE_TAG`   | Docker image tag                      | Build & Runtime |
| `SWEDEB_PORT`        | Container port                        | Build & Runtime |
| `SWEDEB_HOST_PORT`   | Host port mapping                     | Build & Runtime |
| `SWEDEB_DATA_FOLDER` | Corpus data path                      | Runtime         |
| `METADATA_VERSION`   | Metadata version                      | Runtime         |
| `CORPUS_VERSION`     | Corpus version                        | Runtime         |

See [Deployment Guide](docs/DEPLOYMENT.md) for complete variable reference.

## Acknowledgments

This project is built on data from the [SWERIK project](https://github.com/swerik-project) (Swedish Parliamentary Records in the Digital Age) and uses [humlab-penelope](https://github.com/humlab/humlab-penelope) for corpus processing and [CWB (Corpus Workbench)](https://cwb.sourceforge.io/) for high-performance text queries.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Humlab, Umeå University
