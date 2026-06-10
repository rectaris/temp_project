#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-update-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

copier_available() {
  command -v copier >/dev/null 2>&1 || { command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; }
}

run_copier() {
  if command -v copier >/dev/null 2>&1; then
    copier "$@"
  else
    (cd "$root" && UV_CACHE_DIR="$root/.uv-cache" uv run copier "$@")
  fi
}

if ! copier_available; then
  if [ "${REQUIRE_COPIER:-0}" = "1" ]; then
    echo "copier CLI not found" >&2
    exit 127
  fi
  echo "copier CLI not found; skipped copier update test"
  echo "copier update test passed"
  exit 0
fi

out="$tmp/generated"
base_ref=${COPIER_UPDATE_BASE_REF:-v0.2.0}
run_copier copy -f --vcs-ref "$base_ref" --data-file "$root/tests/fixtures/typescript.answers.yml" "$root" "$out" >/dev/null

git -C "$out" init -b main >/dev/null
git -C "$out" config user.email "ci@example.invalid"
git -C "$out" config user.name "CI"
git -C "$out" add -A
git -C "$out" commit -m "Initial generated workflow" >/dev/null

cat >"$out/docs/agent/SPEC_PRODUCT.md" <<'EOF'
# Product Notes

Local project-owned agent notes.
EOF
git -C "$out" add docs/agent/SPEC_PRODUCT.md
git -C "$out" commit -m "Add local project notes" >/dev/null

run_copier update -f --vcs-ref HEAD "$out" >/dev/null

test -f "$out/.copier-answers.yml"
test -f "$out/AGENTS.md"
test -f "$out/docs/agent/spec-index.yaml"
test -f "$out/docs/agent/SPEC_FILE_MANAGEMENT.md"
test -f "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test -f "$out/docs/plan/README.md"
test -f "$out/docs/plan/backlog/README.md"
test -f "$out/docs/plan/handoffs/README.md"
test -f "$out/docs/plan/sub-agents/custom-agents.md"
test -f "$out/docs/agent/SPEC_PRODUCT.md"
test -f "$out/scripts/workflow-status.sh"
test -f "$out/scripts/create-plan.sh"
test -f "$out/scripts/select-task-context.sh"
test -f "$out/scripts/clean-handoffs.sh"
test -f "$out/scripts/lint-plan-docs.sh"
test -f "$out/scripts/format-plan-docs.sh"
test -f "$out/scripts/validate-changes.py"
test -f "$out/scripts/security-static-check.py"
grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
grep -q 'Integration Checklist' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'To add Linear later' "$out/docs/agent/SPEC_EXTERNAL_SERVICES.md"

if find "$out" -name '*.rej' -print -quit | grep -q .; then
  echo "copier update produced rejection files" >&2
  exit 1
fi

git -C "$out" diff --check
echo "copier update test passed"
