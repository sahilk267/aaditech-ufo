#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

VERSION_TAG="$(./scripts/docker_image_version.sh)"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-sahilk267}"
IMAGE_NAME="${IMAGE_NAME:-aaditech-ufo}"
FULL_IMAGE="${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}:${VERSION_TAG}"
LATEST_IMAGE="${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/${IMAGE_NAME}:latest"

echo "[docker] Building ${FULL_IMAGE}"
docker build -t "${FULL_IMAGE}" -t "${LATEST_IMAGE}" .

if [[ "${PUSH_IMAGE:-false}" != "true" ]]; then
  echo "[docker] Build complete. Skipping push (set PUSH_IMAGE=true to publish)."
  exit 0
fi

if [[ -n "${DOCKER_USERNAME:-}" && -n "${DOCKER_PASSWORD:-}" ]]; then
  echo "${DOCKER_PASSWORD}" | docker login "${IMAGE_REGISTRY}" -u "${DOCKER_USERNAME}" --password-stdin
fi

echo "[docker] Pushing ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"
echo "[docker] Pushing ${LATEST_IMAGE}"
docker push "${LATEST_IMAGE}"

echo "[docker] Published: ${FULL_IMAGE}"
