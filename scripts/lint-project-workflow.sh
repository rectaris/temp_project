#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
required_list=${TMPDIR:-/tmp}/project-agent-workflow-required-$$
python_list=${TMPDIR:-/tmp}/project-agent-workflow-python-$$
trap 'rm -f "$required_list" "$python_list"' EXIT HUP INT TERM
python3 "$root/scripts/check-copier-template.py" --print-source-required >"$required_list"

missing=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  if [ ! -f "$root/$path" ]; then
    echo "missing: $path" >&2
    missing=1
  fi
done <"$required_list"

if [ "$missing" -ne 0 ]; then
  exit 1
fi

grep -q '^name: project-agent-workflow$' "$root/SKILL.md"
grep -q '^description: ' "$root/SKILL.md"
grep -q 'spec-index.yaml' "$root/template/AGENTS.md.jinja"
grep -q '_subdirectory: template' "$root/copier.yml"

python3 "$root/scripts/check-copier-template.py" --print-source-shell | while IFS= read -r path; do
  [ -n "$path" ] || continue
  sh -n "$root/$path"
done

python3 "$root/scripts/check-copier-template.py" --print-source-python >"$python_list"
if [ -s "$python_list" ]; then
  (cd "$root" && PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/project-agent-workflow-pycache-$$" xargs python3 -m py_compile <"$python_list")
fi

python3 "$root/scripts/check-copier-template.py"
python3 "$root/tests/test-hooks.py"

echo "workflow package lint passed"
