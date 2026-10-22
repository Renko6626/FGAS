#!/usr/bin/env bash
# Build the API and web images for linux/amd64 and push them to ACR.
# Run `docker login` for the ACR registry first.
set -euo pipefail
cd "$(dirname "$0")/.."

usage() { echo "Usage: $0 VERSION" >&2; exit 2; }
[[ $# == 1 ]] || usage
version=$1
[[ $version =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ ]] || usage

acr=${FGAS_ACR:-crpi-bug4nt14ryr5n8sw.cn-beijing.personal.cr.aliyuncs.com/renko}
api_repo=${FGAS_API_REPO:-$acr/fgas-api}
web_repo=${FGAS_WEB_REPO:-$acr/fgas}

docker build --platform linux/amd64 -f deploy/Dockerfile -t "$api_repo:$version" .
docker build --platform linux/amd64 -f deploy/Dockerfile.web -t "$web_repo:$version" .
docker push "$api_repo:$version"
docker push "$web_repo:$version"

printf 'Set these in Coolify:\nFGAS_API_IMAGE=%s\nFGAS_WEB_IMAGE=%s\n' \
    "$api_repo:$version" "$web_repo:$version"
