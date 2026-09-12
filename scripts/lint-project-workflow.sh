#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

# Local Git hook activation is a repository-shipped fast-feedback layer, not the
# enforcement boundary. This detector reports an inactive selection and never
# writes Git configuration. It stays root-only and is not shipped to generated
# projects.
check_hook_activation() {
  target=$1
  [ -f "$target/.githooks/pre-commit" ] || return 0
  [ -z "${CI:-}" ] || return 0
  git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  selected=$(git -C "$target" config --get core.hooksPath || true)
  [ "$selected" != ".githooks" ] || return 0
  echo "core.hooksPath does not select the shipped Git hooks: ${selected:-<unset>}" >&2
  echo "Next: git config core.hooksPath .githooks" >&2
  return 1
}

if [ "${1:-}" = "--check-hook-activation" ]; then
  shift
  [ "$#" -le 1 ] || { echo "Usage: $0 [--check-hook-activation [DIRECTORY]]" >&2; exit 2; }
  if [ "$#" -eq 1 ]; then
    root=$(CDPATH= cd -- "$1" && pwd)
  fi
  check_hook_activation "$root"
  exit 0
fi

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
python3 "$root/.codex/skills/verify-copier-update/scripts/check-triage-coverage.py"
python3 "$root/template/.project-agent-workflow/skills/verify-copier-update/scripts/check-triage-coverage.py"
(cd "$root" && python3 scripts/restructure-plan.py --verify)
python3 "$root/scripts/check-external-service-policy.py" check
python3 "$root/scripts/check-root-agent-policy.py" --self-test
python3 "$root/scripts/import-codex-transcript.py" --self-test
python3 "$root/scripts/check-agent-log-manifest.py" --self-test
python3 "$root/tests/test-hooks.py"
python3 "$root/tests/test-human-report.py"
python3 "$root/tests/test-agent-model-profiles.py"
python3 "$root/tests/test-copier-migration.py"
python3 "$root/tests/test-copier-adoption.py"
python3 "$root/tests/test-referent-contract.py"
python3 "$root/tests/test-harness-comparison.py"
python3 "$root/tests/test-harness-comparison.py" --generated
python3 "$root/tests/test-harness-profiles.py"
python3 "$root/tests/test-template-feedback.py"
python3 "$root/tests/test-template-feedback-collection.py"
python3 "$root/tests/test-development-direction.py"
REQUIRE_COPIER=1 python3 "$root/tests/test-template-feedback-pipeline.py"
REQUIRE_COPIER=1 "$root/tests/smoke.sh" --harness-profile-preservation
python3 "$root/tests/test-validation-tools.py"
python3 "$root/tests/test-verify-copier-update.py"
"$root/tests/root-plan-lifecycle.sh"

check_hook_activation "$root"

echo "workflow package lint passed"
