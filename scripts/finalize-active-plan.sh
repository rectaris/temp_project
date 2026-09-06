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
require_task_worktree "finalizing this plan"

group_state=
if [ "${1:-}" = "--group-state" ]; then
  [ "$#" -ge 2 ] || { echo "--group-state requires a path" >&2; exit 2; }
  group_state=$2
  shift 2
fi
[ "$#" -eq 1 ] || { echo "Usage: $0 [--group-state PATH] docs/plan/active/NNN-slug.md" >&2; exit 2; }
src=$1
case "$src" in docs/plan/active/[0-9][0-9][0-9]-*.md) ;; *) echo "expected active plan path" >&2; exit 2 ;; esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }
# An enrolled parallel execution group member is finalized through the grouped
# adapter, never through this legacy serial entrypoint.
[ -f scripts/parallel-plan-state.py ] || {
  echo "missing parallel plan group authority: scripts/parallel-plan-state.py" >&2
  exit 1
}
if [ -n "$group_state" ]; then
  python3 scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation finalization --group-state "$group_state" >/dev/null || exit 1
else
  python3 scripts/parallel-plan-state.py check-enrollment \
    --plan "$src" --operation finalization >/dev/null || exit 1
fi
status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
[ "$status" = "ready_to_archive" ] || { echo "cannot finalize $src: status is $status, expected ready_to_archive" >&2; exit 1; }
grep -q '^checked_summary_ja: .\+' "$src" || { echo "cannot finalize $src: missing non-empty checked_summary_ja" >&2; exit 1; }
awk '/^## Validation Notes$/{in_notes=1; next} /^## /{in_notes=0} in_notes && NF {found=1} END{exit(found ? 0 : 1)}' "$src" || { echo "cannot finalize $src: Validation Notes are empty" >&2; exit 1; }
# Local semantic records are advisory and remain parent-owned.
if [ -f scripts/referent-contract.py ]; then
  python3 scripts/referent-contract.py pending --target "$src" >&2 || :
fi

base=$(basename "$src"); id=${base%%-*}
# The complete active index is parsed before the first repository mutation, so
# a malformed document stops finalization with every byte preserved.
python3 - "$id" "$src" <<'PY'
import re
import sys
from pathlib import Path

plan_id, source = sys.argv[1:]


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


try:
    rows = parse_active_index(read_active_index(Path("docs/plan/plan.md")))
except ActiveIndexError as exc:
    raise SystemExit(f"cannot finalize {source}: {exc}")
matches = [row for row in rows if row[0] == plan_id]
if len(matches) != 1:
    raise SystemExit(f"cannot finalize {source}: expected exactly one active-plan index entry")
if matches[0][1] != source:
    raise SystemExit(f"cannot finalize {source}: active index points to {matches[0][1]}")
if matches[0][2] != "ready_to_archive":
    raise SystemExit(f"cannot finalize {source}: active index status is {matches[0][2]}")
PY
year=$(date +%Y); month=$(date +%m); day=$(date +%d)
case "$day" in 0[1-9]|1[0-5]) half=01-15 ;; *) half=16-31 ;; esac
dst_dir="docs/plan/checked/$year/$month/$half"; dst="$dst_dir/$base"
[ ! -e "$dst" ] || { echo "archive already exists: $dst" >&2; exit 1; }
if awk -F"	" -v id="$id" -v dst="$dst" '$1 == id || $2 == dst {found=1} END{exit(found ? 0 : 1)}' docs/plan/checked.md; then
  echo "cannot finalize $src: checked index conflicts with plan id or archive path" >&2
  exit 1
fi
mkdir -p "$dst_dir"
python3 - "$src" "$dst" <<'PY'
from pathlib import Path
import os
import re
import sys

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
content, count = re.subn(
    r"^status: .*",
    "status: checked",
    source.read_text(encoding="utf-8"),
    count=1,
    flags=re.MULTILINE,
)
if count != 1:
    raise SystemExit("plan must contain a status field")
try:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
except FileExistsError as exc:
    raise SystemExit(f"archive already exists: {destination}") from exc
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
except BaseException:
    destination.unlink(missing_ok=True)
    raise
PY
python3 - "$src" "$dst" <<'PY'
from pathlib import Path
import os
import sys
import tempfile

source, destination = sys.argv[1], sys.argv[2]
new_entry = f"- {destination}"


def rebind(text: str) -> str | None:
    lines = text.splitlines(keepends=True)
    field = None
    changed = False
    for index, raw in enumerate(lines):
        line = raw.rstrip()
        if line.startswith("## "):
            break
        if ":" in line and not line.startswith(" "):
            field = line.split(":", 1)[0].strip()
            continue
        stripped = raw.strip()
        if field != "context_files" or not stripped.startswith("- "):
            continue
        if stripped[2:].strip() != source:
            continue
        indent = raw[: len(raw) - len(raw.lstrip())]
        ending = raw[len(raw.rstrip("\r\n")):]
        lines[index] = f"{indent}{new_entry}{ending}"
        changed = True
    return "".join(lines) if changed else None


def live_plans() -> list[Path]:
    # Finalization already parsed the whole active index before its first
    # mutation, so these rows come from a validated document.
    plans = []
    index = Path("docs/plan/plan.md")
    if index.is_file():
        for row in index.read_text(encoding="utf-8").splitlines():
            columns = row.split("\t")
            if len(columns) == 3 and columns[1].startswith("docs/plan/active/"):
                plans.append(Path(columns[1]))
    backlog = Path("docs/plan/backlog")
    if backlog.is_dir():
        plans.extend(sorted(backlog.glob("**/[0-9][0-9][0-9]-*.md")))
    return plans


rewritten: list[tuple[Path, str]] = []
try:
    for plan in live_plans():
        if str(plan) == source or not plan.is_file():
            continue
        original = plan.read_text(encoding="utf-8")
        updated = rebind(original)
        if updated is None:
            continue
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{plan.name}.", suffix=".tmp", dir=plan.parent
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(updated)
        os.replace(temporary, plan)
        rewritten.append((plan, original))
except BaseException:
    for plan, original in rewritten:
        plan.write_text(original, encoding="utf-8")
    Path(destination).unlink(missing_ok=True)
    raise
PY
rm "$src"
python3 - <<'PY' "$id" "$dst"
import re
import sys
from pathlib import Path


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


plan = Path("docs/plan/plan.md")
kept = [row for row in parse_active_index(read_active_index(plan)) if row[0] != sys.argv[1]]
plan.write_text(render_active_index(kept), encoding="utf-8")
checked = Path("docs/plan/checked.md")
with checked.open("a", encoding="utf-8") as handle:
    handle.write(f"{sys.argv[1]}\t{sys.argv[2]}\n")
PY
echo "$dst"
