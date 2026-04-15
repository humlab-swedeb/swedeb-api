#!/bin/bash
# Health check script to verify both API and frontend assets

set -e

# Check API health
if ! curl -f http://localhost:${SWEDEB_PORT:-8092}/v1/health >/dev/null 2>&1; then
    echo "ERROR: API health check failed"
    exit 1
fi

# Check frontend assets
if [ ! -f "/app/public/index.html" ]; then
    echo "ERROR: Frontend assets not found"
    exit 1
fi

# Check frontend version file
if [ ! -f "/app/public/.frontend_version" ]; then
    echo "WARNING: Frontend version file missing"
fi

echo "Health check passed"
exit 0