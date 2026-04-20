# Proposal: Local Container Testing Workflow

**Status:** Deferred  
**Created:** 2026-04-20  
**Author:** System Analysis  
**Type:** Developer Experience / Tooling

## Problem Statement

Developers need a reliable way to test Docker container builds and runtime behavior locally before pushing changes to CI/CD. This is critical for:

1. **Build Validation** - Verifying that the Dockerfile builds successfully with current code changes
2. **Integration Testing** - Testing the interaction between API backend and frontend assets within the container
3. **Production Parity** - Ensuring local testing mirrors the actual CI/CD build process
4. **Rapid Iteration** - Quick feedback loops when debugging container-specific issues
5. **Deployment Confidence** - Catching issues before they reach staging/production environments

## Intent of Removed Files

The following files were removed as part of cleanup but represent a valid testing workflow that should be redesigned:

### 1. `docker/test-local.sh` (Interactive Testing Script)

**Purpose:** Comprehensive local container testing with rich developer experience

**Key Features:**
- Build and run containers locally with detailed logging and colored output
- Multiple testing modes:
  - Full build with bundled frontend assets
  - Skip-build mode for rapid testing of existing images
  - REPL mode for frontend development (mount local dist directory)
  - Podman/Docker interchangeability
- Frontend asset management:
  - Download frontend from GitHub releases during build
  - Optional local frontend mounting for rapid iteration
  - Validation of frontend presence and version
- Error handling and diagnostics:
  - Detailed build/run logs saved to `/tmp/`
  - Color-coded success/warning/error messages
  - Container cleanup between runs

**Command Examples:**
```bash
./test-local.sh                              # Full build + run
./test-local.sh --skip-build                 # Test existing image
./test-local.sh --frontend-dir ../dist       # Mount local frontend
./test-local.sh --podman                     # Use Podman
```

### 2. `docker/build-local-image.sh` (CI Build Mirror)

**Purpose:** Thin wrapper to build locally using the exact same script as GitHub Actions

**Design Philosophy:**
- Single source of truth: reuses `.github/scripts/build-and-push-image.sh`
- Environment-aware: supports test/staging/production build variants
- Registry-agnostic: sets `SKIP_PUSH=1` to avoid registry authentication
- Version-aware: extracts version from `uv version` output

**Workflow:**
```bash
./build-local-image.sh staging  # Builds swedeb-api:staging locally
```

### 3. `docker/compose.local.yml` (Declarative Testing)

**Purpose:** Docker Compose configuration for local testing with volume mounts

**Configuration:**
- Build from local Dockerfile (not pre-built image)
- Mount local data directory for corpus/metadata
- Simplified environment variables
- Named network for isolation
- Optional frontend mount for debugging

**Use Case:** Developers who prefer `docker compose up` over shell scripts

### 4. `docker/DOCKER_BUILD_TESTING.md` (Comprehensive Documentation)

**Purpose:** Complete guide to local container testing workflows

**Content:**
- Quick start commands via Makefile targets
- Detailed explanation of build process and frontend bundling
- Debugging guide with common issues and solutions
- REPL development workflow for frontend iteration
- Before-push checklist
- Comparison of testing modes

**Makefile Integration:**
- `make test-local` → Full build and run
- `make test-local-podman` → Test with Podman
- `make test-local-skip-build` → Skip build step
- `make test-local-repl` → Frontend development mode
- `make test-clean` → Cleanup artifacts

## Core Design Principles (To Preserve)

### 1. Production Parity
- Local builds must mirror CI/CD builds exactly
- Same Dockerfile, same build arguments, same frontend download
- Environment-specific configurations (test/staging/production)

### 2. Developer Experience
- Rich, color-coded terminal output
- Clear error messages with diagnostic logs
- Multiple workflow modes for different use cases
- Documentation-driven with examples

### 3. Frontend Asset Management
- Frontend downloaded from GitHub releases during build (matches production)
- Baked into image at build time (ReadOnly filesystem compatible)
- Optional local mount for rapid frontend development
- Version tracking and validation

### 4. Flexibility
- Support both Docker and Podman
- Interactive scripts AND declarative compose files
- Skip-build options for faster iteration
- Local frontend mounting for REPL workflow

### 5. Maintainability
- Single source of truth for build logic (reuse CI scripts)
- Clear separation: build-local-image.sh vs test-local.sh
- Makefile targets for discoverability

## Why Removed / Why Deferred

The current implementation has several issues that warrant a redesign:

1. **Build Context Mismatch** - Recently discovered that the Dockerfile COPY paths were inconsistent with build context
2. **Complexity Creep** - test-local.sh has grown with legacy flags (--use-fallback, --mount-public) that are deprecated
3. **Documentation Drift** - DOCKER_BUILD_TESTING.md references workflows that have evolved
4. **Unclear Ownership** - Overlap between build-local-image.sh and test-local.sh purposes
5. **Missing Test Coverage** - Scripts are not tested by CI, can drift from production builds

## Future Redesign Considerations

When recreating this workflow, consider:

### Architecture
- [ ] Consolidate build-local-image.sh and test-local.sh into single coherent tool
- [ ] Use build context consistently (docker/ directory vs repo root)
- [ ] Remove deprecated flags and simplify option parsing
- [ ] Consider using existing tools (docker compose watch, Tilt, etc.) vs custom scripts

### Testing
- [ ] Add CI validation that local build script produces working images
- [ ] Test matrix: Docker/Podman × test/staging/production
- [ ] Verify frontend asset download and version matching

### Documentation
- [ ] Single source of truth for local testing workflow
- [ ] Clear separation: "local dev" (uvicorn) vs "local container test"
- [ ] Troubleshooting guide with actual error messages from recent issues

### Developer Experience
- [ ] Maintain colored, informative output
- [ ] Keep multiple modes (full build, skip-build, frontend-only)
- [ ] Consider watch mode for rapid iteration
- [ ] Integration with VSCode/IDE debugging

### Podman Compatibility
- [ ] Ensure scripts work with both Docker and Podman
- [ ] Test with SELinux (`:Z` volume flags)
- [ ] Validate against production Podman deployment

## Related Work

- **CI/CD Build Script** - `.github/scripts/build-and-push-image.sh` (already correct, builds from docker/ context)
- **Production Deployment** - `docker/quadlets/app.container` (Podman quadlet with volume mounts)
- **Local Development** - `README.md` (uvicorn + pnpm dev, no containers)

## References

- Original discussion: GitHub Actions build error due to Dockerfile COPY path mismatch
- Root cause: Commit a9df23c removed `docker/config/` but Dockerfile still referenced it
- Fix applied: Updated Dockerfile to match docker/ build context

## Next Steps

When ready to recreate this workflow:

1. Review this proposal and update design decisions
2. Choose architecture: custom script vs existing tool (compose watch, Tilt, etc.)
3. Implement with clear separation of concerns
4. Add CI validation of local build process
5. Document with examples from actual usage
6. Test across Docker/Podman and all environments

---

**Note:** This proposal captures the intent and design of the removed local testing workflow for future reference.
