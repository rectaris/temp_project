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
repository_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repository_root"

copier update --trust "$@"
python3 .project-agent-workflow/scripts/validate-copier-update.py --destination .
