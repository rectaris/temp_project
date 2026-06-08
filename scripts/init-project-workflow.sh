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
template_root="$package_root/assets/templates"

if [ ! -d "$template_root" ]; then
  echo "Template directory not found: $template_root" >&2
  exit 1
fi

mkdir -p "$target"
target_root=$(CDPATH= cd -- "$target" && pwd)

installed=0
skipped=0

find "$template_root" -type f | sort | while IFS= read -r src; do
  rel=${src#"$template_root"/}
  dest="$target_root/$rel"
  mkdir -p "$(dirname -- "$dest")"
  if [ -e "$dest" ] && [ "$force" -ne 1 ]; then
    echo "skip existing: $rel"
    skipped=$((skipped + 1))
    continue
  fi
  cp "$src" "$dest"
  echo "install: $rel"
  installed=$((installed + 1))
done

echo "Project agent workflow templates applied to $target_root"
echo "Run from target repo: git status --short"

