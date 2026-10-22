#!/usr/bin/env bash
set -euo pipefail
usage() { echo "Usage: $0 BUNDLE USER@HOST /absolute/deploy/path [--init-db]" >&2; exit 2; }
[[ $# == 3 || ( $# == 4 && $4 == --init-db ) ]] || usage
bundle=$1
target=$2
deploy_root=${3%/}
[[ -f $bundle && $target =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.@:-]*$ && $deploy_root =~ ^/[a-zA-Z0-9_/-][a-zA-Z0-9_./-]*$ && $deploy_root != *..* ]] || usage
archive=$(basename "$bundle")
[[ $archive =~ ^fgas-[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}\.tar\.gz$ ]] || usage
release=${archive%.tar.gz}
# Paths are restricted above so these remote shell arguments cannot contain shell syntax.
ssh "$target" "mkdir -p '$deploy_root/releases'"
scp "$bundle" "$target:$deploy_root/releases/$archive"
ssh "$target" "set -eu; cd '$deploy_root/releases'; tar -xzf '$archive'; bash '$release/apply-release.sh' ${4:-}"
