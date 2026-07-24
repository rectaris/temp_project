#!/bin/sh
set -eu

[ "$#" -eq 1 ] || { echo "Usage: $0 docs/plan/active/NNN-slug.md" >&2; exit 2; }
src=$1
case "$src" in docs/plan/active/[0-9][0-9][0-9]-*.md) ;; *) echo "expected active plan path" >&2; exit 2 ;; esac
[ -f "$src" ] || { echo "missing plan: $src" >&2; exit 1; }

status=$(awk -F': ' '$1 == "status" { print $2; exit }' "$src")
case "$status" in
  in_progress) ;;
  deferred)
    echo "cannot mark deferred plan ready; return it to in_progress after its deferral condition is resolved: $src" >&2
    exit 1
    ;;
  *) echo "cannot mark plan ready from status: $status" >&2; exit 1 ;;
esac

if grep -Eq '^[[:space:]]*[-*+][[:space:]]+\[ \]' "$src"; then
  echo "cannot mark plan ready: unchecked tasks remain in $src" >&2
  exit 1
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
' "$src" || { echo "cannot mark plan ready: Validation Notes are empty or pending in $src" >&2; exit 1; }

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
    original_index = index.read_text(encoding="utf-8")
    expected = f"{plan_id}\t{source}\t{status}"
    lines = original_index.splitlines()
    if lines.count(expected) != 1:
        raise SystemExit(f"active index must contain exactly: {expected}")
    updated_plan, count = re.subn(
        r"^status: .*", "status: ready_to_archive", original_plan, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise SystemExit("plan must contain a status field")
    replacement = f"{plan_id}\t{source}\tready_to_archive"
    updated_index = "\n".join(replacement if line == expected else line for line in lines).rstrip() + "\n"
    atomic_write(target, updated_plan)
    try:
        atomic_write(index, updated_index)
    except BaseException:
        atomic_write(target, original_plan)
        raise
PY
echo "$src"
