#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/project-agent-workflow-root-plan-$$
# The required-evidence record is private and keyed by repository identity, so
# it lives outside every worktree. The fixture origin keeps it away from any
# real plan record, and this run removes exactly the paths it created.
private_records=""
cleanup() {
  rm -rf "$tmp"
  for record in $private_records; do
    rm -f "$record"
  done
}
trap cleanup EXIT HUP INT TERM

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

expected_empty="# Active Plan

No active development items.
"
if [ "$(cat "$tmp/docs/plan/plan.md")" != "$(printf '%s' "$expected_empty")" ]; then
  echo "root finalizer did not leave the canonical empty active index" >&2
  exit 1
fi

# A tab-less index is one malformed representation, so both lifecycle commands
# must refuse it before they touch any plan record.
cat >"$tmp/docs/plan/active/004-malformed.md" <<'EOF'
# Malformed index root plan

status: in_progress
checked_summary_ja: 壊れた索引を拒否する。

## Tasks

- [x] finished

## Validation Notes

- root lifecycle validation passed.
EOF
printf '# Active Plan\n\nid\\tpath\\tstatus\n004\\tdocs/plan/active/004-malformed.md\\tin_progress\n' \
  >"$tmp/docs/plan/plan.md"
malformed_before=$(cat "$tmp/docs/plan/plan.md")
checked_before=$(cat "$tmp/docs/plan/checked.md")
if (cd "$tmp" && scripts/complete-plan.sh docs/plan/active/004-malformed.md >/dev/null 2>"$tmp/complete-malformed.err"); then
  echo "root complete-plan accepted a malformed active index" >&2
  exit 1
fi
grep -q 'active plan index' "$tmp/complete-malformed.err"
grep -q '^status: in_progress$' "$tmp/docs/plan/active/004-malformed.md"
[ "$(cat "$tmp/docs/plan/plan.md")" = "$malformed_before" ] || {
  echo "root complete-plan rewrote a malformed active index" >&2
  exit 1
}

sed -i 's/^status: in_progress$/status: ready_to_archive/' "$tmp/docs/plan/active/004-malformed.md"
if (cd "$tmp" && scripts/finalize-active-plan.sh docs/plan/active/004-malformed.md >/dev/null 2>"$tmp/finalize-malformed.err"); then
  echo "root finalizer accepted a malformed active index" >&2
  exit 1
fi
grep -q 'active plan index' "$tmp/finalize-malformed.err"
[ -f "$tmp/docs/plan/active/004-malformed.md" ] || {
  echo "root finalizer archived a plan through a malformed active index" >&2
  exit 1
}
[ "$(cat "$tmp/docs/plan/plan.md")" = "$malformed_before" ] || {
  echo "root finalizer rewrote a malformed active index" >&2
  exit 1
}
[ "$(cat "$tmp/docs/plan/checked.md")" = "$checked_before" ] || {
  echo "root finalizer wrote a checked index row through a malformed active index" >&2
  exit 1
}
rm "$tmp/docs/plan/active/004-malformed.md"
printf '%s' "$expected_empty" >"$tmp/docs/plan/plan.md"

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
  "$root/scripts/parallel-plan-state.py" "$root/scripts/run-parallel-plans.py" \
  "$root/scripts/verify-parallel-plan-sessions.py" "$grouped/scripts/"
git -C "$grouped" init -q -b main
git -C "$grouped" config user.email "test@example.invalid"
git -C "$grouped" config user.name "Test"
git -C "$grouped" remote add origin "https://example.invalid/owner/lifecycle.git"

