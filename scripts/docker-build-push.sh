#!/bin/bash

# Docker Build and Push Script
# Builds and pushes images to a Docker registry
# Usage: ./scripts/docker-build-push.sh [registry] [tag]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
IMAGE_REGISTRY=${1:-ghcr.io}
IMAGE_NAMESPACE=${2:-$(git config user.name | tr '[:upper:]' '[:lower:]')}
IMAGE_NAME=${3:-aaditech-ufo}
IMAGE_TAG=${4:-latest}

# Derived values
IMAGE_URL="${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}"
FULL_IMAGE_TAG="${IMAGE_URL}:${IMAGE_TAG}"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${RC}"
echo -e "${GREEN}║   Docker Build and Push                                   ║${RC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${RC}"
echo ""

echo "Configuration:"
echo "  Registry:  ${IMAGE_REGISTRY}"
echo "  Namespace: ${IMAGE_NAMESPACE}"
echo "  Image:     ${IMAGE_NAME}"
echo "  Tag:       ${IMAGE_TAG}"
echo "  Full Tag:  ${FULL_IMAGE_TAG}"
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${RC}"
    exit 1
fi

echo -e "${YELLOW}[1/3]${RC} Building Docker image..."
cd "$PROJECT_ROOT"

docker build \
    -t "${FULL_IMAGE_TAG}" \
    -t "${IMAGE_URL}:latest" \
    --build-arg PYTHON_VERSION=3.12 \
    --progress=plain \
    -f Dockerfile \
    .

echo ""
echo -e "${YELLOW}[2/3]${RC} Checking Docker credentials..."

# For GitHub Container Registry
if [[ "$IMAGE_REGISTRY" == "ghcr.io" ]]; then
    echo "To push to GitHub Container Registry:"
    echo "  1. Create a GitHub Personal Access Token at: https://github.com/settings/tokens"
    echo "  2. Grant 'write:packages' permission"
    echo "  3. Run: docker login ghcr.io"
    echo "  4. Use your GitHub username and token as password"
fi

echo ""
echo -e "${YELLOW}[3/3]${RC} Pushing image to registry..."

docker push "${FULL_IMAGE_TAG}"
docker push "${IMAGE_URL}:latest"

echo ""
echo -e "${GREEN}✓ Image pushed successfully!${RC}"
echo ""
echo "Use in deployment:"
echo "  docker pull ${FULL_IMAGE_TAG}"
echo "  docker run -e DATABASE_URL=... ${FULL_IMAGE_TAG}"
