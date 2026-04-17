#!/bin/bash
# Test script to simulate read-only /app/public and verify workaround works

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Testing /tmp Workaround for Read-Only FS"
echo "=========================================="
echo ""

# Build image if needed
if ! podman images | grep -q "swedeb-api:local-test"; then
    echo "Image not found, building..."
    cd ..
    uv build --wheel --out-dir wheels
    podman build -t swedeb-api:local-test -f docker/Dockerfile \
        --build-arg GIT_BRANCH=dev \
        --build-arg FRONTEND_VERSION=staging \
        .
    cd docker
fi

# Create a read-only public directory mount
echo "Setting up read-only /app/public simulation..."
mkdir -p test-data/public-readonly
chmod 555 test-data/public-readonly  # Make it read-only

# Clean up old container
podman rm -f swedeb-api-readonly-test 2>/dev/null || true

echo ""
echo "Starting container with READ-ONLY /app/public..."
echo "This should trigger the /tmp extraction workaround"
echo ""
echo "=========================================="
echo "Container Output:"
echo "=========================================="
echo ""

# Run container with read-only /app/public mount
podman run --rm --name swedeb-api-readonly-test \
    -p 8093:8092 \
    -v "$(pwd)/test-data/public-readonly:/app/public:Z,ro" \
    -e FRONTEND_VERSION=staging \
    -e CORPUS_REGISTRY=/data/registry \
    swedeb-api:local-test 2>&1 | tee /tmp/readonly-test.log

# Check results
echo ""
echo "=========================================="
echo "Test Results:"
echo "=========================================="
echo ""

if grep -q "Attempting workaround: extract to /tmp and copy" /tmp/readonly-test.log; then
    echo "✓ Workaround was TRIGGERED (as expected)"
else
    echo "✗ Workaround was NOT triggered (unexpected)"
fi

if grep -q "Successfully copied files to /app/public" /tmp/readonly-test.log; then
    echo "✓ Files successfully copied from /tmp to /app/public"
else
    echo "✗ Copy from /tmp failed"
fi

if grep -q "Frontend assets successfully downloaded and extracted" /tmp/readonly-test.log; then
    echo "✓ Overall extraction SUCCESS"
else
    echo "✗ Overall extraction FAILED"
fi

if grep -q "Uvicorn running on http://0.0.0.0:8092" /tmp/readonly-test.log; then
    echo "✓ Server started successfully"
else
    echo "✗ Server failed to start"
fi

echo ""
echo "Full log saved to: /tmp/readonly-test.log"
