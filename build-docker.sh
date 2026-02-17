#!/bin/bash
# Build script that works around Docker BuildKit proxy timeout issues
# 
# Issue: Docker BuildKit times out when using proxy (http.docker.internal:3128)
# Solution: Disable BuildKit for builds since regular docker pull works fine

echo "=========================================="
echo "Docker Build Script (BuildKit Disabled)"
echo "=========================================="
echo ""
echo "Building Docker containers with BuildKit disabled to avoid proxy timeouts..."
echo "Note: BuildKit is disabled because it times out with the configured proxy."
echo ""

# Disable BuildKit to use legacy builder (which handles proxy better)
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# Verify docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose command not found"
    exit 1
fi

# Run docker-compose build
echo "Starting build..."
docker-compose build "$@"

echo ""
echo "=========================================="
echo "Build completed successfully!"
echo "=========================================="
