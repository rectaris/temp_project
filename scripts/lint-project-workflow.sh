#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
required_list=${TMPDIR:-/tmp}/project-agent-workflow-required-$$
trap 'rm -f "$required_list"' EXIT HUP INT TERM
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

sh -n "$root/scripts/init-project-workflow.sh"
sh -n "$root/scripts/lint-project-workflow.sh"
sh -n "$root/tests/smoke.sh"
sh -n "$root/tests/copier-update.sh"
sh -n "$root/template/scripts/next-plan-id.sh"
sh -n "$root/template/scripts/create-plan.sh"
sh -n "$root/template/scripts/promote-plan.sh"
sh -n "$root/template/scripts/complete-plan.sh"
sh -n "$root/template/scripts/finalize-active-plan.sh"
sh -n "$root/template/scripts/check-agent-completion.sh"
sh -n "$root/template/scripts/lint-plan-docs.sh"
sh -n "$root/template/scripts/format-plan-docs.sh"
sh -n "$root/template/scripts/select-task-context.sh"
sh -n "$root/template/scripts/clean-handoffs.sh"

PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/project-agent-workflow-pycache-$$" \
  python3 -m py_compile \
  "$root/template/.codex/hooks/pre_tool_hardening_gate.py" \
  "$root/template/.codex/hooks/stop_review_gate.py" \
  "$root/scripts/check-copier-template.py" \
  "$root/template/scripts/lint-plan-docs.py" \
  "$root/template/scripts/planlib.py" \
  "$root/template/scripts/format-plan-docs.py" \
  "$root/template/scripts/search-plan-archive.py" \
  "$root/template/scripts/validate-changes.py" \
  "$root/template/scripts/security-static-check.py" \
  "$root/template/scripts/structure-map.py" \
  "$root/tests/test-hooks.py"

python3 "$root/scripts/check-copier-template.py"
python3 "$root/tests/test-hooks.py"

echo "workflow package lint passed"
