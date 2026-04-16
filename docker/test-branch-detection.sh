#!/bin/bash
# Test script for frontend version auto-detection logic

set -euo pipefail

log() {
    echo "[TEST] $*"
}

test_branch_detection() {
    local branch=$1
    local expected=$2
    
    # Simulate the detection logic
    case "${branch}" in
        main|master)
            FRONTEND_VERSION="latest"
            ;;
        staging|test)
            FRONTEND_VERSION="${branch}"
            ;;
        *)
            FRONTEND_VERSION="latest"
            ;;
    esac
    
    if [ "$FRONTEND_VERSION" = "$expected" ]; then
        log "✓ Branch '$branch' → '$FRONTEND_VERSION' (expected: $expected)"
        return 0
    else
        log "✗ Branch '$branch' → '$FRONTEND_VERSION' (expected: $expected)"
        return 1
    fi
}

log "Testing frontend version auto-detection logic..."
echo

FAILED=0

test_branch_detection "main" "latest" || FAILED=$((FAILED + 1))
test_branch_detection "master" "latest" || FAILED=$((FAILED + 1))
test_branch_detection "staging" "staging" || FAILED=$((FAILED + 1))
test_branch_detection "test" "test" || FAILED=$((FAILED + 1))
test_branch_detection "feature/my-branch" "latest" || FAILED=$((FAILED + 1))
test_branch_detection "dev" "latest" || FAILED=$((FAILED + 1))

echo
if [ $FAILED -eq 0 ]; then
    log "All tests passed! ✓"
    exit 0
else
    log "$FAILED test(s) failed! ✗"
    exit 1
fi
