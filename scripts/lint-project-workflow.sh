#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

required='
SKILL.md
agents/openai.yaml
references/routing.md
references/planning.md
references/validation.md
references/file-management.md
references/orchestration.md
assets/templates/AGENTS.md
assets/templates/docs/agent/spec-index.yaml
assets/templates/docs/agent/SPEC_VALIDATION.md
assets/templates/docs/agent/SPEC_GIT_WORKFLOW.md
scripts/init-project-workflow.sh
scripts/lint-project-workflow.sh
'

missing=0
for path in $required; do
  if [ ! -f "$root/$path" ]; then
    echo "missing: $path" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  exit 1
fi

grep -q '^name: project-agent-workflow$' "$root/SKILL.md"
grep -q '^description: ' "$root/SKILL.md"
grep -q 'spec-index.yaml' "$root/assets/templates/AGENTS.md"

sh -n "$root/scripts/init-project-workflow.sh"
sh -n "$root/scripts/lint-project-workflow.sh"
sh -n "$root/tests/smoke.sh"

python3 -m py_compile \
  "$root/assets/templates/.codex/hooks/pre_tool_hardening_gate.py" \
  "$root/assets/templates/.codex/hooks/stop_review_gate.py"

echo "workflow package lint passed"

