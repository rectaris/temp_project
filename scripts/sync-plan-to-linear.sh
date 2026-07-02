#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  scripts/sync-plan-to-linear.sh <docs/plan/<active|backlog|checked>/NNN-slug.md> --dry-run
  scripts/sync-plan-to-linear.sh <docs/plan/<active|backlog>/NNN-slug.md> --update-issue --dry-run
  scripts/sync-plan-to-linear.sh <docs/plan/<active|backlog>/NNN-slug.md> --ensure-issue
  scripts/sync-plan-to-linear.sh <docs/plan/<active|backlog>/NNN-slug.md> --update-issue --apply
  scripts/sync-plan-to-linear.sh <docs/plan/active/NNN-slug.md> --preflight-completion-status
  scripts/sync-plan-to-linear.sh <docs/plan/checked/NNN-slug.md> --update-status --apply
  scripts/sync-plan-to-linear.sh <docs/plan/<active|backlog>/NNN-slug.md> --apply --from-payload <payload.json>

Generic Linear lifecycle gate.

--dry-run renders a local draft without Linear reads or writes.
Read/write-capable modes require docs/agent/external-services.yaml and a
project-specific Linear adapter before they can perform external side effects.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ "$#" -lt 2 ]; then
  usage >&2
  exit 2
fi

plan_path=$1
shift

case "$*" in
  "--dry-run") mode=dry_run ;;
  "--update-issue --dry-run") mode=read_preview ;;
  "--ensure-issue") mode=write ;;
  "--update-issue --apply") mode=write ;;
  "--preflight-completion-status") mode=read_preview ;;
  "--update-status --apply") mode=write ;;
  --apply\ --from-payload\ *) mode=local_apply ;;
  *) usage >&2; exit 2 ;;
esac

[ -f "$plan_path" ] || { echo "plan file not found: $plan_path" >&2; exit 1; }

python3 - "$plan_path" "$mode" "$*" <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import re
import sys


plan_path = Path(sys.argv[1])
mode = sys.argv[2]
raw_mode = sys.argv[3]
policy_path = Path("docs/agent/external-services.yaml")


def read_linear_state() -> str:
    if not policy_path.is_file():
        return "disabled"
    in_linear = False
    for line in policy_path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^  linear_sync:\s*$", line):
            in_linear = True
            continue
        if in_linear and re.match(r"^  [a-zA-Z0-9_]+:\s*$", line):
            return "disabled"
        if in_linear:
            match = re.match(r"^    state:\s*([A-Za-z0-9_-]+)\s*$", line)
            if match:
                return match.group(1)
    return "disabled"


def plan_state(path: Path) -> str:
    parts = path.parts
    if len(parts) >= 4 and parts[0] == "docs" and parts[1] == "plan":
        if parts[2] in {"active", "backlog", "checked"}:
            return parts[2]
    raise SystemExit(f"unsupported plan path: {path}")


def desired_status(state: str) -> str:
    return {"active": "Todo", "backlog": "Backlog", "checked": "Done"}[state]


def title_for(path: Path) -> str:
    match = re.match(r"^([0-9]{3})-(.+)\.md$", path.name)
    if not match:
        raise SystemExit(f"plan filename must be NNN-slug.md: {path}")
    return f"Plan {match.group(1)}: {match.group(2)}"


def summary_for(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return title_for(path)


state = read_linear_state()
source_state = plan_state(plan_path)
payload = {
    "source_plan_path": str(plan_path),
    "source_plan_state": source_state,
    "title": title_for(plan_path),
    "summary": summary_for(plan_path),
    "desired_status_name": desired_status(source_state),
    "linear_policy_state": state,
    "mode": raw_mode,
}

if mode == "dry_run":
    print("# Linear Draft")
    print()
    print(f"- Title: {payload['title']}")
    print(f"- Desired status: {payload['desired_status_name']}")
    print(f"- Policy state: {state}")
    print()
    print("```json")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print("```")
    raise SystemExit(0)

if mode == "local_apply":
    raise SystemExit("--apply --from-payload needs a project-specific adapter before it can change local linkage metadata")

if mode == "read_preview":
    if state not in {"configured_read_only", "configured_write_capable"}:
        raise SystemExit(f"Linear read is not authorized by policy state: {state}")
    raise SystemExit("Linear read adapter is not configured in this generic template")

if mode == "write":
    if state != "configured_write_capable":
        raise SystemExit(f"Linear write is not authorized by policy state: {state}")
    raise SystemExit("Linear write adapter is not configured in this generic template")

raise SystemExit(f"unsupported mode: {mode}")
PY
