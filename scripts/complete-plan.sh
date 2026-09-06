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
require_task_worktree "completing this plan"

# 0: completion evidence is present, 1: unchecked tasks remain,
# 2: Validation Notes are empty or pending.
completion_evidence() {
  if grep -Eq '^[[:space:]]*[-*+][[:space:]]+\[ \]' "$1"; then
    return 1
  fi
  awk '
    /^## Validation Notes$/ { in_notes=1; next }
    /^## / { in_notes=0 }
    in_notes {
      line=$0
      sub(/^[[:space:]]*([-*+]|[0-9]+[.)])[[:space:]]+/, "", line)
      sub(/^[[:space:]]+/, "", line)
      if (line != "" && tolower(line) !~ /^pending([ .:]|$)/) found=1
    }
    END { exit(found ? 0 : 1) }
  ' "$1" || return 2
  return 0
}

check_only=0
group_state=
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --check-completion-evidence) check_only=1; shift ;;
    --group-state) [ "$#" -ge 2 ] || { echo "--group-state requires a path" >&2; exit 2; }; group_state=$2; shift 2 ;;
    *) break ;;
  esac
done

[ "$#" -eq 1 ] || { echo "Usage: $0 [--check-completion-evidence] [--group-state PATH] docs/plan/active/NNN-slug.md" >&2; exit 2; }
src=$1
case "$src" in docs/plan/active/[0-9][0-9][0-9]-*.md) ;; *) echo "expected active plan path" >&2; exit 2 ;; esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }

if [ "$check_only" -eq 1 ]; then
  completion_evidence "$src" || exit 1
  exit 0
fi

# An enrolled parallel execution group member is completed through the grouped
# adapter, never through this legacy serial entrypoint.
[ -f scripts/parallel-plan-state.py ] || {
  echo "missing parallel plan group authority: scripts/parallel-plan-state.py" >&2
  exit 1
}
if [ -n "$group_state" ]; then
  python3 scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation completion --group-state "$group_state" >/dev/null || exit 1
else
  python3 scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation completion >/dev/null || exit 1
fi

status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
case "$status" in
  in_progress) ;;
  deferred)
    echo "cannot mark deferred plan ready; return it to in_progress after its deferral condition is resolved: $src" >&2
    exit 1
    ;;
  replan_required)
    echo "cannot complete a plan that requires restructuring: $src" >&2
    exit 1
    ;;
  *) echo "cannot mark plan ready from status: $status" >&2; exit 1 ;;
esac

evidence=0
completion_evidence "$src" || evidence=$?
case "$evidence" in
  0) ;;
  1) echo "cannot mark plan ready: unchecked tasks remain in $src" >&2; exit 1 ;;
  *) echo "cannot mark plan ready: Validation Notes are empty or pending in $src" >&2; exit 1 ;;
esac

# Local semantic records are advisory and remain parent-owned.
if [ -f scripts/referent-contract.py ]; then
  python3 scripts/referent-contract.py pending --target "$src" >&2 || :
fi

base=$(basename "$src"); id=${base%%-*}
python3 - "$id" "$src" "$status" <<'PY'
from pathlib import Path
import fcntl
import os
import re
import sys
import tempfile

plan_id, source, status = sys.argv[1:]
index = Path("docs/plan/plan.md")
target = Path(source)


# --- active plan index grammar: keep byte-identical across enforcing commands ---
ACTIVE_INDEX_TITLE = "# Active Plan"
ACTIVE_INDEX_EMPTY_BODY = "No active development items."
ACTIVE_INDEX_HEADER = "id\tpath\tstatus"
ACTIVE_INDEX_STATUSES = ("in_progress", "ready_to_archive", "deferred", "replan_required")
ACTIVE_INDEX_ID_RE = re.compile(r"[0-9]{3}")
ACTIVE_INDEX_ROW_PATH_RE = re.compile(r"docs/plan/active/([0-9]{3})-[a-z0-9][a-z0-9-]*\.md")


class ActiveIndexError(ValueError):
    """Raised when the active plan index is not one accepted representation."""


