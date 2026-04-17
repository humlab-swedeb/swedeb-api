#!/bin/bash
# Quick test scenarios for common debugging situations

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════╗
║               Swedeb API Local Testing - Quick Reference                ║
╚══════════════════════════════════════════════════════════════════════════╝

SCENARIO 1: Test the fix for "Assets directory not writable" error
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This tests the /tmp extraction workaround:

    make test-local-podman-fallback

Expected: Container starts successfully using /tmp workaround


SCENARIO 2: Test GitHub download in normal conditions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Full build and test with GitHub download:

    make test-local

Expected: Downloads from GitHub and starts successfully


SCENARIO 3: Test network-isolated deployment (no GitHub access)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Simulates deployment without internet access:

    make test-local-fallback

Expected: Falls back to local tarball and starts successfully


SCENARIO 4: Quick iteration - test script changes without rebuild
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After editing download-frontend.sh or entrypoint.sh:

    # Rebuild only
    docker build -t swedeb-api:local-test -f Dockerfile .. 
    
    # Test without full rebuild
    make test-local-skip-build

Expected: Faster iteration on script changes


SCENARIO 5: Debug inside running container
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Start container in background and debug interactively:

    # Terminal 1: Start container
    docker run --rm --name swedeb-api-local-test \
      -p 8092:8092 \
      -v $(pwd)/test-data/dist:/data/dist:ro \
      swedeb-api:local-test

    # Terminal 2: Get shell
    docker exec -it swedeb-api-local-test /bin/bash
    
    # Inside container:
    ls -la /app/public/
    cat /app/public/.frontend_version
    /app/docker/test-network.sh


SCENARIO 6: Compare writable vs read-only /app/public
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Test both modes to verify workaround is necessary:

    # With writable mount (should work)
    make test-local-mount-public
    
    # Without mount (tests workaround)
    make test-local

Expected: Both should work, second uses /tmp workaround


COMMON COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
make help                  # Show all Makefile targets
./test-local.sh --help     # Show test script options
make test-clean            # Clean up all test artifacts
docker logs -f swedeb-api-local-test   # Follow container logs
docker images | grep swedeb            # List local images


QUICK DIAGNOSTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Check if image exists:
    docker images swedeb-api:local-test

Check if container is running:
    docker ps -a | grep swedeb-api-local-test

Remove stuck container:
    docker rm -f swedeb-api-local-test

Check last build logs:
    cat /tmp/docker-build.log


BEFORE CREATING A PR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Test locally with Podman (mimics production):
   make test-local-podman-fallback

2. Verify container starts and port 8092 responds:
   curl http://localhost:8092/api/v1/health

3. Check logs for errors:
   docker logs swedeb-api-local-test

4. Clean up before committing:
   make test-clean
   git status


DEBUGGING CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Wheel builds successfully
□ Docker image builds without errors
□ Container starts without exiting
□ Frontend assets extracted to /app/public
□ API responds on port 8092
□ No ERROR messages in logs
□ SHA256 caching works (no re-extraction)
□ Fallback works when GitHub unreachable
□ /tmp workaround activates for read-only fs

EOF

# Interactive menu
echo ""
read -p "Run a test scenario? [1-6/n]: " choice

case "$choice" in
    1)
        echo "Running test-local-podman-fallback..."
        make test-local-podman-fallback
        ;;
    2)
        echo "Running test-local..."
        make test-local
        ;;
    3)
        echo "Running test-local-fallback..."
        make test-local-fallback
        ;;
    4)
        echo "Building image..."
        docker build -t swedeb-api:local-test -f Dockerfile ..
        echo "Running test without rebuild..."
        make test-local-skip-build
        ;;
    5)
        echo "Starting container in background..."
        docker run --rm -d --name swedeb-api-local-test \
            -p 8092:8092 \
            -v "$(pwd)/test-data/dist:/data/dist:ro" \
            swedeb-api:local-test
        echo "Getting shell..."
        docker exec -it swedeb-api-local-test /bin/bash
        ;;
    6)
        echo "Running writable mount test..."
        make test-local-mount-public
        echo ""
        echo "Running read-only test..."
        make test-local
        ;;
    n|N|"")
        echo "No test selected. Exiting."
        ;;
    *)
        echo "Invalid choice: $choice"
        exit 1
        ;;
esac
