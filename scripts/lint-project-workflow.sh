#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

missing=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  if [ ! -f "$root/$path" ]; then
    echo "missing: $path" >&2
    missing=1
  fi
done <<'EOF'
copier.yml
SKILL.md
agents/openai.yaml
references/routing.md
references/planning.md
references/validation.md
references/file-management.md
references/orchestration.md
references/template-development.md
template/AGENTS.md.jinja
template/README.md.jinja
template/.gitignore.jinja
template/[[ _copier_conf.answers_file ]].jinja
template/docs/agent/spec-index.yaml.jinja
template/docs/agent/SPEC_VALIDATION.md.jinja
template/docs/agent/SPEC_GIT_WORKFLOW.md
scripts/init-project-workflow.sh
scripts/lint-project-workflow.sh
scripts/check-copier-template.py
EOF

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

PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/project-agent-workflow-pycache-$$" \
  python3 -m py_compile \
  "$root/template/.codex/hooks/pre_tool_hardening_gate.py" \
  "$root/template/.codex/hooks/stop_review_gate.py" \
  "$root/scripts/check-copier-template.py" \
  "$root/template/scripts/lint-plan-docs.py" \
  "$root/template/scripts/format-plan-docs.py" \
  "$root/template/scripts/search-plan-archive.py" \
  "$root/template/scripts/validate-changes.py" \
  "$root/template/scripts/security-static-check.py" \
  "$root/template/scripts/structure-map.py" \
  "$root/tests/test-hooks.py"

python3 "$root/scripts/check-copier-template.py"
python3 "$root/tests/test-hooks.py"

echo "workflow package lint passed"
