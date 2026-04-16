# Frontend Asset Download - Bug Fixes

## Issues Fixed

### 1. Tag vs Tarball Naming Mismatch (Critical Bug)

**Problem**: 
- GitHub releases are tagged as `v1.2.3`
- Tarball assets are named `frontend-1.2.3.tar.gz` (no 'v' prefix)
- Script tried to download `frontend-v1.2.3.tar.gz` → 404 error

**Fix** in `download-frontend.sh`:
```bash
# Before
VERSION=$(curl ... | grep '"tag_name"' | cut -d '"' -f 4)  # Gets "v1.2.3"
TARBALL="frontend-${VERSION}.tar.gz"                      # "frontend-v1.2.3.tar.gz" ❌

# After  
VERSION_TAG=$(curl ... | grep '"tag_name"' | cut -d '"' -f 4)  # Gets "v1.2.3"
VERSION=${VERSION_TAG#v}                                        # Strip 'v' → "1.2.3"
TARBALL="frontend-${VERSION}.tar.gz"                           # "frontend-1.2.3.tar.gz" ✓
```

### 2. Missing Test Branch Support

**Problem**: 
- Script handled `latest` and `staging` but not `test`
- Test branch releases would fail

**Fix** in `download-frontend.sh`:
```bash
# Before
elif [ "$FRONTEND_VERSION" = "staging" ]; then
    # staging-specific logic

# After
elif [ "$FRONTEND_VERSION" = "staging" ] || [ "$FRONTEND_VERSION" = "test" ]; then
    # Unified logic for both staging and test branches
    VERSION="${FRONTEND_VERSION}"
    RELEASE_INFO=$(curl ... /releases/tags/${FRONTEND_VERSION})
    TARBALL=$(echo "$RELEASE_INFO" | grep -o "frontend-[^\"]*-${FRONTEND_VERSION}\.tar\.gz" ...)
```

### 3. Version Specification Flexibility

**Problem**:
- Users might specify `FRONTEND_VERSION=v1.2.3` (with 'v')
- Script didn't handle this case

**Fix** in `download-frontend.sh`:
```bash
# Now strips 'v' prefix if present
VERSION=${FRONTEND_VERSION#v}
# Detects semantic version pattern
if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+ ]]; then
    VERSION_TAG="v${VERSION}"
    TARBALL="frontend-${VERSION}.tar.gz"
```

### 4. Version Comparison Normalization

**Problem**:
- `.frontend_version` file might contain `1.2.3`
- User specifies `FRONTEND_VERSION=v1.2.3`
- String comparison fails, triggers unnecessary re-download

**Fix** in `entrypoint.sh`:
```bash
# Before
if [ "$CURRENT_VERSION" != "$FRONTEND_VERSION" ]; then

# After
REQUESTED_VERSION=${FRONTEND_VERSION#v}
CACHED_VERSION=${CURRENT_VERSION#v}
if [ "$CACHED_VERSION" != "$REQUESTED_VERSION" ]; then
```

## Testing the Fixes

### Test Case 1: Latest Release
```bash
export FRONTEND_VERSION=latest
./download-frontend.sh
# Should download: frontend-1.2.3.tar.gz (not frontend-v1.2.3.tar.gz)
# Version file contains: 1.2.3
```

### Test Case 2: Staging Branch
```bash
export FRONTEND_VERSION=staging
./download-frontend.sh
# Should query staging pre-release
# Should download: frontend-1.2.3-staging.tar.gz
# Version file contains: staging
```

### Test Case 3: Test Branch (Previously Broken)
```bash
export FRONTEND_VERSION=test
./download-frontend.sh
# Should query test pre-release
# Should download: frontend-1.2.3-test.tar.gz
# Version file contains: test
```

### Test Case 4: Specific Version Without 'v'
```bash
export FRONTEND_VERSION=1.2.3
./download-frontend.sh
# Should construct tag: v1.2.3
# Should download: frontend-1.2.3.tar.gz
# Version file contains: 1.2.3
```

### Test Case 5: Specific Version With 'v' (Previously Broken)
```bash
export FRONTEND_VERSION=v1.2.3
./download-frontend.sh
# Should strip 'v' to get: 1.2.3
# Should construct tag: v1.2.3
# Should download: frontend-1.2.3.tar.gz
# Version file contains: 1.2.3
```

### Test Case 6: Version Comparison (Previously Broken)
```bash
# Scenario: Version file contains "1.2.3", user specifies "v1.2.3"
echo "1.2.3" > /app/public/.frontend_version
export FRONTEND_VERSION=v1.2.3
./entrypoint.sh
# Should NOT trigger download (normalized comparison: 1.2.3 == 1.2.3)
```

## Impact Assessment

### Before Fixes
- ❌ Production deployments with `FRONTEND_VERSION=latest` would fail (404 on tarball)
- ❌ Test branch deployments would fail (no handler)
- ❌ Users specifying `v1.2.3` would fail
- ❌ Unnecessary re-downloads on container restart with 'v' prefix mismatch

### After Fixes
- ✅ All version formats work correctly
- ✅ All branches (main, staging, test) supported
- ✅ Normalized version comparison prevents unnecessary downloads
- ✅ Robust handling of GitHub release naming conventions

## Related Files Changed

1. `/home/roger/source/swedeb/swedeb-api/docker/download-frontend.sh`
   - Fixed tag vs tarball naming
   - Added test branch support
   - Added version normalization

2. `/home/roger/source/swedeb/swedeb-api/docker/entrypoint.sh`
   - Added normalized version comparison
   - Handles 'v' prefix in both cached and requested versions

3. `/home/roger/source/swedeb/swedeb-api/docs/FRONTEND_ASSET_FLOW.md`
   - New documentation explaining complete flow
   - Usage examples for all scenarios
   - Troubleshooting guide
