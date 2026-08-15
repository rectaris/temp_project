#!/bin/sh
set -eu

main() {
  for argument in "$@"; do
    case "$argument" in
      --force|--force=*)
        echo "run-copier-update.sh rejects Copier force flags" >&2
        exit 2
        ;;
      --*) ;;
      -*f*)
        echo "run-copier-update.sh rejects Copier force flags" >&2
        exit 2
        ;;
    esac
  done

  python3 .project-agent-workflow/scripts/validate-copier-update.py \
    --destination . --before-update
  copier update --trust "$@"
  python3 .project-agent-workflow/scripts/validate-copier-update.py --destination .
}

main "$@"; exit
