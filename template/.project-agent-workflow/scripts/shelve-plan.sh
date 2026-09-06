#!/bin/sh
set -eu

# Every repository-changing lifecycle command runs in its own task worktree.
# The guard reports its own enforcement scope, so a repository that cannot
# carry a binding keeps its previous behavior instead of refusing every run.
require_task_worktree() {
  _top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  for _candidate in \
    .project-agent-workflow/scripts/worktree_guard.py \
    scripts/project_workflow/worktree_guard.py; do
    if [ -f "$_top/$_candidate" ]; then
      if ! _refusal=$(python3 "$_top/$_candidate" require --action "$1" 2>&1); then
        echo "$_refusal" >&2
        exit 1
      fi
      return 0
    fi
  done
}
require_task_worktree "shelving this plan"

usage() {
  echo "Usage: $0 docs/plan/backlog/NNN-slug.md 'why this is not being implemented'" >&2
  echo "       $0 --restore docs/plan/shelved/NNN-slug.md" >&2
  exit 2
}

case "${1:-}" in
  --restore)
    [ "$#" -eq 2 ] || usage
    src=$2
    case "$src" in docs/plan/shelved/[0-9][0-9][0-9]-*.md) ;; *) usage ;; esac
    mode=restore
    reason=
    ;;
  *)
    [ "$#" -eq 2 ] || usage
    src=$1
    reason=$2
    case "$src" in docs/plan/backlog/[0-9][0-9][0-9]-*.md) ;; *) usage ;; esac
    mode=shelve
    ;;
esac

[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }
[ -L "$src" ] && { echo "refusing a symlinked plan: $src" >&2; exit 1; }

status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
if [ "$mode" = shelve ]; then
  case "$status" in
    backlog) ;;
    *) echo "only a backlog plan can be shelved, not status: $status" >&2; exit 1 ;;
  esac
  case "$reason" in
    *[!\ ]*) ;;
    *) echo "a shelved plan requires a written reason" >&2; exit 1 ;;
  esac
  case "$reason" in
    *'\'*) echo "a shelved reason may not contain a backslash" >&2; exit 1 ;;
  esac
  if [ "$reason" != "$(printf '%s' "$reason" | tr -d '\n\r\t')" ]; then
    echo "a shelved reason must be a single line of text" >&2
    exit 1
  fi
else
  case "$status" in
    shelved) ;;
    *) echo "only a shelved plan can be restored, not status: $status" >&2; exit 1 ;;
  esac
fi

python3 - "$mode" "$src" "$reason" <<'PY'
from pathlib import Path
import fcntl
import os
import re
import sys
import tempfile
from datetime import date

mode, source, reason = sys.argv[1:]
target = Path(source)
destination_dir = Path("docs/plan/shelved" if mode == "shelve" else "docs/plan/backlog")
destination = destination_dir / target.name


def atomic_write(path: Path, content: str) -> None:
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


lock_dir = Path(".agent-artifacts")
lock_dir.mkdir(parents=True, exist_ok=True)
destination_dir.mkdir(parents=True, exist_ok=True)
with (lock_dir / "plan-lifecycle.lock").open("a", encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"destination already exists: {destination}")
    original = target.read_text(encoding="utf-8")
    if mode == "shelve":
        if not reason.strip() or reason != reason.strip("\n\r\t "):
            raise SystemExit("a shelved plan requires a written single-line reason")
        replacement = (
            "status: shelved\n"
            f"shelved_reason: {reason}\n"
            f"shelved_at: {date.today().isoformat()}"
        )
        if "\n" in reason or "\r" in reason:
            raise SystemExit("a shelved reason must be a single line of text")
        updated, count = re.subn(
            r"^status: .*",
            lambda _match: replacement,
            original,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        updated, count = re.subn(
            r"^status: .*\nshelved_reason: .*\nshelved_at: .*",
            "status: backlog",
            original,
            count=1,
            flags=re.MULTILINE,
        )
    if count != 1:
        raise SystemExit("plan must carry the fields this move rewrites")
    atomic_write(destination, updated)
    try:
        target.unlink()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
PY

base=$(basename "$src")
if [ "$mode" = shelve ]; then
  echo "docs/plan/shelved/$base"
else
  echo "docs/plan/backlog/$base"
fi
