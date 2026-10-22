#!/usr/bin/env bash
# Build an offline bundle, or assemble a small bundle for already-published GHCR images.
set -euo pipefail
cd "$(dirname "$0")/.."

usage() { echo "Usage: $0 VERSION [--registry ghcr.io/owner/repository]" >&2; exit 2; }
[[ $# == 1 || ( $# == 3 && $2 == --registry ) ]] || usage
version=$1
[[ $version =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ ]] || usage
prefix=${3:-fgas}
if [[ $# == 3 ]]; then
    [[ $prefix =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]+$ && $prefix != *..* && $prefix != */ ]] || usage
fi
api_image="$prefix-api:$version"
web_image="$prefix-web:$version"
release="fgas-$version"
mkdir -p .releases
output="$PWD/.releases/$release.tar.gz"
[[ ! -e $output ]] || { echo "Already exists: $output. Use a new version or move it aside." >&2; exit 1; }
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
mkdir "$staging/$release"
cp deploy/compose.yaml deploy/env.example deploy/apply-release.sh "$staging/$release/"
printf 'FGAS_API_IMAGE=%s\nFGAS_WEB_IMAGE=%s\nFGAS_DB_IMAGE=postgres:14\n' \
    "$api_image" "$web_image" > "$staging/$release/release.env"

if [[ $# == 1 ]]; then
    docker build --platform linux/amd64 -f deploy/Dockerfile -t "$api_image" .
    docker build --platform linux/amd64 -f deploy/Dockerfile.web -t "$web_image" .
    docker pull --platform linux/amd64 postgres:14
    docker image save -o "$staging/$release/images.tar" "$api_image" "$web_image" postgres:14
fi
tar -czf "$staging/$release.tar.gz" -C "$staging" "$release"
mv "$staging/$release.tar.gz" "$output"
echo "Release bundle: $output"