def read_active_index(path: Path) -> str:
    """Read one active plan index without newline translation."""

    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ActiveIndexError(f"active plan index is not UTF-8 text: {exc}") from exc


def parse_active_index(text: str) -> list[tuple[str, str, str]]:
    """Return the rows of one exact accepted active plan index document.

    The empty representation is the title, one blank line, and the empty
    marker. The populated representation is the title, one blank line, the
    actual-tab header, and one or more actual-tab rows. Every other nonempty
    document is rejected whole instead of being partially parsed.
    """

    if "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        raise ActiveIndexError("active plan index must end with exactly one trailing newline")
    lines = text.split("\n")[:-1]
    if lines[:2] != [ACTIVE_INDEX_TITLE, ""]:
        raise ActiveIndexError("active plan index must start with its title and one blank line")
    body = lines[2:]
    if not body:
        raise ActiveIndexError("active plan index must hold the empty marker or the header")
    if body[0] == ACTIVE_INDEX_EMPTY_BODY:
        if len(body) > 1:
            raise ActiveIndexError("empty active plan index must hold no other content")
        return []
    if body[0] != ACTIVE_INDEX_HEADER:
        raise ActiveIndexError(f"active plan index needs the exact tab header: {body[0]!r}")
    if len(body) == 1:
        raise ActiveIndexError("active plan index header must be followed by at least one row")
    rows: list[tuple[str, str, str]] = []
    for line in body[1:]:
        columns = line.split("\t")
        if len(columns) != 3:
            raise ActiveIndexError(f"active plan index row needs three tab columns: {line!r}")
        plan_id, path, status = columns
        if ACTIVE_INDEX_ID_RE.fullmatch(plan_id) is None:
            raise ActiveIndexError(f"active plan index row needs a three-digit id: {line!r}")
        match = ACTIVE_INDEX_ROW_PATH_RE.fullmatch(path)
        if match is None:
            raise ActiveIndexError(f"active plan index row needs a normalized path: {line!r}")
        if match.group(1) != plan_id:
            raise ActiveIndexError(f"active plan index row id does not match its file: {line!r}")
        if status not in ACTIVE_INDEX_STATUSES:
            raise ActiveIndexError(f"active plan index row status is not allowed: {line!r}")
        if any(plan_id == row[0] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index id: {plan_id}")
        if any(path == row[1] for row in rows):
            raise ActiveIndexError(f"duplicate active plan index path: {path}")
        rows.append((plan_id, path, status))
    return rows


def render_active_index(rows: list[tuple[str, str, str]]) -> str:
    """Serialize fully parsed rows as the single canonical representation."""

    if rows:
        body = "\n".join("\t".join(row) for row in rows)
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_HEADER}\n{body}\n"
    else:
        text = f"{ACTIVE_INDEX_TITLE}\n\n{ACTIVE_INDEX_EMPTY_BODY}\n"
    if parse_active_index(text) != rows:
        raise ActiveIndexError("canonical active plan index serialization failed")
    return text
# --- end active plan index grammar ---


def atomic_write(path: Path, content: str) -> None:
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


lock_dir = Path(".agent-artifacts")
lock_dir.mkdir(parents=True, exist_ok=True)
with (lock_dir / "plan-lifecycle.lock").open("a", encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    original_plan = target.read_text(encoding="utf-8")
    # The complete index is parsed before the first mutation, so a malformed
    # document leaves every plan and index byte untouched.
    try:
        rows = parse_active_index(read_active_index(index))
    except ActiveIndexError as exc:
        raise SystemExit(str(exc))
    if [row for row in rows if row[0] == plan_id] != [(plan_id, source, status)]:
        raise SystemExit(f"active index must contain exactly one row for {plan_id}")
    updated_index = render_active_index(
        [
            (row[0], row[1], "ready_to_archive") if row[0] == plan_id else row
            for row in rows
        ]
    )
    updated_plan, count = re.subn(
        r"^status: .*", "status: ready_to_archive", original_plan, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise SystemExit("plan must contain a status field")
    atomic_write(target, updated_plan)
    try:
        atomic_write(index, updated_index)
    except BaseException:
        atomic_write(target, original_plan)
        raise
PY
echo "$src"
