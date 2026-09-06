#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-root-plan-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

mkdir -p "$tmp/scripts" "$tmp/docs/plan/active" "$tmp/docs/plan/checked"
cp "$root/scripts/complete-plan.sh" "$root/scripts/finalize-active-plan.sh" \
  "$root/scripts/parallel-plan-state.py" "$tmp/scripts/"
# The lifecycle entrypoints consult the parallel group authority, which resolves
# enrolment from the repository, so the fixture is a real Git repository.
git -C "$tmp" init -q -b main
git -C "$tmp" config user.email "test@example.invalid"
git -C "$tmp" config user.name "Test"

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

durable=$(find "$root/docs/plan" -name '[0-9][0-9][0-9]-*.md' \
  | sed 's|.*/||' | sort | awk -F- '$1 < 264 {print; exit}')
if [ -z "$durable" ]; then
  echo "root plan lifecycle test found no durable plan predating the admission boundary" >&2
  exit 1
fi
durable_path=$(find "$root/docs/plan" -name "$durable" | head -n 1)
python3 "$policy" --check-plan-admission "$durable_path" \
  >"$tmp/admission/durable.out"
grep -q 'predates the admission boundary' "$tmp/admission/durable.out"
grep -q '^status: [a-z_]*$' "$durable_path"

# An enrolled parallel execution group member is refused by the legacy serial
# completion and finalization entrypoints even when it is otherwise ready.
grouped="$tmp/grouped"
mkdir -p "$grouped/scripts" "$grouped/docs/plan/active" "$grouped/docs/plan/execution-groups"
cp "$root/scripts/complete-plan.sh" "$root/scripts/finalize-active-plan.sh" \
  "$root/scripts/parallel-plan-state.py" "$grouped/scripts/"
git -C "$grouped" init -q -b main
git -C "$grouped" config user.email "test@example.invalid"
git -C "$grouped" config user.name "Test"

write_group_member() {
  cat >"$grouped/docs/plan/active/$1" <<GROUP_MEMBER_EOF
# Group member $2

status: $3
plan_purpose: implementation
primary_invariant: invariant $2
execution_group: docs/plan/execution-groups/lifecycle.json
write_scope:
  - src/$2.py
context_files:
  - AGENTS.md
checked_summary_ja: グループ構成員を完了する。

## Tasks

-  [x] finished

## Validation Notes

1. Fixture validation.
GROUP_MEMBER_EOF
}

cat >"$grouped/docs/plan/checked.md" <<'GROUP_CHECKED_EOF'
# Checked Plan Index

id	path
GROUP_CHECKED_EOF

write_group_member "284-alpha.md" alpha ready_to_archive
write_group_member "285-beta.md" beta in_progress
cat >"$grouped/docs/plan/plan.md" <<'GROUP_INDEX_EOF'
# Active Plan

id	path	status
284	docs/plan/active/284-alpha.md	ready_to_archive
285	docs/plan/active/285-beta.md	in_progress
GROUP_INDEX_EOF
python3 - "$grouped" <<'GROUP_DESCRIPTION_EOF'
import hashlib
import json
import sys
from pathlib import Path

fixture = Path(sys.argv[1])


def group_digest(value):
    data = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


members = []
for plan_id, slug in (("284", "alpha"), ("285", "beta")):
    relative = f"docs/plan/active/{plan_id}-{slug}.md"
    members.append(
        {
            "plan_id": plan_id,
            "plan_path": relative,
            "plan_digest": group_digest((fixture / relative).read_bytes()),
            "write_scope_digest": group_digest(
                json.dumps([f"src/{slug}.py"], sort_keys=True, separators=(",", ":"))
            ),
        }
    )
(fixture / "docs/plan/execution-groups/lifecycle.json").write_text(
    json.dumps(
        {
            "schema_version": 1,
            "group_id": "lifecycle",
            "target_ref": "refs/heads/main",
            "declared_independence": "disjoint fixture modules with no shared interface",
            "members": members,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
GROUP_DESCRIPTION_EOF
git -C "$grouped" add -A
git -C "$grouped" commit -qm "grouped fixture"

if (cd "$grouped" && scripts/complete-plan.sh docs/plan/active/285-beta.md \
    >/dev/null 2>"$tmp/grouped-complete.err"); then
  echo "root complete-plan accepted an enrolled execution group member" >&2
  exit 1
fi
grep -q 'enrolled in execution group' "$tmp/grouped-complete.err"
grep -q '^status: in_progress$' "$grouped/docs/plan/active/285-beta.md"

if (cd "$grouped" && scripts/finalize-active-plan.sh docs/plan/active/284-alpha.md \
    >/dev/null 2>"$tmp/grouped-finalize.err"); then
  echo "root finalize-active-plan accepted an enrolled execution group member" >&2
  exit 1
fi
grep -q 'enrolled in execution group' "$tmp/grouped-finalize.err"
grep -q '^status: ready_to_archive$' "$grouped/docs/plan/active/284-alpha.md"

# A missing group authority module must fail closed, never silently skip the gate.
mv "$grouped/scripts/parallel-plan-state.py" "$grouped/parallel-plan-state.py.away"
if (cd "$grouped" && scripts/finalize-active-plan.sh docs/plan/active/284-alpha.md \
    >/dev/null 2>"$tmp/grouped-missing-authority.err"); then
  echo "root finalize-active-plan proceeded without the group authority module" >&2
  exit 1
fi
grep -q 'missing parallel plan group authority' "$tmp/grouped-missing-authority.err"
grep -q '^status: ready_to_archive$' "$grouped/docs/plan/active/284-alpha.md"
mv "$grouped/parallel-plan-state.py.away" "$grouped/scripts/parallel-plan-state.py"

# A tracked description removed only in the worktree must not un-enrol a member.
mv "$grouped/docs/plan/execution-groups/lifecycle.json" "$tmp/lifecycle-detached.json"
if (cd "$grouped" && scripts/complete-plan.sh docs/plan/active/285-beta.md \
    >/dev/null 2>"$tmp/grouped-detached.err"); then
  echo "root complete-plan accepted a member after a worktree-only group deletion" >&2
  exit 1
fi
grep -q 'tracked but missing from the working tree' "$tmp/grouped-detached.err"
grep -q '^status: in_progress$' "$grouped/docs/plan/active/285-beta.md"
mv "$tmp/lifecycle-detached.json" "$grouped/docs/plan/execution-groups/lifecycle.json"

# The same entrypoints keep working for an ungrouped plan in the same repository.
write_group_member "290-solo.md" solo ready_to_archive
sed -i '/^execution_group: /d' "$grouped/docs/plan/active/290-solo.md"
printf '290\tdocs/plan/active/290-solo.md\tready_to_archive\n' >>"$grouped/docs/plan/plan.md"
git -C "$grouped" add -A
git -C "$grouped" commit -qm "ungrouped fixture"
(cd "$grouped" && scripts/finalize-active-plan.sh docs/plan/active/290-solo.md >/dev/null)
[ ! -e "$grouped/docs/plan/active/290-solo.md" ] || {
  echo "root finalize-active-plan left an ungrouped plan in the active directory" >&2
  exit 1
}
archived=$(find "$grouped/docs/plan/checked" -name '290-solo.md' | head -n 1)
[ -n "$archived" ] || { echo "root finalize-active-plan did not archive an ungrouped plan" >&2; exit 1; }
grep -q '^status: checked$' "$archived"

echo "root plan lifecycle test passed"
