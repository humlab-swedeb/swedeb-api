# Developer Guide

This guide provides comprehensive information for developers working on the Swedeb API project, including workflow, branching strategy, commit conventions, and CI/CD architecture.

## Table of Contents

- [Branch Strategy](#branch-strategy)
- [Developer Workflow](#developer-workflow)
- [Commit Message Guidelines](#commit-message-guidelines)
- [CI/CD Architecture](#cicd-architecture)
- [Hotfix Procedures](#hotfix-procedures)
- [Manual Deployments](#manual-deployments)
- [Best Practices](#best-practices)

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

| Branch | Purpose | Auto-Deploy | Image Tags |
|--------|---------|-------------|------------|
| `dev` | Integration (no auto-builds) | ❌ No | N/A |
| `test` | Test environment | ✅ Yes | `{version}-test`, `test`, `test-latest` |
| `staging` | Pre-production validation | ✅ Yes | `{version}-staging`, `staging` |
| `main` | Production releases | ✅ Yes | `{version}`, `{major}`, `{minor}`, `latest`, `production` |

**Quick Reference**:
```
Feature Branch → dev → test → staging → main
                (no builds) ↓     ↓        ↓
                          test  staging production
```

## Developer Workflow

### 1. Feature Development

Work on a feature branch and create PR to `dev`:

```bash
# Create feature branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# Make changes, commit with conventional commits
git add .
git commit -m "feat: add new feature"
git push origin feature/my-feature

# Create PR to dev branch via GitHub
# After review and approval, merge to dev
```

**Result**: No automatic builds (dev branch does not trigger CI)

### 2. Test Environment

When ready to test, promote to test branch:

```bash
# Create PR from dev to test
git checkout test
git pull origin test
git merge dev
git push origin test

# Or via GitHub: Create PR dev → test
```

**Result**: Automatic build triggered, creates `test` images

```bash
# Deploy test image (if using Docker Compose)
cd docker
docker-compose -f compose.test.yml pull
docker-compose -f compose.test.yml up -d

# Run integration tests
# Verify functionality
```

### 3. Staging Deployment

When dev is stable, promote to staging:

```bash
# Create PR from test to staging
git checkout staging
git pull origin staging
git merge test
git push origin staging

# Or via GitHub: Create PR test → staging
```

**Result**: Automatic build triggered, creates `staging` images

```bash
# Deploy staging image (if using Docker Compose)
cd docker
docker-compose -f compose.staging.yml pull
docker-compose -f compose.staging.yml up -d

# Run acceptance tests
# Verify pre-production environment
```

### 4. Production Release

When staging is validated, create release:

```bash
# Create PR from staging to main
# Ensure commits follow conventional commit format

# After approval, merge staging to main
git checkout main
git pull origin main
git merge staging
git push origin main
```

**Result**: 
- ✅ Semantic-release analyzes commits
- ✅ Determines version bump (major/minor/patch)
- ✅ Updates CHANGELOG.md
- ✅ Builds Python wheel
- ✅ Creates GitHub Release with assets
- ✅ Builds and pushes production Docker images
- ✅ Commits version changes back to main

### Complete Promotion Pipeline

Full end-to-end workflow from feature development to production deployment:

```bash
# 1. Feature Development
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# Make changes with conventional commits
git add .
git commit -m "feat: add new API endpoint"
git push origin feature/my-feature

# Create PR to dev branch
# After review and approval, merge to dev

# 2. Promote to Test
git checkout test
git pull origin test
git merge dev
git push origin test
# ✅ Automatic build triggered → creates test images

# 3. Test in Test Environment
# Visit test environment and run integration tests
# URL: http://test-server:8001/docs

# 4. Promote to Staging
git checkout staging
git pull origin staging
git merge test
git push origin staging
# ✅ Automatic build triggered → creates staging images

# 5. Validate in Staging
# Visit staging environment and run acceptance tests
# URL: http://staging-server:8002/docs

# 6. Promote to Production
git checkout main
git pull origin main
git merge staging
git push origin main
# ✅ Semantic-release triggered → creates production images, tags, changelog

# 7. Deploy to Production Server
ssh production-server
cd /opt/swedeb-api

# Check new version from GitHub releases
NEW_VERSION=$(curl -s https://api.github.com/repos/humlab-swedeb/swedeb-api/releases/latest | grep '"tag_name"' | sed 's/.*"v\(.*\)".*/\1/')

# Update to new version
sed -i "s/SWEDEB_IMAGE_TAG=.*/SWEDEB_IMAGE_TAG=${NEW_VERSION}/" .env
podman pull ghcr.io/humlab-swedeb/swedeb-api:${NEW_VERSION}
systemctl --user restart swedeb-api-production

# 8. Verify Production Deployment
systemctl --user status swedeb-api-production
journalctl --user -u swedeb-api-production -n 100
curl https://your-domain.com/docs
```

## Commit Message Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types and Version Impact

| Type | Version Bump | Example |
|------|-------------|---------|
| `feat:` | **minor** (0.6.0 → 0.7.0) | `feat: add new API endpoint` |
| `fix:` | **patch** (0.6.0 → 0.6.1) | `fix: resolve database connection issue` |
| `BREAKING CHANGE:` | **major** (0.6.0 → 1.0.0) | `feat!: redesign API (BREAKING CHANGE)` |
| `chore:` | **none** | `chore: update dependencies` |
| `docs:` | **none** | `docs: update README` |
| `ci:` | **patch** (if scope `ci-*`) | `ci(ci-build): optimize workflow` |

### Examples

```bash
# Minor version bump (new feature)
git commit -m "feat: add user authentication"

# Patch version bump (bug fix)
git commit -m "fix: correct typo in error message"

# Major version bump (breaking change)
git commit -m "feat!: redesign API endpoints

BREAKING CHANGE: All endpoints now use /v2/ prefix"

# No release (maintenance)
git commit -m "chore: update package dependencies"
git commit -m "docs: add deployment guide"
```

## CI/CD Architecture

### Unified Build Strategy

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
                   │  1. Auto-detect GIT_BRANCH           │
                   │  2. Login to GHCR                    │
                   │  3. Parse version components         │
                   │  4. Build with environment tags      │
                   │     + --build-arg GIT_BRANCH         │
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

### Key Components

#### 1. Unified Build Script
**File**: `.github/scripts/build-and-push-image.sh`

**Purpose**: Single source of truth for building and pushing Docker images

**Parameters**:
- `<version>`: Semantic version (e.g., 0.6.1)
- `<environment>`: `test`, `staging`, or `production`

**Environment Variables**:
- `DOCKER_USERNAME`: GitHub actor
- `DOCKER_PASSWORD`: GitHub token
- `CWB_REGISTRY_TOKEN`: Personal token for cross-org access (optional)
- `GITHUB_REPOSITORY`: Org/repo name
- `GITHUB_REF_NAME`: Git branch name (auto-detected in CI)

#### 2. Test Build Flow

```
test branch push
  → GitHub Actions triggers test.yml
    → Checkout code
    → Get version from pyproject.toml
    → Login to GHCR
    → Run build-and-push-image.sh test
      → Auto-detects branch: test
      → Builds Docker image with --build-arg GIT_BRANCH=test
      → Tags: {version}-test, test, test-latest
      → Pushes to GHCR
```

#### 3. Staging Build Flow

```
staging branch push
  → GitHub Actions triggers staging.yml
    → Checkout code
    → Get version from pyproject.toml
    → Login to GHCR
    → Run build-and-push-image.sh staging
      → Auto-detects branch: staging
      → Builds Docker image with --build-arg GIT_BRANCH=staging
      → Tags: {version}-staging, staging
      → Pushes to GHCR
```

#### 4. Production Release Flow

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
          → Auto-detects branch: main
          → Builds Docker image with --build-arg GIT_BRANCH=main
          → Tags: {version}, {major}, {minor}, latest, production
          → Pushes to GHCR
        → Commits CHANGELOG.md back to main
```

### Frontend Version Auto-Detection

The build script automatically passes `GIT_BRANCH` to Docker builds, enabling the container to auto-detect which frontend version to download:

- **main/master branch** → Downloads `latest` frontend release
- **staging branch** → Downloads `staging` frontend pre-release
- **test branch** → Downloads `test` frontend pre-release

This ensures branch alignment without manual configuration.

### Workflow Comparison

| Aspect | Test | Staging | Production |
|--------|------|---------|------------|
| **Trigger** | Push to `test` | Push to `staging` | Push to `main` |
| **Versioning** | From pyproject.toml | From pyproject.toml | Semantic-release |
| **Build Script** | `build-and-push-image.sh` | `build-and-push-image.sh` | `build-and-push-image.sh` |
| **Environment Arg** | `test` | `staging` | `production` |
| **Tags Created** | 3 tags | 2 tags | 5 tags |
| **Changelog** | ❌ Not updated | ❌ Not updated | ✅ Auto-generated |
| **GitHub Release** | ❌ Not created | ❌ Not created | ✅ Created with assets |
| **Python Wheel** | ❌ Not built | ❌ Not built | ✅ Built and attached |

## Hotfix Procedures

### Option 1: Fast-track Through Pipeline (Recommended)

```bash
git checkout dev
git checkout -b hotfix/critical-fix

# Make fix with conventional commit
git commit -m "fix: resolve critical security issue"
git push origin hotfix/critical-fix

# Fast-track PRs:
# 1. PR hotfix → dev → merge
# 2. PR dev → test → merge → test in test environment
# 3. PR test → staging → merge → validate in staging
# 4. PR staging → main → merge → deploys to production

# Backport to all branches
git checkout test && git cherry-pick <commit-hash> && git push
git checkout staging && git cherry-pick <commit-hash> && git push
```

### Option 2: Direct to Main (Emergency Only)

```bash
git checkout main
git checkout -b hotfix/emergency

# Make fix
git commit -m "fix: critical production issue"
git push origin hotfix/emergency

# Create PR to main
# After merge, semantic-release creates new version

# Backport to all branches
git checkout staging && git cherry-pick <commit-hash> && git push
git checkout test && git cherry-pick <commit-hash> && git push
git checkout dev && git cherry-pick <commit-hash> && git push
```

## Manual Deployments

### Deploy Specific Version

```bash
# Via GitHub CLI
gh workflow run test.yml -f version=0.6.1
gh workflow run staging.yml -f version=0.6.1

# Or via GitHub UI:
# Actions → Deploy to Test/Staging → Run workflow → Enter version
```

## Image Tag Reference

All images published to `ghcr.io/humlab-swedeb/swedeb-api`

### Test Tags
- `0.6.1-test` - Specific test build
- `test` - Latest test build (moves with each test push)
- `test-latest` - Alias for latest test build

### Staging Tags
- `0.6.1-staging` - Specific staging build
- `staging` - Latest staging build (moves with each staging push)

### Production Tags
- `0.6.1` - Specific production version
- `0.6` - Latest 0.6.x version (moves with patch releases)
- `0` - Latest 0.x.x version (moves with minor releases)
- `latest` - Latest production release
- `production` - Alias for latest production

## Best Practices

1. **Always use conventional commits** - Ensures proper versioning and changelog generation
2. **No auto-builds on dev** - Keep dev as a stable integration point without CI overhead
3. **Test on test branch** - Catch issues in test environment before staging
4. **Validate on staging** - Final check before production to catch environment-specific issues
5. **Use PRs for promotion** - Maintain code review process and audit trail
6. **Pin specific versions** - Avoid using `latest` in production configuration
7. **Monitor deployments** - Check GitHub Actions workflow runs for build status
8. **Document breaking changes** - Use `BREAKING CHANGE:` footer in commits
9. **Keep branches in sync** - Regularly backport fixes to all active branches
10. **Review semantic-release output** - Verify version bumps and changelog entries

## Local Development

### Prerequisites
- Python 3.12+
- Poetry for dependency management
- Docker (optional, for containerized development)
- CWB data files (see [sample-data repository](https://github.com/humlab-swedeb/sample-data))

### Setup

```bash
# Clone repository
git clone https://github.com/humlab-swedeb/swedeb-api.git
cd swedeb-api

# Install dependencies
poetry install

# Configure environment
cp .env_example .env
# Edit .env with your data paths

# Run development server
poetry run uvicorn main:app --reload

# View API documentation
# Swagger UI: http://127.0.0.1:8000/docs
# ReDoc: http://127.0.0.1:8000/redoc
```

### Common Commands

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
make profile-kwic-pyinstrument   # Profile KWIC queries
```

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Complete deployment instructions
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [AI Coding Instructions](../.github/copilot-instructions.md) - Guide for AI assistants
