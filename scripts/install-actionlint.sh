#!/bin/sh
set -eu

version=1.7.12
archive=actionlint_${version}_linux_amd64.tar.gz
expected=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
destination=${1:-"${TMPDIR:-/tmp}/project-agent-workflow-actionlint"}

mkdir -p "$destination"
archive_path="$destination/$archive"
curl -fsSL "https://github.com/rhysd/actionlint/releases/download/v$version/$archive" -o "$archive_path"
printf '%s  %s\n' "$expected" "$archive_path" | sha256sum --check -
tar -xzf "$archive_path" -C "$destination" actionlint
"$destination/actionlint" -version
