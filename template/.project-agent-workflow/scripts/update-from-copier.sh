#!/bin/sh
set -eu

for argument in "$@"; do
  case "$argument" in
    --force|--force=*)
      echo "update-from-copier.sh rejects Copier force flags" >&2
      exit 2
      ;;
    --*) ;;
    -*f*)
      echo "update-from-copier.sh rejects Copier force flags" >&2
      exit 2
      ;;
  esac
done
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rootdir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$rootdir"
exec "$script_dir/run-copier-update.sh" "$@"
python3 .project-agent-workflow/scripts/validate-copier-update.py --destination .
