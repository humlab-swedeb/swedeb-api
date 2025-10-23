# Four-Branch Workflow Guide

## Quick Reference

```
Feature Branch → dev → test → staging → main
                (no builds) ↓     ↓        ↓
                          test  staging production
```

## Branch Strategy

| Branch | Purpose | Auto-Deploy | Image Tags |
|--------|---------|-------------|------------|
| `dev` | Integration (no auto-builds) | ❌ No | N/A |
| `test` | Test environment | ✅ Yes | `{version}-test`, `test`, `test-latest` |
| `staging` | Pre-production validation | ✅ Yes | `{version}-staging`, `staging` |
| `main` | Production releases | ✅ Yes | `{version}`, `{major}`, `{minor}`, `latest`, `production` |

## Developer Workflow

### 1. Feature Development

Work on a feature branch and PR to `dev`:

```bash
# Create feature branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# Make changes, commit with conventional commits
git add .
git commit -m "feat: add new feature"
git push origin feature/my-feature

# Create PR to dev branch
# After approval, merge to dev
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
# Deploy test image
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
# Deploy staging image
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
# Minor version bump
git commit -m "feat: add user authentication"

# Patch version bump
git commit -m "fix: correct typo in error message"

# Major version bump
git commit -m "feat!: redesign API endpoints

BREAKING CHANGE: All endpoints now use /v2/ prefix"

# No release
git commit -m "chore: update package dependencies"
git commit -m "docs: add deployment guide"
```

## Rollback Procedures

### Test Rollback
```bash
# Revert to previous test image
cd docker
docker-compose -f compose.test.yml down
docker pull ghcr.io/humlab-swedeb/swedeb-api:{previous-version}-test
# Update compose.test.yml to use specific version
docker-compose -f compose.test.yml up -d
```

### Staging Rollback
```bash
# Use specific staging version
docker pull ghcr.io/humlab-swedeb/swedeb-api:{previous-version}-staging
# Update compose.staging.yml
docker-compose -f compose.staging.yml up -d
```

### Production Rollback
```bash
# Use specific production version
docker pull ghcr.io/humlab-swedeb/swedeb-api:{previous-version}
# Update compose.production.yml
docker-compose -f compose.production.yml up -d
```

## Hotfix Procedure

For urgent production fixes:

```bash
# Option 1: Fast-track through pipeline
git checkout dev
git pull origin dev
git checkout -b hotfix/urgent-fix

# Make fix with conventional commit
git commit -m "fix: resolve critical security issue"

# Fast-track: PR to dev → merge → PR to test → merge → PR to staging → merge → PR to main
```

```bash
# Option 2: Direct to main (emergency only)
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix

# Make fix
git commit -m "fix: resolve critical production issue"
git push origin hotfix/critical-fix

# Create PR to main
# After merge, backport to test, staging and dev
git checkout test
git cherry-pick <commit-hash>
git push origin test

git checkout staging
git cherry-pick <commit-hash>
git push origin staging

git checkout dev
git cherry-pick <commit-hash>
git push origin dev
```

## Manual Deployments

### Deploy Specific Version

```bash
# Test
gh workflow run test.yml -f version=0.6.1

# Staging
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

1. **Always use conventional commits** - Ensures proper versioning
2. **No auto-builds on dev** - Keep dev as a stable integration point
3. **Test on test branch** - Catch issues in test environment
4. **Validate on staging** - Final check before production
5. **Use PRs for promotion** - Maintain code review process
6. **Tag specific versions** - Avoid using `latest` in production compose files
7. **Monitor deployments** - Check workflow runs in GitHub Actions
8. **Document breaking changes** - Use BREAKING CHANGE footer in commits
