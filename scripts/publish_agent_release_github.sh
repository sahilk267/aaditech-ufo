#!/usr/bin/env bash
set -euo pipefail

# Publish a built aaditech-agent EXE to a running server via the API upload endpoint.
# Expects these env vars or args:
#   AGENT_PUBLISH_URL (e.g. https://example.com)
#   AGENT_PUBLISH_TOKEN (bearer token)
# Usage:
#   AGENT_PUBLISH_URL=https://host AGENT_PUBLISH_TOKEN=token ./scripts/publish_agent_release_github.sh /path/to/aaditech-agent-1.0.0.exe 1.0.0

SOURCE_FILE="$1"
VERSION="$2"

if [[ -z "${AGENT_PUBLISH_URL:-}" || -z "${AGENT_PUBLISH_TOKEN:-}" ]]; then
  echo "AGENT_PUBLISH_URL and AGENT_PUBLISH_TOKEN must be set"
  exit 1
fi

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "Source file not found: ${SOURCE_FILE}"
  exit 1
fi

curl -v -X POST \
  -H "Authorization: Bearer ${AGENT_PUBLISH_TOKEN}" \
  -F "release_file=@${SOURCE_FILE}" \
  -F "version=${VERSION}" \
  "${AGENT_PUBLISH_URL%/}/api/agent/releases/upload"
