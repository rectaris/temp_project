#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 [--force] <target-repo>" >&2
}

force=0
case "${1:-}" in
  --force)
    force=1
    shift
    ;;
esac

if [ "$#" -ne 1 ]; then
  usage
  exit 2
fi

target=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
package_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

if [ ! -f "$package_root/copier.yml" ] || [ ! -d "$package_root/template" ]; then
  echo "Copier template not found under: $package_root" >&2
  exit 1
fi

if ! command -v copier >/dev/null 2>&1; then
  echo "copier CLI is required. Install with: uv tool install copier" >&2
  exit 127
fi

if [ "$force" -eq 1 ]; then
  copier copy -f "$package_root" "$target"
else
  copier copy "$package_root" "$target"
fi

target_root=$(CDPATH= cd -- "$target" && pwd)
echo "Project agent workflow rendered to $target_root"
echo "Run from target repo: git status --short"
