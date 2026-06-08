#!/bin/sh
set -eu

echo "== Git =="
git status --short || true

echo
echo "== Active Plan =="
if [ -f docs/plan/plan.md ]; then
  sed -n '1,120p' docs/plan/plan.md
else
  echo "docs/plan/plan.md not found"
fi

