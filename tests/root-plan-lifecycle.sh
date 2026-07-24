#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-root-plan-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

mkdir -p "$tmp/scripts" "$tmp/docs/plan/active" "$tmp/docs/plan/checked"
cp "$root/scripts/complete-plan.sh" "$root/scripts/finalize-active-plan.sh" "$tmp/scripts/"

cat >"$tmp/docs/plan/active/001-sample.md" <<'EOF'
# Sample root plan

status: in_progress
checked_summary_ja: ルート計画を完了する。

## Tasks

-  [ ] unfinished

## Validation Notes

1. Pending validation.

## Example

status: preserve-in-body
EOF
cat >"$tmp/docs/plan/plan.md" <<'EOF'
# Active Plan

id	path	status
001	docs/plan/active/001-sample.md	in_progress
EOF
cat >"$tmp/docs/plan/checked.md" <<'EOF'
# Checked Plan Index

id	path
EOF

cp "$tmp/docs/plan/active/001-sample.md" "$tmp/docs/plan/active/002-deferred.md"
sed -i 's/^status: in_progress$/status: deferred/' "$tmp/docs/plan/active/002-deferred.md"
printf '002\tdocs/plan/active/002-deferred.md\tdeferred\n' >>"$tmp/docs/plan/plan.md"
if (cd "$tmp" && scripts/complete-plan.sh docs/plan/active/002-deferred.md >/dev/null 2>&1); then
  echo "root complete-plan archived deferred work" >&2
  exit 1
fi
grep -q '^status: deferred$' "$tmp/docs/plan/active/002-deferred.md"
sed -i '/^002\t/d' "$tmp/docs/plan/plan.md"
rm "$tmp/docs/plan/active/002-deferred.md"

if (cd "$tmp" && scripts/complete-plan.sh docs/plan/active/001-sample.md >/dev/null 2>&1); then
  echo "root complete-plan accepted unfinished tasks and pending evidence" >&2
  exit 1
fi
sed -i 's/^-  \[ \] unfinished$/- [x] finished/; s/^1\. Pending validation\.$/- root lifecycle validation passed./' "$tmp/docs/plan/active/001-sample.md"
(cd "$tmp" && scripts/complete-plan.sh docs/plan/active/001-sample.md >/dev/null)
grep -q '^status: ready_to_archive$' "$tmp/docs/plan/active/001-sample.md"
grep -q '^001	docs/plan/active/001-sample.md	ready_to_archive$' "$tmp/docs/plan/plan.md"

out_one="$tmp/finalize-one.out"
out_two="$tmp/finalize-two.out"
(cd "$tmp" && scripts/finalize-active-plan.sh docs/plan/active/001-sample.md >"$out_one" 2>/dev/null) &
pid_one=$!
(cd "$tmp" && scripts/finalize-active-plan.sh docs/plan/active/001-sample.md >"$out_two" 2>/dev/null) &
pid_two=$!
successes=0
if wait "$pid_one"; then successes=$((successes + 1)); fi
if wait "$pid_two"; then successes=$((successes + 1)); fi
[ "$successes" -eq 1 ] || { echo "root finalizer concurrency expected one successful writer" >&2; exit 1; }
archive=$(sed -n '/^docs\/plan\/checked\//p' "$out_one" "$out_two")
[ -n "$archive" ] || { echo "root finalizer did not report an archive path" >&2; exit 1; }
grep -q '^status: checked$' "$tmp/$archive"
grep -q '^status: preserve-in-body$' "$tmp/$archive"
grep -q "^001	$archive$" "$tmp/docs/plan/checked.md"
if grep -q '^001	' "$tmp/docs/plan/plan.md"; then
  echo "root finalizer left an active index row" >&2
  exit 1
fi

echo "root plan lifecycle test passed"