write_group_member() {
  cat >"$grouped/docs/plan/active/$1" <<GROUP_MEMBER_EOF
# Group member $2

status: $3
plan_purpose: implementation
primary_invariant: invariant $2
execution_group: docs/plan/execution-groups/lifecycle.json
acceptance:
  - two operator-started sessions publish and retire the $2 result
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

# Supplying the group execution state does not weaken the gate before the parent
# publishes that member's exact reviewed result.
group_state="$tmp/group-state.json"
grouped_head=$(git -C "$grouped" rev-parse HEAD)
(cd "$grouped" && python3 scripts/parallel-plan-state.py group-init "$group_state" \
  --group-description docs/plan/execution-groups/lifecycle.json \
  --target-ref refs/heads/main --start-commit "$grouped_head" >/dev/null)
if (cd "$grouped" && scripts/complete-plan.sh --group-state "$group_state" \
    docs/plan/active/285-beta.md >/dev/null 2>"$tmp/grouped-unpublished.err"); then
  echo "root complete-plan accepted an unpublished execution group member" >&2
  exit 1
fi
grep -q 'has not published a verified result' "$tmp/grouped-unpublished.err"
grep -q '^status: in_progress$' "$grouped/docs/plan/active/285-beta.md"

# A missing grouped execution adapter must fail closed even with a valid state.
mv "$grouped/scripts/run-parallel-plans.py" "$tmp/adapter-away.py"
if (cd "$grouped" && scripts/complete-plan.sh --group-state "$group_state" \
    docs/plan/active/285-beta.md >/dev/null 2>"$tmp/grouped-no-adapter.err"); then
  echo "root complete-plan proceeded without the grouped execution adapter" >&2
  exit 1
fi
grep -q 'grouped execution adapter' "$tmp/grouped-no-adapter.err"
grep -q '^status: in_progress$' "$grouped/docs/plan/active/285-beta.md"
mv "$tmp/adapter-away.py" "$grouped/scripts/run-parallel-plans.py"

# Bind the live-evidence contract after the enrollment assertions and rebuild
# the grouped state so the later lifecycle checks use a real gated member. The
# contract names one exact acceptance item the plan already carries, because the
# obligation is that item and not a manifest keyword.
live_acceptance_item="two operator-started sessions publish and retire the beta result"
live_acceptance_digest="sha256:$(printf '%s' "$live_acceptance_item" | sha256sum | cut -d' ' -f1)"
sed -i \
  "/^execution_group:/i live_evidence_contract: parallel_sessions_v1\nlive_evidence_acceptance_sha256: $live_acceptance_digest" \
  "$grouped/docs/plan/active/285-beta.md"
python3 - "$grouped" <<'GROUP_LIVE_BINDING_EOF'
import hashlib
import json
import sys
from pathlib import Path

fixture = Path(sys.argv[1])
description_path = fixture / "docs/plan/execution-groups/lifecycle.json"
description = json.loads(description_path.read_text(encoding="utf-8"))
plan = fixture / "docs/plan/active/285-beta.md"
for member in description["members"]:
    if member["plan_path"] == "docs/plan/active/285-beta.md":
        member["plan_digest"] = "sha256:" + hashlib.sha256(plan.read_bytes()).hexdigest()
description_path.write_text(json.dumps(description, indent=2) + "\n", encoding="utf-8")
GROUP_LIVE_BINDING_EOF
git -C "$grouped" add -A
git -C "$grouped" commit -qm "bind live evidence fixture"
rm "$group_state"
grouped_head=$(git -C "$grouped" rev-parse HEAD)
(cd "$grouped" && python3 scripts/parallel-plan-state.py group-init "$group_state" \
  --group-description docs/plan/execution-groups/lifecycle.json \
  --target-ref refs/heads/main --start-commit "$grouped_head" >/dev/null)

# The gate reads one canonical private record outside every worktree, so a
# gated plan with no record refuses instead of passing by default.
beta_record=$(cd "$grouped" && python3 - <<'PY'
import importlib.util
from pathlib import Path

script = Path("scripts/verify-parallel-plan-sessions.py")
spec = importlib.util.spec_from_file_location("live_verifier", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.requirement_path(Path.cwd(), "docs/plan/active/285-beta.md"))
PY
)
private_records="$private_records $beta_record"
rm -f "$beta_record"
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/285-beta.md >/dev/null 2>"$tmp/live-record-missing.err"); then
  echo "live verifier passed a gated plan with no required-evidence record" >&2
  exit 1
fi
grep -q 'required-evidence record is missing' "$tmp/live-record-missing.err"

# A private verifier for the live parallel-session proof fails closed without a
# matching report digest.
required_record="$tmp/required-evidence.json"
cat >"$required_record" <<EOF
{
  "plan_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "live_acceptance_digest": "$live_acceptance_digest",
  "execution_genesis": "genesis:fixture",
  "report_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
EOF
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py \
    --plan docs/plan/active/285-beta.md --report "$tmp/live-report.json" \
    --required-evidence "$required_record" >/dev/null 2>"$tmp/live-report-missing.err"); then
  echo "live verifier accepted a missing report" >&2
  exit 1
fi
grep -q 'live report does not exist' "$tmp/live-report-missing.err"

cat >"$tmp/live-report.json" <<EOF
{
  "plan_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "live_acceptance_digest": "$live_acceptance_digest",
  "distinct_session_ids": ["session-a", "session-b"],
  "implementation_intervals": [
    {"start": "2026-09-16T00:00:00Z", "end": "2026-09-16T00:10:00Z"},
    {"start": "2026-09-16T00:05:00Z", "end": "2026-09-16T00:20:00Z"}
  ]
}
EOF
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py \
    --plan docs/plan/active/285-beta.md --report "$tmp/live-report.json" \
    --required-evidence "$required_record" >/dev/null 2>"$tmp/live-report-digest.err"); then
  echo "live verifier accepted mismatched digest evidence" >&2
  exit 1
fi
grep -q 'digest mismatch' "$tmp/live-report-digest.err"

