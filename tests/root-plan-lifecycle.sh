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

cp "$tmp/docs/plan/active/001-sample.md" "$tmp/docs/plan/active/003-replan.md"
sed -i 's/^status: in_progress$/status: replan_required/' "$tmp/docs/plan/active/003-replan.md"
printf '003\tdocs/plan/active/003-replan.md\treplan_required\n' >>"$tmp/docs/plan/plan.md"
if (cd "$tmp" && scripts/complete-plan.sh docs/plan/active/003-replan.md >/dev/null 2>&1); then
  echo "root complete-plan archived replan-required work" >&2
  exit 1
fi
grep -q '^status: replan_required$' "$tmp/docs/plan/active/003-replan.md"
sed -i '/^003\t/d' "$tmp/docs/plan/plan.md"
rm "$tmp/docs/plan/active/003-replan.md"

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

mkdir -p "$tmp/admission"
policy="$root/scripts/check-root-agent-policy.py"

cat >"$tmp/admission/263-legacy.md" <<'EOF'
# Legacy root plan

status: backlog
write_scope:
  - scripts/tool.py
validation:
  - git diff --check
acceptance:
  - Preserve the pre-policy root backlog plan.

## Tasks
EOF
python3 "$policy" --check-plan-admission "$tmp/admission/263-legacy.md" >/dev/null

cp "$tmp/admission/263-legacy.md" "$tmp/admission/264-missing.md"
if python3 "$policy" --check-plan-admission "$tmp/admission/264-missing.md" \
    >/dev/null 2>"$tmp/admission/264-missing.err"; then
  echo "root admission boundary accepted a plan without an admission record" >&2
  exit 1
fi
grep -q 'plan_purpose' "$tmp/admission/264-missing.err"

condition_one='Refuse a boundary plan without bounded feasibility evidence.'
condition_two='Bind every boundary completion condition to one focused witness.'
digest_one=$(printf '%s' "$condition_one" | python3 -c 'import hashlib,sys; print("sha256:" + hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')
digest_two=$(printf '%s' "$condition_two" | python3 -c 'import hashlib,sys; print("sha256:" + hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')

write_admitted_plan() {
  target=$1
  scope=$2
  cat >"$target" <<EOF
# Admitted root plan

status: backlog
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"The root policy command already parses plan manifests."}
completion_conditions:
  - $condition_one
  - $condition_two
completion_witness_map:
  - {"condition_sha256":"$digest_one","witness":"python3 tests/focused.py"}
  - {"condition_sha256":"$digest_two","witness":"python3 tests/focused.py"}
write_scope:
  - $scope
focused_validation:
  - python3 tests/focused.py
validation:
  - git diff --check
acceptance:
  - Preserve the admitted root backlog plan.

## Tasks
EOF
}

write_admitted_plan "$tmp/admission/265-admitted.md" "scripts/tool.py"
python3 "$policy" --check-plan-admission "$tmp/admission/265-admitted.md" >/dev/null

write_admitted_plan "$tmp/admission/266-lifecycle-only.md" "docs/plan/active/266-lifecycle-only.md"
if python3 "$policy" --check-plan-admission "$tmp/admission/266-lifecycle-only.md" \
    >/dev/null 2>"$tmp/admission/266-lifecycle-only.err"; then
  echo "root admission boundary accepted a plan-lifecycle-only write scope" >&2
  exit 1
fi
grep -q 'outside plan-lifecycle records' "$tmp/admission/266-lifecycle-only.err"

sed 's/^  - {"condition_sha256":"'"$digest_two"'".*$//' \
  "$tmp/admission/265-admitted.md" >"$tmp/admission/267-partial.md"
if python3 "$policy" --check-plan-admission "$tmp/admission/267-partial.md" \
    >/dev/null 2>"$tmp/admission/267-partial.err"; then
  echo "root admission boundary accepted partial completion witness coverage" >&2
  exit 1
fi
grep -q 'completion_witness_map' "$tmp/admission/267-partial.err"

python3 "$policy" --check-plan-admission \
  "$root/docs/plan/backlog/251-place-fixture-words-and-alias-sources.md" >/dev/null
grep -q '^status: backlog$' \
  "$root/docs/plan/backlog/251-place-fixture-words-and-alias-sources.md"

echo "root plan lifecycle test passed"
