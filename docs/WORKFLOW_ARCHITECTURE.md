# CI/CD Workflow Architecture

## Branch Strategy

This project uses a **four-branch workflow** for controlled progression through environments:

```
┌─────────────────────────────────────────────────────────────────┐
│                     BRANCH WORKFLOW STRATEGY                    │
└─────────────────────────────────────────────────────────────────┘

    Feature Branches
         │
         │ PR
         ▼
    ┌─────────┐
    │   dev   │ ← Integration branch (NO auto-builds)
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │  test   │ ← Test environment
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │ staging │ ← Staging/pre-production testing
    └────┬────┘
         │ PR
         ▼
    ┌─────────┐
    │  main   │ ← Production releases (semantic versioning)
    └─────────┘
```

### Branch Purpose

| Branch | Purpose | Build Trigger | Image Tags |
|--------|---------|---------------|------------|
| **dev** | Integration (no builds) | ❌ Manual only | N/A |
| **test** | Test environment | Auto on push | `{version}-test`, `test`, `test-latest` |
| **staging** | Pre-production validation | Auto on push | `{version}-staging`, `staging` |
| **main** | Production releases | Auto on push | `{version}`, `{major}`, `{minor}`, `latest`, `production` |

## Unified Build Strategy

All three environments use the **same Docker build script** with different parameters, ensuring consistency and reducing maintenance overhead.

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED BUILD ARCHITECTURE                   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│    Test Build        │  │   Staging Build      │  │  Production Release  │
│  (push to test)      │  │  (push to staging)   │  │  (push to main)      │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                         │                         │
           ▼                         ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ .github/workflows/   │  │ .github/workflows/   │  │  .releaserc.yml      │
│ test.yml             │  │ staging.yml          │  │                      │
│                      │  │                      │  │  Plugin Chain:       │
│ Steps:               │  │ Steps:               │  │  1. commit-analyzer  │
│ 1. checkout          │  │ 1. checkout          │  │  2. release-notes    │
│ 2. get version       │  │ 2. get version       │  │  3. changelog        │
│ 3. docker login      │  │ 3. docker login      │  │  4. exec (prepare)   │
│ 4. build & push ─────┼──┼─ 4. build & push ────┼──┼─ 5. github release   │
│    (test)            │  │    (staging)         │  │  6. exec (publish)   │
└──────────────────────┘  └──────────────────────┘  │  7. git commit back  │
                                                    └──────────┬───────────┘
           │                         │                         │
           └─────────────────────────┴─────────────────────────┘
                                     │
                                     ▼
                   ┌──────────────────────────────────────┐
                   │  build-and-push-image.sh             │
                   │                                      │
                   │  Args: <version> <environment>       │
                   │  Env: test | staging | production    │
                   │                                      │
                   │  Logic:                              │
                   │  1. Validate environment             │
                   │  2. Login to GHCR                    │
                   │  3. Parse version components         │
                   │  4. Build with environment tags      │
                   │  5. Push all tags                    │
                   └──────────────────────────────────────┘
                                     │
                                     ▼
                   ┌──────────────────────────────────────┐
                   │     GitHub Container Registry        │
                   │      ghcr.io/humlab-swedeb/          │
                   │          swedeb-api                  │
                   │                                      │
                   │  Test Tags:                          │
                   │  • 0.6.1-test                        │
                   │  • test                              │
                   │  • test-latest                       │
                   │                                      │
                   │  Staging Tags:                       │
                   │  • 0.6.1-staging                     │
                   │  • staging                           │
                   │                                      │
                   │  Production Tags:                    │
                   │  • 0.6.1                             │
                   │  • 0.6                               │
                   │  • 0                                 │
                   │  • latest                            │
                   │  • production                        │
                   └──────────────────────────────────────┘
