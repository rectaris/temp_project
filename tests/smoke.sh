#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-smoke-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

mkdir -p "$tmp/repo"
"$root/scripts/init-project-workflow.sh" "$tmp/repo" >/dev/null

test -f "$tmp/repo/AGENTS.md"
test -f "$tmp/repo/docs/agent/spec-index.yaml"
test -f "$tmp/repo/docs/plan/plan.md"
test -f "$tmp/repo/.codex/agents/repo_explorer.toml"
test -f "$tmp/repo/.codex/hooks/pre_tool_hardening_gate.py"

"$root/scripts/init-project-workflow.sh" "$tmp/repo" >"$tmp/second-install.log"
grep -q 'skip existing: AGENTS.md' "$tmp/second-install.log"

echo "smoke test passed"
