#!/usr/bin/env bash
set -euo pipefail

# Register a built Windows agent executable into server release portal storage.
# Usage:
#   ./scripts/publish_agent_release.sh --file /path/to/aaditech-agent.exe --version 1.0.0

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTANCE_DIR="${ROOT_DIR}/instance"
RELEASES_DIR="${AGENT_RELEASES_DIR:-${INSTANCE_DIR}/agent_releases}"

SOURCE_FILE=""
VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      SOURCE_FILE="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ -z "${SOURCE_FILE}" || -z "${VERSION}" ]]; then
  echo "Usage: $0 --file <path-to-exe> --version <version>"
  exit 1
fi

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "Source file not found: ${SOURCE_FILE}"
  exit 1
fi

if [[ "${SOURCE_FILE##*.}" != "exe" ]]; then
  echo "Source file must be .exe"
  exit 1
fi

if [[ ! "${VERSION}" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
  echo "Invalid version format: ${VERSION}"
  exit 1
fi

mkdir -p "${RELEASES_DIR}"
TARGET_FILE="${RELEASES_DIR}/aaditech-agent-${VERSION}.exe"
cp "${SOURCE_FILE}" "${TARGET_FILE}"

echo "Published release: ${TARGET_FILE}"
ls -lh "${TARGET_FILE}"
