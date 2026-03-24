#!/usr/bin/env bash
set -euo pipefail

# Generates an OCI-friendly image tag.
# Priority:
# 1) explicit IMAGE_TAG env
# 2) git tag on HEAD
# 3) branch-shortsha

if [[ -n "${IMAGE_TAG:-}" ]]; then
  echo "${IMAGE_TAG}"
  exit 0
fi

if git describe --tags --exact-match >/dev/null 2>&1; then
  tag="$(git describe --tags --exact-match)"
  tag="${tag#v}"
  echo "${tag}"
  exit 0
fi

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'detached')"
sha="$(git rev-parse --short HEAD 2>/dev/null || echo 'nogit')"

# Normalize to safe docker tag chars
safe_branch="$(echo "${branch}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g')"
echo "${safe_branch}-${sha}"
