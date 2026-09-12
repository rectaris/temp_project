#!/bin/sh
set -eu

plans_only=0
if [ "${1:-}" = "--plans-only" ]; then
  plans_only=1
  shift
fi
if [ "$#" -ne 0 ]; then
  echo "Usage: $0 [--plans-only]" >&2
  exit 2
fi

blocked=0
if [ -f docs/plan/plan.md ]; then
  python3 - <<'PY' || exit 1
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
ACTIVE_INDEX_NOT_ADOPTED = (
    "docs/plan/plan.md does not open with the active plan index title, so it has not "
    "adopted the index format. This is not a first-line defect: the whole document must "
    'be the title "# Active Plan", one blank line, and then either the single line '
    '"No active development items." or the tab header "id\\tpath\\tstatus" followed by '
    "one tab-separated row per active plan. Nothing else may remain. Adopting the format "
    "therefore discards whatever this document holds now, so when that content is owned "
    "by the project rather than the template, confirm the change with its owner instead "
    "of rewriting the document to satisfy this check."
)


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

    Whether the document opens with the title is decided before the
    document-wide newline rules, because a document that never adopted this
    format must be named as such rather than reported for a stray line ending
    it was never expected to carry.
    """

    if text.split("\n", 1)[0].rstrip("\r") != ACTIVE_INDEX_TITLE:
        raise ActiveIndexError(ACTIVE_INDEX_NOT_ADOPTED)
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
    parse_active_index(read_active_index(Path("docs/plan/plan.md")))
except ActiveIndexError as exc:
    if str(exc) == ACTIVE_INDEX_NOT_ADOPTED:
        print(f"unadopted active plan index blocks completion: {exc}", file=sys.stderr)
    else:
        print(f"malformed active plan index blocks completion: {exc}", file=sys.stderr)
        print("Next: rewrite docs/plan/plan.md as the empty marker or the tab index.", file=sys.stderr)
    sys.exit(1)
PY
  while IFS="	" read -r id plan status; do
    case "$id" in
      ''|id) continue ;;
    esac
    [ -f "$plan" ] || continue
    lifecycle=$(awk -F': ' '$1 == "status" { print $2; exit }' "$plan")
    if [ "$lifecycle" = "ready_to_archive" ]; then
      blocked=1
      echo "ready-to-archive plan blocks completion: $plan (status: $lifecycle)" >&2
      if ! grep -q '^checked_summary_ja: .\+' "$plan"; then
        echo "Missing evidence: checked_summary_ja" >&2
      fi
      if ! awk '/^## Validation Notes$/{in_notes=1; next} /^## /{in_notes=0} in_notes && NF {found=1} END{exit(found ? 0 : 1)}' "$plan"; then
        echo "Missing evidence: non-empty Validation Notes" >&2
      fi
      echo "Next: .project-agent-workflow/scripts/finalize-active-plan.sh $plan" >&2
      continue
    fi
    [ "$status" = "in_progress" ] || continue
    [ "$lifecycle" = "in_progress" ] || continue
    if sh .project-agent-workflow/scripts/complete-plan.sh --check-completion-evidence "$plan" </dev/null; then
      blocked=1
      echo "completed plan is not marked ready: $plan (status: $lifecycle)" >&2
      echo "Next: .project-agent-workflow/scripts/complete-plan.sh $plan" >&2
    fi
  done < docs/plan/plan.md
fi

if [ "$blocked" -ne 0 ]; then
  exit 1
fi

if [ "$plans_only" -eq 0 ] && [ -n "$(git status --short)" ]; then
  echo "dirty worktree blocks completion report" >&2
  git status --short >&2
  echo "Next: inspect git status --short, then commit intended changes or remove unrelated generated files." >&2
  exit 1
fi

echo "agent completion gate passed"