actual_report_digest=$(python3 - "$tmp/live-report.json" <<'PY'
import hashlib, pathlib, sys
print('sha256:' + hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
python3 - "$required_record" "$tmp/live-report.json" "$grouped/docs/plan/active/285-beta.md" <<'PY'
import json, hashlib, pathlib, sys
required = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
plan = pathlib.Path(sys.argv[3])
record = json.loads(required.read_text())
record['plan_digest'] = 'sha256:' + hashlib.sha256(plan.read_bytes()).hexdigest()
record['execution_plan_digest'] = record['plan_digest']
record['report_digest'] = 'sha256:' + hashlib.sha256(report.read_bytes()).hexdigest()
required.write_text(json.dumps(record, indent=2) + '\n')
PY
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py \
    --plan docs/plan/active/285-beta.md --report "$tmp/live-report.json" \
    --required-evidence "$required_record" >/dev/null); then
  :
else
  echo "live verifier rejected matching required evidence and report" >&2
  exit 1
fi

# The canonical record is written in the schema the gate verifies, and binding
# the verified report is what discharges the obligation.
(cd "$grouped" && python3 - "$beta_record" "$actual_report_digest" <<'PY'
import importlib.util
import sys
from pathlib import Path

script = Path("scripts/verify-parallel-plan-sessions.py")
spec = importlib.util.spec_from_file_location("live_verifier", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
plan = "docs/plan/active/285-beta.md"
contract = module.plan_contract(Path.cwd(), plan)
record = {
    "schema_version": module.REQUIREMENT_SCHEMA_VERSION,
    "record_type": module.REQUIREMENT_RECORD_TYPE,
    "repository_identity": module.repository_identity(Path.cwd()),
    "plan_path": plan,
    "plan_digest": contract["plan_digest"],
    "execution_plan_digest": contract["plan_digest"],
    "live_evidence_contract": contract["contract"],
    "live_acceptance_digest": contract["live_acceptance_digest"],
    "execution_genesis_digest": "sha256:" + "1" * 64,
    "run_id": "lifecycle-fixture-run",
    "reserved_group_id": "lifecycle",
    "state": "reserved",
    "group_description_digest": "",
    "report_path": "",
    "report_digest": "",
    "record_digest": "",
}
record["record_digest"] = module.self_digest(record)
module.write_private_json(Path(sys.argv[1]), record)
PY
)

# A reserved record is never success, and the serial completion entrypoint must
# reach that same conclusion.
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/285-beta.md >/dev/null 2>"$tmp/live-reserved.err"); then
  echo "live verifier passed a reserved required-evidence record" >&2
  exit 1
fi
grep -q 'reserves the demonstration' "$tmp/live-reserved.err"

# Removing the contract fields is not a way out: the obligation lives in the
# private record, so the gate refuses the edited plan instead of releasing it.
cp "$grouped/docs/plan/active/285-beta.md" "$tmp/beta-with-contract.md"
sed -i '/^live_evidence_/d' "$grouped/docs/plan/active/285-beta.md"
if (cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/285-beta.md >/dev/null 2>"$tmp/live-dropped.err"); then
  echo "live verifier released an obligation after the contract fields were removed" >&2
  exit 1
fi
grep -q 'no longer declares' "$tmp/live-dropped.err"
cp "$tmp/beta-with-contract.md" "$grouped/docs/plan/active/285-beta.md"

# Binding the verified report discharges the obligation, and only then does the
# gate pass. The bound report is private evidence, so it carries private mode.
chmod 600 "$tmp/live-report.json"
(cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py bind \
  --plan docs/plan/active/285-beta.md --report "$tmp/live-report.json" >/dev/null)
(cd "$grouped" && python3 scripts/verify-parallel-plan-sessions.py require \
  --plan docs/plan/active/285-beta.md >"$tmp/live-satisfied.json")
grep -q '"satisfied": true' "$tmp/live-satisfied.json"

# The report environment variable configures the non-gating report check only.
# Pointing it at forged bytes must not change what require concludes.
cat >"$tmp/forged-evidence.json" <<EOF
{
  "plan_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "live_acceptance_digest": "$live_acceptance_digest",
  "execution_genesis": "genesis:forged",
  "report_digest": "$actual_report_digest"
}
EOF
sed -i '/^live_evidence_/d' "$grouped/docs/plan/active/285-beta.md"
if (cd "$grouped" && PROJECT_AGENT_WORKFLOW_REQUIRED_EVIDENCE="$tmp/forged-evidence.json" \
    python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/285-beta.md >/dev/null 2>"$tmp/live-env.err"); then
  echo "live verifier let the report environment variable waive the gate" >&2
  exit 1
fi
grep -q 'no longer declares' "$tmp/live-env.err"
cp "$tmp/beta-with-contract.md" "$grouped/docs/plan/active/285-beta.md"

fixed_required_record="$beta_record"

# An owner-authorized acceptance partition moves the live-evidence obligation to
# the plan that now carries the exact item. The source gate is released, the
# destination gate is not, and no lifecycle entrypoint can waive either. This
# fixture is a separate repository with its own parent-direct execution ledger,
# so it never reaches the evidence or ledger of a real plan.
transfer="$tmp/transfer"
transfer_state="$tmp/transfer-state"
mkdir -p "$transfer/scripts" "$transfer/docs/plan/active" "$transfer/docs/plan/backlog" \
  "$transfer_state"
cp "$root/scripts/complete-plan.sh" "$root/scripts/finalize-active-plan.sh" \
  "$root/scripts/parallel-plan-state.py" "$root/scripts/plan-execution-state.py" \
  "$root/scripts/verify-parallel-plan-sessions.py" "$transfer/scripts/"
git -C "$transfer" init -q -b main
git -C "$transfer" config user.email "test@example.invalid"
git -C "$transfer" config user.name "Test"
git -C "$transfer" remote add origin "https://example.invalid/owner/transfer.git"

transfer_item="two operator-started sessions publish and retire the partitioned result"
transfer_digest="sha256:$(printf '%s' "$transfer_item" | sha256sum | cut -d' ' -f1)"
cat >"$transfer/docs/plan/active/286-source.md" <<EOF
# Partition source

status: in_progress
plan_purpose: implementation
primary_invariant: the partitioned source invariant
live_evidence_contract: parallel_sessions_v1
live_evidence_acceptance_sha256: $transfer_digest
acceptance:
  - the retained acceptance item
  - $transfer_item
write_scope:
  - AGENTS.md
checked_summary_ja: 分離元計画を完了する。

## Tasks

-  [x] finished

## Validation Notes

1. Fixture validation.
EOF
cat >"$transfer/docs/plan/backlog/287-destination.md" <<EOF
# Partition destination

status: backlog
plan_purpose: implementation
primary_invariant: the partitioned destination invariant
acceptance:
  - $transfer_item
write_scope:
  - AGENTS.md
checked_summary_ja: 分離先計画を完了する。

## Tasks

-  [ ] unfinished

## Validation Notes

1. Pending validation.
EOF
printf 'fixture\n' >"$transfer/AGENTS.md"
git -C "$transfer" add -A
git -C "$transfer" commit -qm "partition baseline"

source_record=$(cd "$transfer" && python3 - <<'PY'
import importlib.util
from pathlib import Path

script = Path("scripts/verify-parallel-plan-sessions.py")
spec = importlib.util.spec_from_file_location("live_verifier", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.requirement_path(Path.cwd(), "docs/plan/active/286-source.md"))
PY
)
private_records="$private_records $source_record"

# Drive one real parent-direct ledger to a checked acceptance partition, then
# publish the owner-authorized transfer through the verifier itself.
(cd "$transfer" && python3 - "$transfer_state" <<'PY'
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

state = Path(sys.argv[1])
ledger = state / "execution.json"
lifecycle = state / "lifecycle.json"
plan = "docs/plan/active/286-source.md"
destination = "docs/plan/backlog/287-destination.md"


def digest_text(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def load(name, script):
    specification = importlib.util.spec_from_file_location(name, Path(script))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run(*arguments):
    completed = subprocess.run(
        [sys.executable, "scripts/plan-execution-state.py", *arguments],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SystemExit(f"ledger command failed: {completed.stderr.strip()}")
    return completed


head = subprocess.run(
    ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
).stdout.strip()
run(
    "prepare-parent-direct", str(ledger),
    "--run-id", "partition-run-001",
    "--plan", plan,
    "--source-head", head,
    "--lifecycle-state", str(lifecycle),
    "--reviewer-registry", str(state / "reviewers.json"),
    "--continuation-registry", str(state / "continuation.json"),
)
Path("AGENTS.md").write_text("fixture\nreviewed\n", encoding="utf-8")
execution = load("partition_state", "scripts/plan-execution-state.py")
recorded = json.loads(ledger.read_text(encoding="utf-8"))
identity = execution.parent_direct_review_identity(recorded)[1]
invariant = digest_text("the partitioned source invariant")
run(
    "record", str(ledger),
    "--run-id", "partition-run-001",
    "--event-id", "partition-review-001",
    "--event-type", "parent_review",
    "--implementation-mode", "parent_direct",
    "--invariant-digest", invariant,
    "--finding-severity", "High",
    "--independent-review-receipt-digest", digest_text("partition review receipt"),
    "--lifecycle-state", str(lifecycle),
    "--candidate-lifecycle-digest", identity,
)
recorded = json.loads(ledger.read_text(encoding="utf-8"))
verifier = load("partition_verifier", "scripts/verify-parallel-plan-sessions.py")
committed = subprocess.run(
    ["git", "show", f"{head}:{plan}"], check=True, capture_output=True
).stdout
manifest = verifier.plan_manifest(committed.decode("utf-8"))
digests = [digest_text(item) for item in manifest["acceptance"]]
live = manifest["live_evidence_acceptance_sha256"]
evidence = state / "descope-evidence.json"
evidence.write_text(
    json.dumps(
        {
            "schema_version": 1,
            "plan_path": plan,
            "plan_digest": "sha256:" + hashlib.sha256(committed).hexdigest(),
            "source_head": head,
            "primary_invariant_digest": recorded["primary_invariant_digest"],
            "affected_invariant_digests": [invariant],
            "candidate_lifecycle_identity_digest": recorded[
                "candidate_lifecycle_identity_digest"
            ],
            "candidate_lifecycle_digest": identity,
            "independent_review_receipt_digest": digest_text(
                "partition descope receipt"
            ),
            "source_acceptance_digests": digests,
            "retained_acceptance_digests": [d for d in digests if d != live],
            "deferred_acceptance_digests": [live],
            "deferred_backlog_path": destination,
            "bounded_write_scope": True,
            "source_scope_unchanged": True,
            "validation_authority_unchanged": True,
            "invariant_boundaries_unchanged": True,
            "primary_invariant_unchanged": True,
            "safety_conditions_unchanged": True,
            "external_effect_authority_unchanged": True,
            "independent_invariant_count": 1,
        },
        sort_keys=True,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
run(
    "record", str(ledger),
    "--run-id", "partition-run-001",
    "--event-id", "partition-descope-001",
    "--event-type", "descope_classification",
    "--implementation-mode", "parent_direct",
    "--invariant-digest", invariant,
    "--independent-review-receipt-digest", digest_text("partition descope receipt"),
    "--descope-evidence-file", str(evidence),
    "--lifecycle-state", str(lifecycle),
    "--candidate-lifecycle-digest", identity,
)
Path("AGENTS.md").write_text("fixture\n", encoding="utf-8")

reserved = subprocess.run(
    [
        sys.executable, "scripts/verify-parallel-plan-sessions.py", "init",
        "--plan", plan, "--execution-state", str(ledger), "--group-id", "partition",
    ],
    check=True, text=True, capture_output=True,
)
record = json.loads(
    Path(verifier.requirement_path(Path.cwd(), plan)).read_text(encoding="utf-8")
)
authorization = {
    "schema_version": verifier.TRANSFER_SCHEMA_VERSION,
    "record_type": verifier.AUTHORIZATION_RECORD_TYPE,
    "repository_identity": record["repository_identity"],
    "source_plan_path": plan,
    "source_plan_digest": verifier.digest_bytes(Path(plan).read_bytes()),
    "destination_plan_path": destination,
    "destination_plan_digest": verifier.digest_bytes(Path(destination).read_bytes()),
    "live_acceptance_digest": record["live_acceptance_digest"],
    "source_record_digest": record["record_digest"],
    "execution_genesis_digest": record["execution_genesis_digest"],
    "run_id": record["run_id"],
    "authorization": (
        "Move the live-evidence obligation of the source plan to the deferred "
        "destination plan and keep the stopped record unchanged."
    ),
    "record_digest": "",
}
authorization["record_digest"] = verifier.self_digest(authorization)
authorization_path = state / "authorization.json"
authorization_path.write_text(
    json.dumps(authorization, sort_keys=True, indent=2) + "\n", encoding="utf-8"
)
authorization_path.chmod(0o600)
published = subprocess.run(
    [
        sys.executable, "scripts/verify-parallel-plan-sessions.py", "transfer",
        "--source-plan", plan, "--destination-plan", destination,
        "--execution-state", str(ledger),
        "--owner-authorization", str(authorization_path),
    ],
    check=True, text=True, capture_output=True,
)
(state / "transfer-record-path").write_text(
    json.loads(published.stdout)["record_path"] + "\n", encoding="utf-8"
)
PY
)
private_records="$private_records $(cat "$transfer_state/transfer-record-path")"

# The verified transfer releases the source gate and nothing else.
(cd "$transfer" && python3 scripts/verify-parallel-plan-sessions.py require \
  --plan docs/plan/active/286-source.md >"$tmp/transfer-source.json")
grep -q '"released": true' "$tmp/transfer-source.json"
grep -q '"satisfied": false' "$tmp/transfer-source.json"

# The destination keeps the unmet obligation even though its own manifest
# declares no contract at all.
if (cd "$transfer" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/backlog/287-destination.md >/dev/null 2>"$tmp/transfer-destination.err"); then
  echo "live verifier passed a destination that still owes the demonstration" >&2
  exit 1
fi
grep -q 'live-evidence obligation' "$tmp/transfer-destination.err"

# The ordinary backlog to active promotion must not drop the obligation.
git -C "$transfer" mv docs/plan/backlog/287-destination.md \
  docs/plan/active/287-destination.md
promoted_record=$(cd "$transfer" && python3 - <<'PY'
import importlib.util
from pathlib import Path

script = Path("scripts/verify-parallel-plan-sessions.py")
spec = importlib.util.spec_from_file_location("live_verifier", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.requirement_path(Path.cwd(), "docs/plan/active/287-destination.md"))
PY
)
private_records="$private_records $promoted_record"
(cd "$transfer" && python3 scripts/verify-parallel-plan-sessions.py require \
  --plan docs/plan/active/286-source.md >"$tmp/transfer-promoted.json")
grep -q '"destination_plan_path": "docs/plan/active/287-destination.md"' \
  "$tmp/transfer-promoted.json"
if (cd "$transfer" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/287-destination.md >/dev/null 2>/dev/null); then
  echo "live verifier passed a promoted destination that still owes the demonstration" >&2
  exit 1
fi

# Every lifecycle entrypoint reaches the same conclusion: the destination stays
# shut, and no manifest edit or report environment variable reopens it.
for entrypoint in complete-plan.sh finalize-active-plan.sh; do
  if (cd "$transfer" && PROJECT_AGENT_WORKFLOW_REQUIRED_EVIDENCE="$tmp/forged-evidence.json" \
      "scripts/$entrypoint" docs/plan/active/287-destination.md \
      >/dev/null 2>"$tmp/transfer-$entrypoint.err"); then
    echo "root $entrypoint completed a destination that still owes the demonstration" >&2
    exit 1
  fi
done

# Gutting the destination is not a discharge either: the source release depends
# on the destination still carrying the exact transferred item.
sed -i "s|  - $transfer_item|  - an unrelated acceptance item|" \
  "$transfer/docs/plan/active/287-destination.md"
if (cd "$transfer" && python3 scripts/verify-parallel-plan-sessions.py require \
    --plan docs/plan/active/286-source.md >/dev/null 2>"$tmp/transfer-gutted.err"); then
  echo "live verifier released a source whose destination dropped the item" >&2
  exit 1
fi
grep -q 'would be lost' "$tmp/transfer-gutted.err"

# After the parent publishes that member's verified result, the same serial
# entrypoints complete and archive it, while its unpublished partner stays shut.
permit_id="lifecycle-beta-permit"
(cd "$grouped" && python3 scripts/parallel-plan-state.py permit-issue "$group_state" \
  --member docs/plan/active/285-beta.md --permit-id "$permit_id" \
  --workspace-digest "sha256:$(printf 'lifecycle workspace' | sha256sum | cut -d' ' -f1)" \
  --output "$tmp/beta-permit.json" >/dev/null)
(cd "$grouped" && python3 scripts/parallel-plan-state.py lease-acquire "$group_state" \
  --member docs/plan/active/285-beta.md --owner lifecycle-parent >/dev/null)
(cd "$grouped" && python3 scripts/parallel-plan-state.py publication-record \
  "$group_state" --member docs/plan/active/285-beta.md --permit-id "$permit_id" \
  --commit "$grouped_head" \
  --assembly-digest "sha256:$(printf 'lifecycle assembly' | sha256sum | cut -d' ' -f1)" \
  >/dev/null)
(cd "$grouped" && scripts/complete-plan.sh --group-state "$group_state" \
  docs/plan/active/285-beta.md >/dev/null)
grep -q '^status: ready_to_archive$' "$grouped/docs/plan/active/285-beta.md"
git -C "$grouped" add -A
git -C "$grouped" commit -qm "published member completion"
(cd "$grouped" && scripts/finalize-active-plan.sh --group-state "$group_state" \
  docs/plan/active/285-beta.md >/dev/null)
published_archive=$(find "$grouped/docs/plan/checked" -name '285-beta.md' | head -n 1)
[ -n "$published_archive" ] || {
  echo "root finalize-active-plan did not archive a published group member" >&2
  exit 1
}
if (cd "$grouped" && scripts/finalize-active-plan.sh --group-state "$group_state" \
    docs/plan/active/284-alpha.md >/dev/null 2>"$tmp/grouped-partner.err"); then
  echo "root finalize-active-plan accepted an unpublished partner member" >&2
  exit 1
fi
grep -q 'has not published a verified result' "$tmp/grouped-partner.err"
grep -q '^status: ready_to_archive$' "$grouped/docs/plan/active/284-alpha.md"
git -C "$grouped" add -A
git -C "$grouped" commit -qm "published member archive"

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
if (cd "$grouped" && scripts/complete-plan.sh docs/plan/active/284-alpha.md \
    >/dev/null 2>"$tmp/grouped-detached.err"); then
  echo "root complete-plan accepted a member after a worktree-only group deletion" >&2
  exit 1
fi
grep -q 'tracked but missing from the working tree' "$tmp/grouped-detached.err"
grep -q '^status: ready_to_archive$' "$grouped/docs/plan/active/284-alpha.md"
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

# The committed pre-commit hook judges the exact staged tree through the same
# completion gate, and every documented local escape stays outside its reach.
hookfix="$tmp/precommit"
mkdir -p "$hookfix/scripts" "$hookfix/.githooks" "$hookfix/docs/plan/active" "$hookfix/docs/plan/checked"
cp "$root/scripts/complete-plan.sh" "$root/scripts/finalize-active-plan.sh" \
  "$root/scripts/parallel-plan-state.py" "$root/scripts/check-agent-completion.sh" \
  "$hookfix/scripts/"
cp "$root/.githooks/pre-commit" "$hookfix/.githooks/pre-commit"
chmod 755 "$hookfix/.githooks/pre-commit"
git -C "$hookfix" init -q -b main
git -C "$hookfix" config user.email "test@example.invalid"
git -C "$hookfix" config user.name "Test"
git -C "$hookfix" config core.hooksPath .githooks

write_hook_plan() {
  cat >"$hookfix/docs/plan/active/$1" <<HOOK_PLAN_EOF
# Hook fixture plan $2

status: in_progress
checked_summary_ja: 完了ゲートの境界を確認する。

## Tasks

- [$3] fixture task

## Validation Notes

- $4
HOOK_PLAN_EOF
}

write_hook_index() {
  {
    printf '# Active Plan\n\n'
    printf 'id\tpath\tstatus\n'
    while [ "$#" -gt 0 ]; do
      printf '%s\tdocs/plan/active/%s\tin_progress\n' "${1%%-*}" "$1"
      shift
    done
  } >"$hookfix/docs/plan/plan.md"
}

hook_commit() {
  git -C "$hookfix" add -A
  git -C "$hookfix" commit -qm "$1" 2>"$tmp/precommit-$2.err"
}

cat >"$hookfix/docs/plan/checked.md" <<'HOOK_CHECKED_EOF'
# Checked Plan Index

id	path
HOOK_CHECKED_EOF

write_hook_plan "001-hook.md" one " " "Pending validation."
write_hook_index "001-hook.md"
hook_commit "unfinished plan" unfinished ||
  { echo "pre-commit hook blocked an unfinished plan" >&2; cat "$tmp/precommit-unfinished.err" >&2; exit 1; }

# A staged completed plan that is still in_progress is refused, and the refusal
# names the lifecycle command that resolves it.
write_hook_plan "001-hook.md" one x "Fixture validation passed."
if hook_commit "completed plan" completed; then
  echo "pre-commit hook accepted a staged completed in_progress plan" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-completed.err"
grep -q 'scripts/complete-plan.sh' "$tmp/precommit-completed.err"

# The staged tree decides. A completion that exists only in the working tree is
# not judged, and a completion that exists only in the index is.
git -C "$hookfix" reset -q
write_hook_plan "001-hook.md" one x "Fixture validation passed."
mkdir -p "$hookfix/src"
printf 'unrelated\n' >"$hookfix/src/unrelated.txt"
git -C "$hookfix" add src/unrelated.txt
git -C "$hookfix" commit -qm "unstaged completion" 2>"$tmp/precommit-unstaged.err" ||
  { echo "pre-commit hook judged unstaged plan bytes" >&2; cat "$tmp/precommit-unstaged.err" >&2; exit 1; }

git -C "$hookfix" add docs/plan/active/001-hook.md
write_hook_plan "001-hook.md" one " " "Pending validation."
if git -C "$hookfix" commit -qm "staged completion" 2>"$tmp/precommit-staged.err"; then
  echo "pre-commit hook ignored a staged completion behind an unfinished working tree" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-staged.err"
git -C "$hookfix" checkout -q -- docs/plan/active/001-hook.md

# A ready-to-archive snapshot directs the reader to finalization, and the
# finalized tree commits without a hook exception.
(cd "$hookfix" && scripts/complete-plan.sh docs/plan/active/001-hook.md >/dev/null)
if hook_commit "ready to archive" ready; then
  echo "pre-commit hook accepted a staged ready-to-archive plan" >&2
  exit 1
fi
grep -q 'ready-to-archive plan blocks completion' "$tmp/precommit-ready.err"
grep -q 'scripts/finalize-active-plan.sh' "$tmp/precommit-ready.err"
(cd "$hookfix" && scripts/finalize-active-plan.sh docs/plan/active/001-hook.md >/dev/null)
hook_commit "finalized plan" finalized ||
  { echo "pre-commit hook blocked a finalized staged tree" >&2; cat "$tmp/precommit-finalized.err" >&2; exit 1; }

# Everything below reuses one staged blocking state.
write_hook_plan "002-blocked.md" two x "Fixture validation passed."
write_hook_index "002-blocked.md"
if hook_commit "blocking state" blocking; then
  echo "pre-commit hook accepted a second staged completed plan" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-blocking.err"

# A skip-worktree entry is staged content, so a sparse selection must not hide
# a plan record from the judgment.
git -C "$hookfix" update-index --skip-worktree docs/plan/active/002-blocked.md
if git -C "$hookfix" commit -qm "skip-worktree record" 2>"$tmp/precommit-sparse.err"; then
  echo "pre-commit hook skipped a skip-worktree plan record" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-sparse.err"
git -C "$hookfix" update-index --no-skip-worktree docs/plan/active/002-blocked.md

# Expansion copies the staged bytes. A configured filter driver never runs, and
# line-ending conversion never rewrites the records the gate reads.
printf 'docs/plan/active/*.md filter=hookdemo\n' >"$hookfix/.gitattributes"
git -C "$hookfix" add .gitattributes
git -C "$hookfix" config filter.hookdemo.clean cat
git -C "$hookfix" config filter.hookdemo.smudge 'tr x " "'
git -C "$hookfix" config filter.hookdemo.required true
git -C "$hookfix" config core.autocrlf true
if git -C "$hookfix" commit -qm "filtered expansion" 2>"$tmp/precommit-filter.err"; then
  echo "pre-commit hook judged filtered bytes instead of staged bytes" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-filter.err"
git -C "$hookfix" config --unset core.autocrlf

# A filter driver whose name cannot be neutralized fails closed instead of
# letting an unreviewed command run during expansion.
git -C "$hookfix" config 'filter.hook demo.smudge' cat
if git -C "$hookfix" commit -qm "unusual driver name" 2>"$tmp/precommit-driver.err"; then
  echo "pre-commit hook expanded the index with an un-neutralized filter driver" >&2
  exit 1
fi
grep -q 'cannot neutralize a Git filter driver' "$tmp/precommit-driver.err"
git -C "$hookfix" config --remove-section 'filter.hook demo'
git -C "$hookfix" config --remove-section filter.hookdemo
git -C "$hookfix" rm -q --cached .gitattributes
rm "$hookfix/.gitattributes"

# A staged tree without any completion gate fails closed.
git -C "$hookfix" rm -q --cached scripts/check-agent-completion.sh
mv "$hookfix/scripts/check-agent-completion.sh" "$tmp/precommit-gate-away.sh"
if git -C "$hookfix" commit -qm "missing gate" 2>"$tmp/precommit-missing.err"; then
  echo "pre-commit hook committed without a staged completion gate" >&2
  exit 1
fi
grep -q 'ships no plan completion gate' "$tmp/precommit-missing.err"
grep -q 'no-verify' "$tmp/precommit-missing.err"
cp "$tmp/precommit-gate-away.sh" "$hookfix/scripts/check-agent-completion.sh"
git -C "$hookfix" add scripts/check-agent-completion.sh

# Documented local escapes: an explicit bypass, a non-executable hook file, and
# an unselected core.hooksPath all leave the blocking state committable.
git -C "$hookfix" commit -q --no-verify -m "explicit bypass" ||
  { echo "git commit --no-verify was blocked" >&2; exit 1; }
git -C "$hookfix" log -1 --format=%s | grep -q '^explicit bypass$'

write_hook_plan "003-blocked.md" three x "Fixture validation passed."
write_hook_index "003-blocked.md"
chmod 644 "$hookfix/.githooks/pre-commit"
hook_commit "non-executable hook" nonexec ||
  { echo "a non-executable hook still blocked the commit" >&2; exit 1; }
chmod 755 "$hookfix/.githooks/pre-commit"

write_hook_plan "004-blocked.md" four x "Fixture validation passed."
write_hook_index "004-blocked.md"
git -C "$hookfix" config --unset core.hooksPath
hook_commit "inactive hooks path" inactive ||
  { echo "an unselected core.hooksPath still blocked the commit" >&2; exit 1; }
git -C "$hookfix" config core.hooksPath .githooks

# One relative main-clone setting also governs a linked worktree.
linked="$tmp/precommit-linked"
git -C "$hookfix" worktree add -q -b linked "$linked"
mkdir -p "$linked/docs/plan/active"
cat >"$linked/docs/plan/active/005-linked.md" <<'HOOK_LINKED_EOF'
# Hook fixture plan five

status: in_progress
checked_summary_ja: 完了ゲートの境界を確認する。

## Tasks

- [x] fixture task

## Validation Notes

- Fixture validation passed.
HOOK_LINKED_EOF
{
  printf '# Active Plan\n\n'
  printf 'id\tpath\tstatus\n'
  printf '005\tdocs/plan/active/005-linked.md\tin_progress\n'
} >"$linked/docs/plan/plan.md"
git -C "$linked" add -A
if git -C "$linked" commit -qm "linked worktree" 2>"$tmp/precommit-linked.err"; then
  echo "pre-commit hook did not run from a linked worktree" >&2
  exit 1
fi
grep -q 'completed plan is not marked ready' "$tmp/precommit-linked.err"
git -C "$hookfix" worktree remove --force "$linked"

# The root-only activation detector reports an inactive selection and never
# writes Git configuration.
lint="$root/scripts/lint-project-workflow.sh"
activation="$tmp/activation"
mkdir -p "$activation/.githooks"
cp "$root/.githooks/pre-commit" "$activation/.githooks/pre-commit"
git -C "$activation" init -q -b main

if CI= "$lint" --check-hook-activation "$activation" >/dev/null 2>"$tmp/activation-inactive.err"; then
  echo "root validation accepted an unselected core.hooksPath" >&2
  exit 1
fi
grep -q 'git config core.hooksPath .githooks' "$tmp/activation-inactive.err"
[ -z "$(git -C "$activation" config --get core.hooksPath || true)" ] ||
  { echo "root validation wrote core.hooksPath" >&2; exit 1; }

git -C "$activation" config core.hooksPath .githooks
CI= "$lint" --check-hook-activation "$activation" >/dev/null
git -C "$activation" config core.hooksPath .other-hooks
if CI= "$lint" --check-hook-activation "$activation" >/dev/null 2>&1; then
  echo "root validation accepted a different core.hooksPath" >&2
  exit 1
fi
git -C "$activation" config --unset core.hooksPath

CI=true "$lint" --check-hook-activation "$activation" >/dev/null

# A shipped hook outside any work tree, such as an extracted archive, reports
# nothing because no Git configuration can select it there.
plain=$(mktemp -d "${TMPDIR:-/tmp}/project-agent-workflow-plain-XXXXXX")
mkdir -p "$plain/.githooks"
cp "$root/.githooks/pre-commit" "$plain/.githooks/pre-commit"
if git -C "$plain" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "the non-work-tree activation fixture is inside a work tree: $plain" >&2
  exit 1
fi
CI= "$lint" --check-hook-activation "$plain" >/dev/null
rm -rf "$plain"

rm "$activation/.githooks/pre-commit"
CI= "$lint" --check-hook-activation "$activation" >/dev/null

echo "root plan lifecycle test passed"
