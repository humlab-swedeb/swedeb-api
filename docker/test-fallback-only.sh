#!/bin/bash
# Test script to verify fallback tarball works when GitHub is unreachable

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Testing Fallback Tarball (GitHub blocked)"
echo "=========================================="
echo ""

# Build image if needed
if ! docker images | grep -q "swedeb-api:local-test"; then
    echo "Image not found, building..."
    cd ..
    uv build --wheel --out-dir wheels
    docker build -t swedeb-api:local-test -f docker/Dockerfile \
        --build-arg GIT_BRANCH=dev \
        --build-arg FRONTEND_VERSION=staging \
        .
    cd docker
fi

# Prepare fallback tarball
echo "Preparing fallback tarball..."
mkdir -p test-data/dist

# Download tarball for fallback if not present
if [ ! -f test-data/dist/frontend-staging.tar.gz ]; then
    echo "Downloading frontend tarball for fallback testing..."
    curl -fsSL -o test-data/dist/frontend-staging.tar.gz \
        "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/staging/frontend-staging.tar.gz"
    echo "✓ Fallback tarball downloaded"
else
    echo "✓ Fallback tarball already exists"
fi

# Clean up old container
docker rm -f swedeb-api-fallback-test 2>/dev/null || true

echo ""
echo "Starting container with NO NETWORK ACCESS..."
echo "This forces GitHub download to fail and trigger fallback"
echo ""
echo "=========================================="
echo "Container Output:"
echo "=========================================="
echo ""

# Run container with NO network (--network=none) BUT mount fallback tarball
docker run --rm --name swedeb-api-fallback-test \
    --network=none \
    -v "$(pwd)/test-data/dist:/data/dist:Z,ro" \
    -e FRONTEND_VERSION=staging \
    -e CORPUS_REGISTRY=/data/registry \
    swedeb-api:local-test 2>&1 | tee /tmp/fallback-test.log &

CONTAINER_PID=$!

# Wait for container to start or fail (max 60 seconds)
echo ""
echo "Waiting for container startup (max 60 seconds)..."
for i in {1..60}; do
    if ! kill -0 $CONTAINER_PID 2>/dev/null; then
        break
    fi
    if grep -q "Uvicorn running" /tmp/fallback-test.log 2>/dev/null; then
        echo "✓ Server started successfully"
        break
    fi
    sleep 1
done

# Kill container
docker rm -f swedeb-api-fallback-test 2>/dev/null || true
wait $CONTAINER_PID 2>/dev/null || true

echo ""
echo "=========================================="
echo "Test Results:"
echo "=========================================="
echo ""

# Check results
if grep -q "GitHub download failed" /tmp/fallback-test.log; then
    echo "✓ GitHub download failed (as expected - no network)"
else
    echo "✗ GitHub download did not fail (unexpected)"
fi

if grep -q "Falling back to local tarball" /tmp/fallback-test.log; then
    echo "✓ Fallback was TRIGGERED"
else
    echo "✗ Fallback was NOT triggered"
fi

if grep -q "Successfully copied from local fallback" /tmp/fallback-test.log; then
    echo "✓ Fallback tarball was used successfully"
else
    echo "✗ Fallback tarball was not used"
fi

if grep -q "Frontend assets successfully downloaded and extracted" /tmp/fallback-test.log; then
    echo "✓ Overall extraction SUCCESS"
else
    echo "✗ Overall extraction FAILED"
fi

if grep -q "Uvicorn running on http://0.0.0.0:8092" /tmp/fallback-test.log; then
    echo "✓ Server started successfully"
else
    echo "✗ Server failed to start"
fi

echo ""
echo "Full log saved to: /tmp/fallback-test.log"
echo ""
echo "Key log excerpts:"
echo "----------------------------------------"
grep -E "GitHub download|Falling back|fallback|Frontend assets successfully" /tmp/fallback-test.log | head -10
