#!/bin/sh
set -eu

mode=${1:---dry-run}
case "$mode" in
  --dry-run|--apply) ;;
  *) echo "Usage: $0 [--dry-run|--apply]" >&2; exit 2 ;;
esac

dir=docs/plan/handoffs
if [ ! -d "$dir" ]; then
  echo "missing handoff directory: $dir" >&2
  exit 1
fi

stray=$(find "$dir" -mindepth 1 -maxdepth 1 -type f ! -name README.md ! -name .gitkeep -print)
if [ -n "$stray" ]; then
  echo "unexpected files directly under $dir; review manually:" >&2
  echo "$stray" >&2
  exit 1
fi

handoffs=$(find "$dir" -mindepth 1 -maxdepth 1 -type d -print)
if [ -z "$handoffs" ]; then
  echo "no handoff directories found"
  exit 0
fi

if [ "$mode" = "--dry-run" ]; then
  echo "handoff directories that would be deleted:"
  echo "$handoffs"
  exit 0
fi

echo "$handoffs" | while IFS= read -r path; do
  [ -n "$path" ] || continue
  rm -rf -- "$path"
done
echo "handoff directories deleted"