```

## Key Components

### 1. Unified Build Script
**File**: `.github/scripts/build-and-push-image.sh`

**Purpose**: Single source of truth for building and pushing Docker images

**Parameters**:
- `<version>`: Semantic version (e.g., 0.6.1)
- `<environment>`: `test`, `staging`, or `production`

**Environment Variables**:
- `DOCKER_USERNAME`: GitHub actor
- `DOCKER_PASSWORD`: GitHub token
- `CWB_REGISTRY_TOKEN`: Personal token for cross-org access (optional)
- `FRONTEND_VERSION_TAG`: Frontend version to include (default: latest)
- `GITHUB_REPOSITORY`: Org/repo name

### 2. Test Build Flow

```
test branch push
  → GitHub Actions triggers test.yml
    → Checkout code
    → Get version from pyproject.toml
    → Login to GHCR
    → Run build-and-push-image.sh test
      → Builds Docker image
      → Tags: {version}-test, test, test-latest
      → Pushes to GHCR
```

### 3. Staging Build Flow

```
staging branch push
  → GitHub Actions triggers staging.yml
    → Checkout code
    → Get version from pyproject.toml
    → Login to GHCR
    → Run build-and-push-image.sh staging
      → Builds Docker image
      → Tags: {version}-staging, staging
      → Pushes to GHCR
```

### 4. Production Release Flow

```
main branch push
  → GitHub Actions triggers release.yml
    → npm ci (install semantic-release)
      → npx semantic-release
        → Analyzes commits
        → Determines version
        → Runs prepare-release-assets.sh
          → Updates pyproject.toml
          → Builds Python wheel
        → Creates GitHub release
        → Runs build-and-push-image.sh production
          → Builds Docker image
          → Tags: {version}, {major}, {minor}, latest, production
          → Pushes to GHCR
        → Commits CHANGELOG.md back to main
```

## Benefits of This Architecture

1. **🔄 Consistency**: Same build logic for all environments
2. **🛠️ Maintainability**: Changes to build process apply to all workflows
3. **🧪 Testability**: Can test build script independently
4. **📦 Simplicity**: Single Dockerfile, environment-specific tagging
5. **🔍 Clarity**: Clear separation between environments
6. **🚀 Progressive Deployment**: dev → staging → production pipeline

## Workflow Comparison

| Aspect | Test | Staging | Production |
|--------|------|---------|------------|
| **Trigger** | Push to `test` | Push to `staging` | Push to `main` |
| **Versioning** | From pyproject.toml | From pyproject.toml | Semantic-release |
| **Build Script** | `build-and-push-image.sh` | `build-and-push-image.sh` | `build-and-push-image.sh` |
| **Environment Arg** | `test` | `staging` | `production` |
| **Tags Created** | 3 tags (version-test, test, test-latest) | 2 tags (version-staging, staging) | 5 tags (version, major, minor, latest, production) |
| **Changelog** | ❌ Not updated | ❌ Not updated | ✅ Auto-generated |
| **GitHub Release** | ❌ Not created | ❌ Not created | ✅ Created with assets |
| **Python Wheel** | ❌ Not built | ❌ Not built | ✅ Built and attached |

## Multi-Image Architecture

The API Docker image depends on two other images:

```dockerfile
ARG FRONTEND_VERSION=latest
FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
FROM ghcr.io/humlab/cwb-container:latest AS final

# ... copy frontend assets from frontend-dist ...
COPY --from=frontend-dist /app/public ./public
```

**Dependencies**:
1. **Frontend Image**: `ghcr.io/humlab-swedeb/swedeb_frontend` (same org)
2. **CWB Base Image**: `ghcr.io/humlab/cwb-container` (different org - requires CWB_REGISTRY_TOKEN)

## Cross-Organization Access

Since the CWB base image is in a different organization (`humlab` vs `humlab-swedeb`), both workflows use:

```yaml
env:
  CWB_REGISTRY_TOKEN: ${{ secrets.CWB_REGISTRY_TOKEN }}
```

This PAT (Personal Access Token) has `read:packages` and `write:packages` scopes, allowing:
- ✅ Read from `humlab/cwb-container`
- ✅ Write to `humlab-swedeb/swedeb-api`
