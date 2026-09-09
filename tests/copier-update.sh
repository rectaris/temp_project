#!/bin/sh
set -eu

require_copier=${REQUIRE_COPIER:-0}
case "$#" in
  0) ;;
  1)
    [ "$1" = "--require-copier" ] || { echo "Usage: $0 [--require-copier]" >&2; exit 2; }
    require_copier=1
    ;;
  *) echo "Usage: $0 [--require-copier]" >&2; exit 2 ;;
esac

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
scratch_base=${SANDBOXED_PLAN_WORKER_SCRATCH_DIR:-${TMPDIR:-/tmp}}
tmp=$(mktemp -d "$scratch_base/project-agent-workflow-update.XXXXXX")
tmp=$(CDPATH= cd -- "$tmp" && pwd -P)
source_head_before=$(git -C "$root" rev-parse HEAD)
source_status_before=$(git -C "$root" status --porcelain=v1 --untracked-files=all)

# Transition state of the v1.4.5 validation-witness migration lane. The
# release path, the attempt-state path, and both process identifiers are
# written before the handler is registered so every early exit can release the
# held update child and stop the detached guardian under `set -u`.
v145_release="$tmp/v145-guardian-release"
v145_attempt=
update_pid=
guardian_pid=0

cleanup() {
  result=$?
  trap - EXIT HUP INT TERM
  touch "$v145_release" 2>/dev/null || true
  # Plan 183 settled the same bounded update-process wait for the cleanup
  # path, so the released child is waited for and retired here before the
  # guardian identifier is read and the temporary root is removed.
  if [ -n "$update_pid" ]; then
    cleanup_waited=0
    while [ "$cleanup_waited" -lt 30 ]; do
      if ! kill -0 "$update_pid" 2>/dev/null; then
        break
      fi
      cleanup_waited=$((cleanup_waited + 1))
      sleep 1
    done
    if kill -0 "$update_pid" 2>/dev/null; then
      kill -TERM "$update_pid" 2>/dev/null || true
      sleep 5
      kill -KILL "$update_pid" 2>/dev/null || true
    fi
    wait "$update_pid" 2>/dev/null || true
    update_pid=
  fi
  # An exit between the guardian start and the pending assertion leaves this
  # handler without the identifier, so recover it from the published attempt
  # state of the quiescent child before the temporary root is removed.
  case "$guardian_pid" in
    ''|*[!0-9]*) guardian_pid=0 ;;
  esac
  if [ "$guardian_pid" -eq 0 ] && [ -n "$v145_attempt" ] && [ -f "$v145_attempt" ]; then
    guardian_pid=$(sed -n 's/^ *"guardian_pid": *\([0-9][0-9]*\),\{0,1\} *$/\1/p' "$v145_attempt" 2>/dev/null || true)
    case "$guardian_pid" in
      ''|*[!0-9]*) guardian_pid=0 ;;
    esac
  fi
  if [ "$guardian_pid" -gt 0 ]; then
    kill -TERM "$guardian_pid" 2>/dev/null || true
  fi
  source_head_after=$(git -C "$root" rev-parse HEAD 2>/dev/null || true)
  source_status_after=$(git -C "$root" status --porcelain=v1 --untracked-files=all 2>/dev/null || true)
  if [ "$source_head_after" != "$source_head_before" ] || [ "$source_status_after" != "$source_status_before" ]; then
    echo "Copier fixture mutated the source repository" >&2
    result=1
  fi
  rm -rf "$tmp"
  exit "$result"
}
trap cleanup EXIT HUP INT TERM
. "$root/tests/lib-copier.sh"

require_fixture_path() {
  fixture_path=$1
  fixture_resolved=$(CDPATH= cd -- "$fixture_path" && pwd -P)
  case "$fixture_resolved" in
    "$tmp"|"$tmp"/*) ;;
    *)
      echo "refusing fixture Git operation outside temporary root: $fixture_resolved" >&2
      exit 1
      ;;
  esac
}

fixture_git() {
  fixture_repository=$1
  shift
  require_fixture_path "$fixture_repository"
  git -C "$fixture_repository" "$@"
}

fixture_clone() {
  fixture_source=$1
  fixture_destination=$2
  fixture_parent=$(dirname -- "$fixture_destination")
  require_fixture_path "$fixture_parent"
  git clone -q "$fixture_source" "$fixture_destination"
}

if ! copier_available; then
  if [ "$require_copier" = "1" ]; then
    echo "copier CLI not found" >&2
    exit 127
  fi
  echo "copier CLI not found; skipped copier update test"
  echo "copier update test passed"
  exit 0
fi

mkdir -p "$tmp"
if ! command -v copier >/dev/null 2>&1; then
  mkdir -p "$tmp/bin" "$tmp/copier-project"
  cp "$root/pyproject.toml" "$root/uv.lock" "$tmp/copier-project/"
  cat >"$tmp/bin/copier" <<'EOF_COPIER_SHIM'
#!/bin/sh
shim_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
exec env \
  UV_CACHE_DIR="$shim_root/uv-cache" \
  UV_PROJECT_ENVIRONMENT="$shim_root/uv-venv" \
  uv run --locked --project "$shim_root/copier-project" copier "$@"
EOF_COPIER_SHIM
  chmod +x "$tmp/bin/copier"
  PATH="$tmp/bin:$PATH"
  export PATH
fi
earliest_ref=${COPIER_UPDATE_EARLIEST_REF:-v0.3.1}
oldest_ref=${COPIER_UPDATE_OLDEST_REF:-v0.4.1}
latest_ref=${COPIER_UPDATE_LATEST_REF:-v0.4.6}
target_commit=${COPIER_UPDATE_TARGET_REF:-HEAD}
update_source="$tmp/update-source"
fixture_clone "$root" "$update_source"
fixture_git "$update_source" fetch -q "$root" "$target_commit"
fixture_git "$update_source" switch -q -c migration-target FETCH_HEAD
fixture_git "$update_source" merge-base --is-ancestor v1.2.1 HEAD
copier_update_inventory="$root/tests/fixtures/orchestration/copier-update-source-inventory.txt"
# The inventory is the only source of the copied and staged paths, so every
# entry is checked against the repository it names before it is copied. A
# blank, duplicate, absolute, traversing, dot-segment, backslash, symlinked,
# missing, non-regular, or out-of-root entry stops the fixture instead of
# reaching the update source.
inventory_root=$(CDPATH= cd -- "$root" && pwd -P)
inventory_seen="$tmp/copier-update-inventory-seen"
: >"$inventory_seen"
while IFS= read -r candidate_path || [ -n "$candidate_path" ]; do
  case "$candidate_path" in
    ""|/*|.|..|./*|../*|*/./*|*/../*|*/.|*/..|*//*|*\\*)
      echo "invalid Copier update inventory path: $candidate_path" >&2
      exit 1
      ;;
  esac
  if grep -F -q -x -e "$candidate_path" "$inventory_seen"; then
    echo "duplicate Copier update inventory path: $candidate_path" >&2
    exit 1
  fi
  printf '%s\n' "$candidate_path" >>"$inventory_seen"
  if [ -L "$root/$candidate_path" ]; then
    echo "symlinked Copier update inventory path: $candidate_path" >&2
    exit 1
  fi
  if [ ! -f "$root/$candidate_path" ]; then
    echo "missing Copier update inventory file: $candidate_path" >&2
    exit 1
  fi
  case "$candidate_path" in
    */*) candidate_expected="$inventory_root/${candidate_path%/*}" ;;
    *) candidate_expected="$inventory_root" ;;
  esac
  candidate_parent=$(CDPATH= cd -- "$(dirname -- "$root/$candidate_path")" && pwd -P)
  if [ "$candidate_parent" != "$candidate_expected" ]; then
    echo "out-of-root Copier update inventory path: $candidate_path" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$update_source/$candidate_path")"
  cp "$root/$candidate_path" "$update_source/$candidate_path"
  fixture_git "$update_source" add -- "$candidate_path"
done < "$copier_update_inventory"
fixture_git "$update_source" -c user.name=CI -c user.email=ci@example.invalid \
  commit --allow-empty -qm "Make Copier updates fail closed"
fixture_git "$update_source" tag v1.2.2
fixture_git "$update_source" -c user.name=CI -c user.email=ci@example.invalid \
  commit --allow-empty -qm "Create v1.3.1 template identity"
fixture_git "$update_source" tag v1.3.1
target_ref=v1.3.1
fixture_git "$update_source" -c user.email=ci@example.invalid -c user.name=CI \
  commit --allow-empty -qm "Create v1.4.2 migration boundary"
fixture_git "$update_source" tag -f v1.4.2

direct_push_update_out="$tmp/direct-push-to-patch-only"
run_copier copy -q -f --trust --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/typescript.answers.yml" "$update_source" "$direct_push_update_out" >/dev/null
fixture_git "$direct_push_update_out" init -b main >/dev/null
fixture_git "$direct_push_update_out" config user.email "ci@example.invalid"
fixture_git "$direct_push_update_out" config user.name "CI"
printf 'project-owned direct-push update marker\n' >"$direct_push_update_out/project-owned.txt"
fixture_git "$direct_push_update_out" add -A
fixture_git "$direct_push_update_out" commit -qm "Create earlier direct-push project"
run_copier update -q --trust --defaults --vcs-ref v1.3.1 "$direct_push_update_out" >/dev/null
grep -q '^ci_autofix_mode: direct_push$' "$direct_push_update_out/.copier-answers.yml"
grep -q 'let mode = "patch-only";' "$direct_push_update_out/.github/workflows/codex-ci-autofix.yml"
if grep -q 'direct-push\|max_attempts\|validate-patch\|apply-patch\|git push\|createComment\|git commit' \
  "$direct_push_update_out/.github/workflows/codex-ci-autofix.yml"; then
  echo "Copier update retained the old direct-push CI autofix graph" >&2
  exit 1
fi
grep -q 'project-owned direct-push update marker' "$direct_push_update_out/project-owned.txt"
if find "$direct_push_update_out" -name '*.rej' -print -quit | grep -q .; then
  echo "direct-push Copier update produced rejection files" >&2
  exit 1
fi
if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$direct_push_update_out" --exclude-dir=.git >/dev/null; then
  echo "direct-push Copier update produced inline conflict markers" >&2
  exit 1
fi
direct_push_deletions=$(fixture_git "$direct_push_update_out" diff --diff-filter=D --name-only)
if [ -n "$direct_push_deletions" ]; then
  echo "direct-push Copier update produced unrelated tracked deletions: $direct_push_deletions" >&2
  exit 1
fi
fixture_git "$direct_push_update_out" diff --check

broad_out="$tmp/task-scoped-default-policy"
run_copier copy -q -f --trust --defaults --vcs-ref v1.3.0 \
  --data-file "$root/tests/fixtures/broad.answers.yml" "$update_source" "$broad_out" >/dev/null
grep -q '^version: 2$' "$broad_out/docs/agent/external-services.yaml"
grep -q '^access_profile: task_scoped_default_allow$' "$broad_out/docs/agent/external-services.yaml"
fixture_git "$broad_out" init -b main >/dev/null
fixture_git "$broad_out" config user.email "ci@example.invalid"
fixture_git "$broad_out" config user.name "CI"
printf '\n# project-owned version 2 policy marker\n' >>"$broad_out/docs/agent/external-services.yaml"
printf 'project-owned version 2 marker\n' >"$broad_out/project-owned-v2.txt"
fixture_git "$broad_out" add -A
fixture_git "$broad_out" commit -m "Initial version 2 generated workflow" >/dev/null
broad_policy_before="$tmp/task-scoped-default-policy-before.yaml"
cp "$broad_out/docs/agent/external-services.yaml" "$broad_policy_before"
run_copier update -q --trust --defaults --vcs-ref v1.3.1 "$broad_out" >/dev/null
if ! cmp -s "$broad_policy_before" "$broad_out/docs/agent/external-services.yaml"; then
  echo "Copier update changed project-owned version 2 external-service policy bytes" >&2
  exit 1
fi
(cd "$broad_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
test -f "$broad_out/.project-agent-workflow/skills/mcp-ops/references/provider-call-execution-context.md"
grep -q 'Bind provider authentication to each exact call' "$broad_out/.project-agent-workflow/skills/mcp-ops/agents/openai.yaml"
grep -q 'project-owned version 2 marker' "$broad_out/project-owned-v2.txt"
if find "$broad_out" -name '*.rej' -print -quit | grep -q .; then
  echo "version 2 Copier update produced rejection files" >&2
  exit 1
fi
if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$broad_out" --exclude-dir=.git >/dev/null; then
  echo "version 2 Copier update produced inline conflict markers" >&2
  exit 1
fi
broad_deletions=$(fixture_git "$broad_out" diff --diff-filter=D --name-only)
if [ -n "$broad_deletions" ]; then
  echo "version 2 Copier update produced unrelated tracked deletions: $broad_deletions" >&2
  exit 1
fi
fixture_git "$broad_out" diff --check

browser_legacy_out="$tmp/browser-run-legacy-policy"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$browser_legacy_out" >/dev/null
fixture_git "$browser_legacy_out" init -b main >/dev/null
fixture_git "$browser_legacy_out" config user.email "ci@example.invalid"
fixture_git "$browser_legacy_out" config user.name "CI"
fixture_git "$browser_legacy_out" add -A
fixture_git "$browser_legacy_out" commit -m "Initial older generated workflow" >/dev/null
if grep -q '^  browser_run:$' "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "older Browser Run fixture unexpectedly contains browser_run" >&2
  exit 1
fi
if grep -q '^_src_path: ../update-source$' "$browser_legacy_out/.copier-answers.yml"; then
  echo "ordinary update fixture unexpectedly uses the helper-only source relationship" >&2
  exit 1
fi
direct_verification_target="$tmp/direct-v1-target"
fixture_clone "$browser_legacy_out" "$direct_verification_target"
fixture_git "$direct_verification_target" config user.email "ci@example.invalid"
fixture_git "$direct_verification_target" config user.name "CI"
sed -i 's|^_src_path:.*$|_src_path: ../update-source|' \
  "$direct_verification_target/.copier-answers.yml"
grep -q '^_src_path: ../update-source$' \
  "$direct_verification_target/.copier-answers.yml"
fixture_git "$direct_verification_target" add .copier-answers.yml
fixture_git "$direct_verification_target" commit -m "Use isolated verification source" >/dev/null
direct_verification_out="$tmp/direct-v1-verification"
if ! python3 "$root/.codex/skills/verify-copier-update/scripts/verify-copier-update.py" \
    --target "$direct_verification_target" \
    --source "$update_source" \
    --source-ref "$target_ref" \
    --output-dir "$direct_verification_out" \
    --trust-template-tasks \
    --validation-command-json \
    '["python3","-c","from pathlib import Path; assert Path(\"README.md\").is_file(); assert Path(\".agents/skills/verify-copier-update/SKILL.md\").is_file()"]' \
    >/dev/null; then
  cat "$direct_verification_out/verification-manifest.json" >&2
  for diagnostic_log in "$direct_verification_out"/logs/*.stderr; do
    [ -s "$diagnostic_log" ] || continue
    printf '%s\n' "--- $(basename -- "$diagnostic_log")" >&2
    cat "$diagnostic_log" >&2
  done
  exit 1
fi
grep -q '"result": "verified"' "$direct_verification_out/verification-manifest.json"
grep -q '"update_path": "direct_supported_v1"' "$direct_verification_out/verification-manifest.json"
browser_legacy_policy_before="$tmp/browser-run-legacy-policy-before.yaml"
cp "$browser_legacy_out/docs/agent/external-services.yaml" "$browser_legacy_policy_before"
run_copier update -q --trust --defaults --vcs-ref "$target_ref" "$browser_legacy_out" >/dev/null
if ! cmp -s "$browser_legacy_policy_before" "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "Copier update changed project-owned older external-service policy bytes" >&2
  exit 1
fi
if grep -q '^  browser_run:$' "$browser_legacy_out/docs/agent/external-services.yaml"; then
  echo "Copier update rewrote project-owned older external-service policy" >&2
  exit 1
fi
(cd "$browser_legacy_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
test -f "$browser_legacy_out/.agents/skills/browser-ops/SKILL.md"
test -f "$browser_legacy_out/.project-agent-workflow/skills/browser-ops/references/browser-run-policy.md"
test -f "$browser_legacy_out/.project-agent-workflow/skills/mcp-ops/references/provider-call-execution-context.md"
test -f "$browser_legacy_out/.agents/skills/verify-copier-update/SKILL.md"
test -f "$browser_legacy_out/.project-agent-workflow/skills/verify-copier-update/SKILL.md"
test -x "$browser_legacy_out/.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py"
fixture_git "$browser_legacy_out" diff --check

validator="$root/scripts/validate-copier-update.py"

initial_copy="$tmp/non-git-initial-copy"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$initial_copy" >/dev/null
python3 "$validator" --destination "$initial_copy" >/dev/null
test -x "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh"
cmp "$validator" "$initial_copy/.project-agent-workflow/scripts/validate-copier-update.py"
sed -i 's/^external_access_profile: restricted$/external_access_profile: task_scoped_default_allow/' \
  "$initial_copy/.copier-answers.yml"
if python3 "$validator" --destination "$initial_copy" >/dev/null 2>&1; then
  echo "Copier validator accepted a task-scoped answer with a preserved version 1 policy" >&2
  exit 1
fi
initial_policy="$initial_copy/docs/agent/external-services.yaml"
initial_policy_backup="$tmp/non-git-initial-policy.yaml"
cp "$initial_policy" "$initial_policy_backup"
printf '%s\n' 'version: 2' 'access_profile: task_scoped_default_allow' >"$initial_policy"
if python3 "$validator" --destination "$initial_copy" >/dev/null 2>&1; then
  echo "Copier validator accepted an incomplete version 2 external-service policy" >&2
  exit 1
fi
cp "$initial_policy_backup" "$initial_policy"
sed -i 's/^external_access_profile: task_scoped_default_allow$/external_access_profile: restricted/' \
  "$initial_copy/.copier-answers.yml"
python3 "$validator" --destination "$initial_copy" >/dev/null
if "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh" -f >/dev/null 2>&1; then
  echo "Copier update wrapper accepted -f" >&2
  exit 1
fi
if "$initial_copy/.project-agent-workflow/scripts/update-from-copier.sh" --force >/dev/null 2>&1; then
  echo "Copier update wrapper accepted --force" >&2
  exit 1
fi

validator_out="$tmp/validator-fixture"
mkdir -p \
  "$validator_out/.github/workflows" \
  "$validator_out/.project-agent-workflow" \
  "$validator_out/scripts"
fixture_git "$validator_out" init -b main >/dev/null
fixture_git "$validator_out" config user.email "ci@example.invalid"
fixture_git "$validator_out" config user.name "CI"
cat >"$validator_out/.gitignore" <<'EOF_VALIDATOR_IGNORE'
*.rej
EOF_VALIDATOR_IGNORE
cp "$root/template/.project-agent-workflow/ownership.yaml" \
  "$validator_out/.project-agent-workflow/ownership.yaml"
printf 'baseline\n' >"$validator_out/product.txt"
printf 'optional workflow\n' >"$validator_out/.github/workflows/codex-ci-autofix.yml"
printf 'optional helper\n' >"$validator_out/scripts/skillspector-scan.sh"
fixture_git "$validator_out" add -A
fixture_git "$validator_out" commit -m "Create validator fixture" >/dev/null

printf 'ignored rejection\n' >"$validator_out/ignored-result.rej"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an ignored rejection file" >&2
  exit 1
fi
rm -f "$validator_out/ignored-result.rej"

printf '%s\n' \
  '<<<<<<< project' \
  'project value' \
  '=======' \
  'template value' \
  '>>>>>>> template' >"$validator_out/conflicted.txt"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a complete conflict block" >&2
  exit 1
fi
rm -f "$validator_out/conflicted.txt"

printf '<<<<<<< incomplete marker only\n' >"$tmp/symlink-conflict-target"
ln -s "$tmp/symlink-conflict-target" "$validator_out/linked-result.rej"
python3 "$validator" --destination "$validator_out" >/dev/null

printf 'unexpected product addition\n' >"$validator_out/untracked-product.txt"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an untracked unclassified path" >&2
  exit 1
fi
rm -f "$validator_out/untracked-product.txt"

mkdir -p "$validator_out/.project-agent-workflow/new-managed"
printf 'managed addition\n' >"$validator_out/.project-agent-workflow/new-managed/result.txt"
python3 "$validator" --destination "$validator_out" >/dev/null
rm -rf "$validator_out/.project-agent-workflow/new-managed"

sed -i '/^seeded_project_owned:/i\  - untracked-product.txt' \
  "$validator_out/.project-agent-workflow/ownership.yaml"
printf 'self-authorized addition\n' >"$validator_out/untracked-product.txt"
if tampered_inventory_error=$(python3 "$validator" --destination "$validator_out" 2>&1); then
  echo "Copier update validator accepted a broadened current ownership inventory" >&2
  exit 1
fi
case "$tampered_inventory_error" in
  *"differs from the inventory shipped with this validator"*) ;;
  *)
    echo "Copier update validator reported an unexpected inventory failure" >&2
    printf '%s\n' "$tampered_inventory_error" >&2
    exit 1
    ;;
esac
fixture_git "$validator_out" restore .project-agent-workflow/ownership.yaml
rm -f "$validator_out/untracked-product.txt"

mkdir -p "$validator_out/.project-agent-workflow/loader-probe"
printf 'loader probe\n' >"$validator_out/.project-agent-workflow/loader-probe/result.txt"
inventory_path="$validator_out/.project-agent-workflow/ownership.yaml"
inventory_hardlink="$tmp/ownership-hardlink.yaml"
ln "$inventory_path" "$inventory_hardlink"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a hard-linked current ownership inventory" >&2
  exit 1
fi
rm -f "$inventory_hardlink"
python3 "$validator" --destination "$validator_out" >/dev/null

inventory_original="$tmp/ownership-original.yaml"
mv "$inventory_path" "$inventory_original"
ln -s "$inventory_original" "$inventory_path"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a symlinked current ownership inventory" >&2
  exit 1
fi
rm -f "$inventory_path"
mv "$inventory_original" "$inventory_path"

VALIDATOR_PATH="$validator" VALIDATOR_DESTINATION="$validator_out" python3 - <<'PY'
import importlib.util
import os
from pathlib import Path
from unittest import mock

validator_path = Path(os.environ["VALIDATOR_PATH"])
destination = Path(os.environ["VALIDATOR_DESTINATION"])
spec = importlib.util.spec_from_file_location("copier_update_validator", validator_path)
if spec is None or spec.loader is None:
    raise SystemExit("could not load Copier update validator")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
inventory = destination / validator.OWNERSHIP_PATH
original_read = validator.os.read
changed = False

def read_then_change(descriptor, size):
    global changed
    data = original_read(descriptor, size)
    if data and not changed:
        changed = True
        metadata = inventory.stat()
        os.utime(
            inventory,
            ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000),
        )
    return data

with mock.patch.object(validator.os, "read", side_effect=read_then_change):
    try:
        validator.load_current_ownership_inventory(destination)
    except validator.UpdateValidationError as exc:
        if "changed while it was read" not in str(exc):
            raise
    else:
        raise SystemExit("Copier update validator accepted inventory changed during reading")
PY
rm -rf "$validator_out/.project-agent-workflow/loader-probe"

rm -f "$validator_out/.github/workflows/codex-ci-autofix.yml" "$validator_out/scripts/skillspector-scan.sh"
python3 "$validator" --destination "$validator_out" >/dev/null
rm -f "$validator_out/product.txt"
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an unclassified tracked deletion" >&2
  exit 1
fi
fixture_git "$validator_out" checkout -q -- product.txt .github/workflows/codex-ci-autofix.yml scripts/skillspector-scan.sh

base_blob=$(fixture_git "$validator_out" rev-parse HEAD:product.txt)
ours_blob=$(printf 'project value\n' | fixture_git "$validator_out" hash-object -w --stdin)
theirs_blob=$(printf 'template value\n' | fixture_git "$validator_out" hash-object -w --stdin)
{
  printf '100644 %s 1\tproduct.txt\n' "$base_blob"
  printf '100644 %s 2\tproduct.txt\n' "$ours_blob"
  printf '100644 %s 3\tproduct.txt\n' "$theirs_blob"
} | fixture_git "$validator_out" update-index --index-info
if python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted an unmerged index" >&2
  exit 1
fi
fixture_git "$validator_out" reset -q --hard HEAD

real_git=$(command -v git)
mkdir -p "$tmp/failing-git"
cat >"$tmp/failing-git/git" <<EOF_FAILING_GIT
#!/bin/sh
if [ "\${LC_ALL:-}" != C ] || [ "\${LANG:-}" != C ]; then
  echo "Git inspection did not use the C locale" >&2
  exit 9
fi
if [ "\${3:-}" = rev-parse ]; then
  exec "$real_git" "\$@"
fi
echo "simulated Git inspection failure" >&2
exit 7
EOF_FAILING_GIT
chmod +x "$tmp/failing-git/git"
if PATH="$tmp/failing-git:$PATH" python3 "$validator" --destination "$validator_out" >/dev/null 2>&1; then
  echo "Copier update validator accepted a Git inspection failure" >&2
  exit 1
fi

boundary_clean="$tmp/v121-to-v122-clean"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$boundary_clean" >/dev/null
fixture_git "$boundary_clean" init -b main >/dev/null
fixture_git "$boundary_clean" config user.email "ci@example.invalid"
fixture_git "$boundary_clean" config user.name "CI"
fixture_git "$boundary_clean" add -A
fixture_git "$boundary_clean" commit -m "Create v1.2.1 boundary fixture" >/dev/null
run_copier update -q --trust --defaults --vcs-ref v1.2.2 "$boundary_clean" >/dev/null
grep -q '^_commit: v1.2.2$' "$boundary_clean/.copier-answers.yml"
test -x "$boundary_clean/.project-agent-workflow/scripts/update-from-copier.sh"
python3 "$validator" --destination "$boundary_clean" >/dev/null

boundary_conflict="$tmp/v121-to-v122-conflict"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$boundary_conflict" >/dev/null
fixture_git "$boundary_conflict" init -b main >/dev/null
fixture_git "$boundary_conflict" config user.email "ci@example.invalid"
fixture_git "$boundary_conflict" config user.name "CI"
fixture_git "$boundary_conflict" add -A
fixture_git "$boundary_conflict" commit -m "Create conflicting v1.2.1 boundary fixture" >/dev/null
sed -i 's|2\. Run `copier update --trust` without force-overwriting local conflicts\.|2. Run the project-specific update command without replacing this line.|' \
  "$boundary_conflict/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'project-specific update command' "$boundary_conflict/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md"
fixture_git "$boundary_conflict" add .project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
fixture_git "$boundary_conflict" commit -m "Customize the update instruction" >/dev/null
if run_copier update -q --trust --defaults --vcs-ref v1.2.2 "$boundary_conflict" >/dev/null 2>&1; then
  echo "v1.2.2 after migration accepted a same-line merge conflict" >&2
  exit 1
fi
if ! fixture_git "$boundary_conflict" ls-files -u | grep -q .; then
  echo "v1.2.1-to-v1.2.2 fixture did not create a real index conflict" >&2
  exit 1
fi

worker_contract_out="$tmp/v121-to-v142-worker-contract"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$worker_contract_out" >/dev/null
fixture_git "$worker_contract_out" init -b main >/dev/null
fixture_git "$worker_contract_out" config user.email "ci@example.invalid"
fixture_git "$worker_contract_out" config user.name "CI"
printf '\nProject-owned v1.2.1 policy marker.\n' >>"$worker_contract_out/AGENTS.md"
fixture_git "$worker_contract_out" add -A
fixture_git "$worker_contract_out" commit -m "Create customized v1.2.1 worker fixture" >/dev/null
worker_contract_agents_before=$(fixture_git "$worker_contract_out" hash-object AGENTS.md)
grep -q '^sandbox_mode = "workspace-write"$' \
  "$worker_contract_out/.codex/agents/sequential_plan_worker.toml"
run_copier update -q --trust --defaults --vcs-ref v1.4.2 "$worker_contract_out" >/dev/null
if ! grep -q '^_commit: v1.4.2$' "$worker_contract_out/.copier-answers.yml"; then
  echo "v1.2.1-to-v1.4.2 fixture recorded an unexpected Copier source revision" >&2
  sed -n '1,12p' "$worker_contract_out/.copier-answers.yml" >&2
  exit 1
fi
cmp "$root/template/.codex/agents/sequential_plan_worker.toml" \
  "$worker_contract_out/.codex/agents/sequential_plan_worker.toml"
test "$worker_contract_agents_before" = "$(fixture_git "$worker_contract_out" hash-object AGENTS.md)"
printf '\nUnexpected update overwrite.\n' >>"$worker_contract_out/AGENTS.md"
if python3 "$validator" --destination "$worker_contract_out" >/dev/null 2>&1; then
  echo "v1.4.2 validator accepted a project-owned AGENTS.md overwrite" >&2
  exit 1
fi
fixture_git "$worker_contract_out" restore AGENTS.md

wrapper_self_update_out="$tmp/v141-to-current-wrapper-self-update"
wrapper_self_update_cwd="$tmp/v141-wrapper-outside-cwd"
mkdir -p "$wrapper_self_update_cwd"
run_copier copy -q -f --trust --defaults --vcs-ref v1.4.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$wrapper_self_update_out" >/dev/null
fixture_git "$wrapper_self_update_out" init -b main >/dev/null
fixture_git "$wrapper_self_update_out" config user.email "ci@example.invalid"
fixture_git "$wrapper_self_update_out" config user.name "CI"
printf '%s\n' \
  'version: 1' \
  'enabled: true' \
  'merge_target_refs:' \
  '  - refs/heads/integration' \
  'protected_local_branch_refs:' \
  '  - refs/heads/main' \
  '  - refs/heads/integration' \
  >"$wrapper_self_update_out/docs/agent/git-retirement.yaml"
retirement_config_before="$tmp/v141-git-retirement-before.yaml"
cp "$wrapper_self_update_out/docs/agent/git-retirement.yaml" "$retirement_config_before"
fixture_git "$wrapper_self_update_out" add -A
fixture_git "$wrapper_self_update_out" commit -m "Create v1.4.1 wrapper self-update fixture" >/dev/null
if ! (cd "$wrapper_self_update_cwd" && \
  "$wrapper_self_update_out/.project-agent-workflow/scripts/update-from-copier.sh" \
    --defaults --vcs-ref "$target_commit" >/dev/null); then
  echo "v1.4.1 wrapper did not survive replacing itself during update" >&2
  exit 1
fi
if ! cmp -s "$retirement_config_before" "$wrapper_self_update_out/docs/agent/git-retirement.yaml"; then
  echo "Copier update changed project-owned Git-retirement configuration bytes" >&2
  exit 1
fi
test -f "$wrapper_self_update_out/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md"
test -x "$wrapper_self_update_out/.project-agent-workflow/scripts/retire-merged-worktrees.py"
grep -q -- '--destination . --before-update' \
  "$wrapper_self_update_out/.project-agent-workflow/scripts/run-copier-update.sh"
if (cd "$wrapper_self_update_out" && \
  .project-agent-workflow/scripts/run-copier-update.sh --force >/dev/null 2>&1); then
  echo "Copier update helper accepted --force" >&2
  exit 1
fi
if (cd "$wrapper_self_update_out" && \
  .project-agent-workflow/scripts/run-copier-update.sh -f >/dev/null 2>&1); then
  echo "Copier update helper accepted -f" >&2
  exit 1
fi
fixture_git "$wrapper_self_update_out" add -A
fixture_git "$wrapper_self_update_out" commit -m "Accept current update wrapper" >/dev/null

sed -i '/main() {/a\  : future-helper-byte-shift' \
  "$update_source/template/.project-agent-workflow/scripts/run-copier-update.sh"
fixture_git "$update_source" add template/.project-agent-workflow/scripts/run-copier-update.sh
fixture_git "$update_source" -c user.name=CI -c user.email=ci@example.invalid \
  commit -qm "Create future helper replacement fixture"
future_helper_ref=$(fixture_git "$update_source" rev-parse HEAD)
if ! (cd "$wrapper_self_update_cwd" && \
  "$wrapper_self_update_out/.project-agent-workflow/scripts/update-from-copier.sh" \
    --defaults --vcs-ref "$future_helper_ref" >/dev/null); then
  echo "current Copier update helper did not survive replacing itself" >&2
  exit 1
fi
grep -q 'future-helper-byte-shift' \
  "$wrapper_self_update_out/.project-agent-workflow/scripts/run-copier-update.sh"

custom_worker_out="$tmp/v121-to-v142-custom-worker"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.1 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$update_source" "$custom_worker_out" >/dev/null
fixture_git "$custom_worker_out" init -b main >/dev/null
fixture_git "$custom_worker_out" config user.email "ci@example.invalid"
fixture_git "$custom_worker_out" config user.name "CI"
sed -i 's/Read the assigned plan and its required specs before editing\./Preserve this project-owned worker instruction./' \
  "$custom_worker_out/.codex/agents/sequential_plan_worker.toml"
fixture_git "$custom_worker_out" add -A
fixture_git "$custom_worker_out" commit -m "Customize the legacy worker contract" >/dev/null
if run_copier update -q --trust --defaults --vcs-ref v1.4.2 "$custom_worker_out" >/dev/null 2>&1; then
  echo "v1.4.2 worker migration overwrote a customized workspace-write profile" >&2
  exit 1
fi
grep -q 'Preserve this project-owned worker instruction.' \
  "$custom_worker_out/.codex/agents/sequential_plan_worker.toml"
grep -q '^sandbox_mode = "workspace-write"$' \
  "$custom_worker_out/.codex/agents/sequential_plan_worker.toml"

legacy_answers="$tmp/legacy-activation.answers.yml"
cat >"$legacy_answers" <<'EOF'
project_name: typescript-app
project_slug: typescript-app
project_purpose: Build a TypeScript application.
primary_language: typescript
use_hooks: true
use_skillspector: true
use_mcp_policy: true
use_linear_sync: true
use_graph_memory: true
EOF

run_adoption() {
  destination=$1
  ref=$2
  shift 2
  if command -v uv >/dev/null 2>&1 && [ -f "$root/pyproject.toml" ]; then
    (cd "$root" && env \
      UV_CACHE_DIR="$tmp/adoption-uv-cache" \
      UV_PROJECT_ENVIRONMENT="$tmp/adoption-uv-venv" \
      uv run --locked --project "$root" python \
      "$root/scripts/adopt-to-namespaced-layout.py" \
      --destination "$destination" --vcs-ref "$ref" "$@")
  else
    copier_executable=$(command -v copier)
    python3 "$root/scripts/adopt-to-namespaced-layout.py" \
      --destination "$destination" --vcs-ref "$ref" \
      --copier-executable "$copier_executable" "$@"
  fi
}
legacy_disabled_answers="$tmp/legacy-disabled.answers.yml"
cat >"$legacy_disabled_answers" <<'EOF'
project_name: legacy-disabled
project_slug: legacy-disabled
project_purpose: Exercise disabled legacy activation answers.
primary_language: docs
use_hooks: false
use_skillspector: false
use_mcp_policy: false
use_linear_sync: false
use_graph_memory: false
EOF

prepare_lane() {
  lane=$1
  base_ref=$2
  answers=$3
  shift 3
  out="$tmp/$lane"
  run_copier copy -q -f --vcs-ref "$base_ref" --data-file "$answers" "$update_source" "$out" >/dev/null
  fixture_git "$out" init -b main >/dev/null
  fixture_git "$out" config user.email "ci@example.invalid"
  fixture_git "$out" config user.name "CI"
  fixture_git "$out" add -A
  fixture_git "$out" commit -m "Initial generated workflow" >/dev/null

  cat >"$out/docs/agent/SPEC_PRODUCT.md" <<'EOF'
# Product Notes

Local project-owned agent notes.
EOF
  cat >"$out/docs/agent/PROJECT_ENVIRONMENT.md" <<'EOF'
# Project Environment

Preserve this project-owned environment policy.
EOF
  cat >"$out/docs/agent/PROJECT_UI_DESIGN.md" <<'EOF'
# Project UI Design

Preserve this project-owned UI policy.
EOF
  fixture_git "$out" add docs/agent/SPEC_PRODUCT.md docs/agent/PROJECT_ENVIRONMENT.md docs/agent/PROJECT_UI_DESIGN.md
  fixture_git "$out" commit -m "Add local project notes" >/dev/null
  if [ "$lane" = "earliest-supported" ]; then
    # Only this lane dispatches a Copier update, and it always updates the
    # `earliest-supported` project. The destination is therefore written as
    # that one anchored path so the dispatch names a readable project instead
    # of an unresolved lane parameter.
    [ "$out" = "$tmp/earliest-supported" ]
    status_before=$(fixture_git "$out" status --porcelain=v1)
    if run_copier update -q -f --trust --vcs-ref "$target_ref" "$tmp/earliest-supported" >/dev/null 2>&1; then
      echo "direct pre-v1 copier update unexpectedly succeeded" >&2
      exit 1
    fi
    status_after=$(fixture_git "$out" status --porcelain=v1)
    [ "$status_after" = "$status_before" ]
    test ! -e "$out/.project-agent-workflow"
    test ! -e "$out/.project-agent-workflow-migration"
  fi
  run_adoption "$out" "$target_ref" "$@" >/dev/null
  printf '%s\n' "$out"
}

# The update fills only the agent model fields a project has not declared, so a
# lane that already holds a value asserts that exact value instead of the seed.
# Each entry is "profile:model:effort" and "-" keeps the seeded default.
agent_profile_expectations=""

seeded_agent_profile_model() {
  case "$1" in
    change_reviewer) echo gpt-5.6-sol ;;
    docs_researcher|evidence_synthesizer|repo_explorer) echo gpt-5.6-luna ;;
    scoped_worker) echo gpt-5.6-terra ;;
    fast_scoped_worker|sequential_plan_worker) echo gpt-5.3-codex-spark ;;
  esac
}

seeded_agent_profile_effort() {
  case "$1" in
    change_reviewer) echo high ;;
    evidence_synthesizer) echo xhigh ;;
    repo_explorer) echo low ;;
    docs_researcher|scoped_worker|fast_scoped_worker|sequential_plan_worker) echo medium ;;
  esac
}

expected_agent_profile_field() {
  expectation_profile=$1
  expectation_field=$2
  for expectation in $agent_profile_expectations; do
    case "$expectation" in
      "$expectation_profile":*) ;;
      *) continue ;;
    esac
    expectation_rest=${expectation#*:}
    case "$expectation_field" in
      model) expectation_value=${expectation_rest%%:*} ;;
      *) expectation_value=${expectation_rest#*:} ;;
    esac
    if [ "$expectation_value" != "-" ]; then
      printf '%s\n' "$expectation_value"
      return 0
    fi
    break
  done
  case "$expectation_field" in
    model) seeded_agent_profile_model "$expectation_profile" ;;
    *) seeded_agent_profile_effort "$expectation_profile" ;;
  esac
}

assert_agent_profiles() {
  out=$1
  for profile in change_reviewer docs_researcher evidence_synthesizer repo_explorer \
    scoped_worker fast_scoped_worker sequential_plan_worker
  do
    profile_file="$out/.codex/agents/$profile.toml"
    grep -qE "^[[:space:]]*model = \"$(expected_agent_profile_field "$profile" model)\"$" "$profile_file"
    grep -qE "^[[:space:]]*model_reasoning_effort = \"$(expected_agent_profile_field "$profile" effort)\"$" "$profile_file"
  done
}

assert_managed_orchestration_reports() {
  test -f "$managed_agents"
  test -f "$managed_orchestration"
  grep -Eqi 'without waiting for per-task user instruction|without requiring a per-task user instruction' "$managed_agents" "$managed_orchestration"
  grep -qi 'final ownership' "$managed_agents"
  grep -q 'final high-risk' "$managed_agents" "$managed_orchestration"
  grep -q 'authorization decisions' "$managed_agents" "$managed_orchestration"
  grep -q 'external writes' "$managed_agents" "$managed_orchestration"
  grep -q 'main session' "$managed_agents" "$managed_orchestration"
  grep -Eqi 'final report transparency is mandatory|final report must state whether helpers were used' "$managed_agents" "$managed_orchestration"
  grep -qi 'helpers were used' "$managed_agents" "$managed_orchestration"
  grep -qi 'context files read-only' "$managed_orchestration" "$managed_agents"
  test -f "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  test -f "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  test -f "$out/.project-agent-workflow/scripts/planlib.py"
  grep -q 'run-sandboxed-plan-worker.py' "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'sequential_plan_worker' "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'The main agent owns task interpretation, integration, validation acceptance, planning updates, commits, and the final report.' "$managed_orchestration"
  grep -q '^DEFAULT_CODEX_MODEL = "gpt-5.3-codex-spark"$' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q '^DEFAULT_FALLBACK_CODEX_MODEL = "gpt-5.6-luna"$' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q '^TERRA_CODEX_MODEL = "gpt-5.6-terra"$' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def select_plan_writable_profile' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def open_availability_state' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q -- '--availability-state' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'skipped_known_unavailable_starts' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def correct_worker' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'correction_lineage' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def validate_candidate' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def open_lifecycle_state' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q -- '--lifecycle-state' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'VALIDATION_AUTHORITY_SCOPE' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'network_enabled=False' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'WORKER_CONTRACT_SCHEMA_VERSION' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def derive_worker_contract' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def verify_worker_contract' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'WORKER_COMPLETION_RECEIPT_SCHEMA_VERSION' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def validate_worker_completion_receipt' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def write_attempt_completion_receipt' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def write_attempt_process_result' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def derive_repository_identity' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'def begin_plan_execution_attempt' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q -- '--predecessor-plan-execution-state' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'REVIEW_REASON_CODES' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'def record_writable_attempt_start' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'def record_attempt_close' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'diagnosis_required' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'def load_authoritative_failure' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'def load_diagnosis_evidence' "$out/.project-agent-workflow/scripts/plan-execution-state.py"
  grep -q 'def validation_failure_identity' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'worker_attempt_label' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'NEW_FILE_ROOT' "$out/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py"
  grep -q 'implementation_risk' "$out/.project-agent-workflow/scripts/planlib.py"
  grep -q 'implementation_ambiguity' "$out/.project-agent-workflow/scripts/planlib.py"
  grep -q 'focused_validation' "$out/.project-agent-workflow/scripts/planlib.py"
  grep -q 'validation_authority_scope' "$out/.project-agent-workflow/scripts/planlib.py"
  grep -qi 'repository breadth alone is insufficient' "$managed_agents" "$managed_orchestration"
  grep -qi 'admissible implementation slice' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -qi 'state path outside the repository' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'run-sandboxed-plan-worker.py correct' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'run-sandboxed-plan-worker.py validate' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -qi 'worker completion receipt' "$managed_agents" "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'primary_invariant' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'exact file paths' "$managed_orchestration" "$out/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md"
  grep -q 'predecessor_acceptance' "$managed_orchestration"
  grep -q 'writable_attempt_started' "$managed_orchestration"
  grep -q 'attempt_closed' "$managed_orchestration"
  grep -q 'successor_claimed' "$managed_orchestration"
  grep -q 'review_evidence_digest' "$managed_orchestration"
  grep -q 'global task lock' "$managed_orchestration"
  grep -q 'def has_pre_v1_adoption_provenance()' "$out/.project-agent-workflow/scripts/planlib.py"
}

# The managed entrypoint routes to the guardian rule instead of repeating it,
# so every update must publish the short route, keep the whole rule in its
# normative destination, and leave the project's own entrypoint untouched.
assert_managed_policy_routing() {
  entrypoint=$1
  destination=$2
  index=$3
  # Fragment checks accept a route that drops its own obligation, so the
  # rendered route and the rendered guardian statement are compared against the
  # exact reviewed bytes that the root checker pins by digest.
  PYTHONDONTWRITEBYTECODE=1 python3 - "$entrypoint" "$destination" "$index" "$root" <<'EOF_MANAGED_ROUTING'
import hashlib
import importlib.util
import sys
from pathlib import Path

entrypoint, destination, index, root = (Path(value) for value in sys.argv[1:5])
spec = importlib.util.spec_from_file_location(
    "managed_routing_policy", root / "scripts/check-root-agent-policy.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

marker = policy.VALIDATION_WITNESS_MIGRATION_MARKER
route_marker = policy.VALIDATION_WITNESS_MIGRATION_ROUTE_MARKER
generated_destination = policy.VALIDATION_WITNESS_MIGRATION_ROUTE_DESTINATIONS[
    "template/.project-agent-workflow/AGENTS.md.jinja"
]

entrypoint_text = entrypoint.read_text(encoding="utf-8")
if marker in entrypoint_text:
    raise SystemExit(f"managed entrypoint restates the relocated guardian rule: {entrypoint}")

routes = [line.strip() for line in entrypoint_text.splitlines() if route_marker in line.lower()]
if len(routes) != 1:
    raise SystemExit(f"managed entrypoint needs exactly one guardian route: {entrypoint}")
route = routes[0]
if len(route.encode("utf-8")) > policy.VALIDATION_WITNESS_MIGRATION_ROUTE_MAX_BYTES:
    raise SystemExit(f"managed entrypoint guardian route is too long: {entrypoint}")
if generated_destination not in route:
    raise SystemExit(f"managed entrypoint guardian route does not name its destination: {entrypoint}")
normalized = route.replace(generated_destination, "<destination>")
if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != (
    policy.VALIDATION_WITNESS_MIGRATION_ROUTE_SHA256
):
    raise SystemExit(f"managed entrypoint guardian route is not the reviewed route: {entrypoint}")

statements = [
    line.strip()
    for line in destination.read_text(encoding="utf-8").splitlines()
    if marker in line
]
if len(statements) != 1:
    raise SystemExit(f"managed destination needs exactly one guardian rule: {destination}")
lowered = statements[0].lower()
for required in policy.VALIDATION_WITNESS_MIGRATION_POLICY_MARKERS:
    if required not in lowered:
        raise SystemExit(f"managed destination is missing {required}: {destination}")
if hashlib.sha256(statements[0].encode("utf-8")).hexdigest() != (
    policy.VALIDATION_WITNESS_MIGRATION_POLICY_SHA256
):
    raise SystemExit(f"managed destination guardian rule is not the reviewed rule: {destination}")

if generated_destination not in index.read_text(encoding="utf-8"):
    raise SystemExit(f"generated index does not route to the guardian rule: {index}")
EOF_MANAGED_ROUTING
}

validate_common_lane() {
  out=$1
  expect_legacy_root=${2:-1}
  expected_ci_autofix=${3:-disabled}
  managed_agents="$out/.project-agent-workflow/AGENTS.md"
  managed_orchestration="$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"

  assert_managed_orchestration_reports
  assert_managed_policy_routing "$managed_agents" "$managed_orchestration" \
    "$out/.project-agent-workflow/docs/agent/spec-index.yaml"

  test -f "$root/tests/fixtures/orchestration/worker-contract-evidence.json"
  grep -q '"suite": "worker-execution-contract-integration"' "$root/tests/fixtures/orchestration/worker-contract-evidence.json"
  test -f "$root/tests/fixtures/orchestration/worker-completion-receipt-scenarios.json"
  grep -q '"suite": "worker-completion-receipt"' "$root/tests/fixtures/orchestration/worker-completion-receipt-scenarios.json"
  test -f "$root/tests/fixtures/orchestration/worker-completion-receipt-holdout.json"
  test -f "$root/tests/fixtures/orchestration/worker-completion-receipt-holdout-v2.json"
  test -f "$root/tests/fixtures/orchestration/worker-completion-receipt-evidence.json"

  test -f "$out/.copier-answers.yml"
  test -f "$out/.project-agent-workflow/AGENTS.md"
  test -f "$out/.project-agent-workflow/docs/agent/spec-index.yaml"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md"
  test -f "$out/.project-agent-workflow/human-report.json"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  test -f "$out/docs/agent/external-services.yaml"
  test -f "$out/docs/plan/README.md"
  test -f "$out/docs/plan/backlog/README.md"
  test -f "$out/docs/plan/handoffs/README.md"
  test -f "$out/docs/plan/sub-agents/custom-agents.md"
  test -f "$out/docs/agent/SPEC_PRODUCT.md"
  test -f "$out/.project-agent-workflow/docs/agent/SPEC_SECURITY.md"
  test -f "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  test -f "$out/docs/agent/PROJECT_UI_DESIGN.md"
  test -f "$out/.project-agent-workflow/scripts/workflow-status.sh"
  test -f "$out/.project-agent-workflow/scripts/human-report.py"
  test -f "$out/.project-agent-workflow/scripts/create-plan.sh"
  test -f "$out/.project-agent-workflow/scripts/select-task-context.sh"
  test -f "$out/.project-agent-workflow/scripts/clean-handoffs.sh"
  test -f "$out/.project-agent-workflow/scripts/lint-plan-docs.sh"
  test -f "$out/.project-agent-workflow/scripts/format-plan-docs.sh"
  test -f "$out/.project-agent-workflow/scripts/validate-changes.py"
  test -f "$out/.project-agent-workflow/scripts/security-static-check.py"
  test -f "$out/.project-agent-workflow/scripts/check-external-service-policy.py"
  test -f "$out/.project-agent-workflow/scripts/migrate-legacy-template-files.py"
  test -f "$out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
  if [ "$expect_legacy_root" = "1" ]; then
    test -f "$out/scripts/create-plan.sh"
  else
    test ! -f "$out/scripts/create-plan.sh"
  fi
  grep -q 'Local project-owned agent notes.' "$out/docs/agent/SPEC_PRODUCT.md"
  grep -q 'Preserve this project-owned environment policy.' "$out/docs/agent/PROJECT_ENVIRONMENT.md"
  grep -q 'Preserve this project-owned UI policy.' "$out/docs/agent/PROJECT_UI_DESIGN.md"
  grep -q 'Integration Checklist' "$out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
  grep -q "ci_autofix_mode: $expected_ci_autofix" "$out/.copier-answers.yml"
  grep -q 'human_report_mode: agent_select_local' "$out/.copier-answers.yml"
  grep -q '"mode": "agent_select_local"' "$out/.project-agent-workflow/human-report.json"
  grep -q 'human_report_shared_mode: disabled' "$out/.copier-answers.yml"
  test ! -e "$out/docs/human-report"
  grep -Fq "CI autofix mode: \`$expected_ci_autofix\`" "$out/.project-agent-workflow/AGENTS.md"
  if [ "$expected_ci_autofix" = "disabled" ]; then
    test ! -f "$out/.github/workflows/codex-ci-autofix.yml"
  else
    test -f "$out/.github/workflows/codex-ci-autofix.yml"
  fi
  test -f "$out/.codex/hooks/agent_log_event.py"
  grep -q 'Compatibility bridge' "$out/.codex/hooks/agent_log_event.py"
  if [ -f "$out/.codex/hooks.json" ]; then
    grep -q 'stop_review_gate.py' "$out/.codex/hooks.json"
  fi
  grep -q 'repository-wide' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'main agent owns' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'Do not delegate short deterministic commands' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'external writes' "$out/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
  grep -q 'project-agent-workflow:managed-core:start' "$out/AGENTS.md"
  if fixture_git "$out" ls-files -u | grep -q .; then
    echo "namespaced adoption left an unmerged index: $out" >&2
    exit 1
  fi
  fixture_git "$out" diff --diff-filter=D --name-only | while IFS= read -r path; do
    case "$path" in
      .github/workflows/codex-ci-autofix.yml|scripts/skillspector-scan.sh) ;;
      *)
        echo "namespaced adoption deleted project-owned or unclassified path: $out/$path" >&2
        exit 1
        ;;
    esac
  done

  if find "$out" -name '*.rej' -print -quit | grep -q .; then
    echo "copier update produced rejection files: $out" >&2
    exit 1
  fi
  if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$out" --exclude-dir=.git >/dev/null; then
    echo "copier update produced inline conflict markers: $out" >&2
    exit 1
  fi
  fixture_git "$out" diff --check
  (cd "$out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
  (cd "$out" && python3 .project-agent-workflow/scripts/format-plan-docs.py --check)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-codex-toml.py >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/structure-map.py --check >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/security-static-check.py --managed >/dev/null)
  (cd "$out" && python3 .project-agent-workflow/scripts/validate-changes.py --all >/dev/null)
  if (cd "$out" && HEADROOM_DISABLED=1 .project-agent-workflow/scripts/context-compress.sh .project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md namespaced-policy >/dev/null 2>&1); then
    echo "context-compress.sh accepted namespaced normative policy after adoption: $out" >&2
    exit 1
  fi
  test ! -e "$out/.agent-logs/namespaced-policy"
  python3 "$root/scripts/check-copier-template.py" --print-generated-required | while IFS= read -r path; do
    [ -n "$path" ] || continue
    test -f "$out/$path"
  done
  if [ ! -x "$out/.githooks/pre-commit" ]; then
    echo "updated project is missing an executable pre-commit hook: $out" >&2
    exit 1
  fi
  cmp "$root/template/.githooks/pre-commit" "$out/.githooks/pre-commit"
  cmp "$root/template/.github/hooks/plan-lifecycle.json" "$out/.github/hooks/plan-lifecycle.json"
  if [ -e "$out/.git" ] && [ -n "$(fixture_git "$out" config --local --get core.hooksPath || true)" ]; then
    echo "the update selected core.hooksPath in the project: $out" >&2
    exit 1
  fi
  assert_agent_profiles "$out"
}

earliest_out=$(prepare_lane earliest-supported "$earliest_ref" "$legacy_answers")
(cd "$earliest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="repo_explorer:-:medium"
validate_common_lane "$earliest_out"
agent_profile_expectations=""
grep -q 'Codex hooks mode: `install_templates`' "$earliest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$earliest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP=`documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear=`documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'graph memory=`documented`' "$earliest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$earliest_out/.project-agent-workflow/scripts/skillspector-scan.sh"

oldest_out=$(prepare_lane oldest-supported "$oldest_ref" "$legacy_answers")
(cd "$oldest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="repo_explorer:-:medium"
validate_common_lane "$oldest_out"
agent_profile_expectations=""
grep -q 'Codex hooks mode: `install_templates`' "$oldest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `document_optional`' "$oldest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP=`documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear=`documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'graph memory=`documented`' "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test -f "$oldest_out/.project-agent-workflow/scripts/skillspector-scan.sh"
test -f "$oldest_out/scripts/skillspector-scan.sh"
grep -q '.project-agent-workflow/scripts/skillspector-scan.sh' "$oldest_out/scripts/skillspector-scan.sh"
test -f "$oldest_out/.project-agent-workflow-migration/v1-pre-namespace/.github/workflows/codex-ci-autofix.yml"
grep -q 'retired_legacy_optional_paths' "$oldest_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
if grep -q 'use_hooks\|use_skillspector\|use_mcp_policy\|use_linear_sync\|use_graph_memory' "$oldest_out/.copier-answers.yml" "$oldest_out/.project-agent-workflow/AGENTS.md" "$oldest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"; then
  echo "old activation booleans leaked into generated policy" >&2
  exit 1
fi
if grep -q 'state: configured' "$oldest_out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans configured external services" >&2
  exit 1
fi

latest_out=$(prepare_lane latest-stable "$latest_ref" "$root/tests/fixtures/python.answers.yml")
(cd "$latest_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="change_reviewer:-:max docs_researcher:gpt-5.4-mini:- scoped_worker:gpt-5.5:high"
validate_common_lane "$latest_out"
agent_profile_expectations=""
test -f "$latest_out/docs/agent/SPEC_COPIER_ADOPTION.md"
test -f "$latest_out/.codex/skills/decision-audit/SKILL.md"
grep -q 'Codex hooks mode: `install_templates`' "$latest_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$latest_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP=`disabled`' "$latest_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$latest_out/.project-agent-workflow/scripts/skillspector-scan.sh"

replanned_history_out="$tmp/replanned-history-update"
run_copier copy -q -f --vcs-ref "$latest_ref" --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$replanned_history_out" >/dev/null
fixture_git "$replanned_history_out" init -b main >/dev/null
fixture_git "$replanned_history_out" config user.email "ci@example.invalid"
fixture_git "$replanned_history_out" config user.name "CI"
fixture_git "$replanned_history_out" add -A
fixture_git "$replanned_history_out" commit -m "Initial generated workflow" >/dev/null
python3 - "$replanned_history_out" <<'PY_REPLAN_SOURCE'
import sys
from pathlib import Path

repository = Path(sys.argv[1])
source_path = repository / "docs/plan/active/991-project-owned-history.md"
source_path.parent.mkdir(parents=True, exist_ok=True)
source_path.write_text("""# Project-owned history

status: replan_required
task_types:
  - planning_docs
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - docs/plan/
context_files:
  - none
required_specs:
  - docs/agent/PROJECT_POLICY.md
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_HUMAN_REPORTING.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
validation:
  - git diff --check
acceptance:
  - Preserve this project-owned acceptance record.
replan_reason_codes:
  - scope_drift
checked_summary_ja: プロジェクト所有の再計画履歴を保持した。

## Tasks

- [ ] Stop before restructuring.
""", encoding="utf-8")
(repository / "docs/plan/plan.md").write_text(
    "# Active Plan\n\nid\tpath\tstatus\n"
    "991\tdocs/plan/active/991-project-owned-history.md\treplan_required\n",
    encoding="utf-8",
)
# The v0.4.6 template this fixture copies from predates docs/plan/replanned.md,
# so seed the empty index the current restructuring authority requires.
replanned_index = repository / "docs/plan/replanned.md"
if not replanned_index.exists():
    replanned_index.write_text(
        "# Replanned Plan Index\n\nid\tpath\tcontract\n", encoding="utf-8"
    )
PY_REPLAN_SOURCE
fixture_git "$replanned_history_out" add docs/plan
fixture_git "$replanned_history_out" commit -m "Add stopped project-owned plan" >/dev/null
python3 - "$replanned_history_out" "$tmp/replanned-history-spec.json" <<'PY_REPLAN_SPEC'
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

repository = Path(sys.argv[1])
spec_path = Path(sys.argv[2])
source_relative = "docs/plan/active/991-project-owned-history.md"
source = (repository / source_relative).read_bytes()
acceptance = "Preserve this project-owned acceptance record."
sha = lambda value: "sha256:" + hashlib.sha256(value).hexdigest()
acceptance_digest = sha(acceptance.encode())
paths = ["docs/plan/active/992-project-owned-slice.md", "docs/plan/active/993-project-owned-integration.md"]

def plan(title: str, invariant: str) -> str:
    successors = "\n".join(f"  - {path}" for path in paths)
    return f"""# {title}

status: in_progress
primary_invariant: {invariant}
replan_source: {source_relative}
replan_contract: docs/plan/replanned/contracts/991-project-owned-history.json
integration_gates:
  - verify the complete source acceptance
successor_plans:
{successors}
inherited_acceptance_digests:
  - {acceptance_digest}
task_types:
  - planning_docs
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - docs/plan/
preservation_scope:
  - none
context_files:
  - none
required_specs:
  - docs/agent/PROJECT_POLICY.md
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_HUMAN_REPORTING.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - git diff --check
validation:
  - git diff --check
acceptance:
  - {acceptance}
validation_witness_schema: 1
validation_witness_map:
  - {{"acceptance_sha256":"{acceptance_digest}","stage":"focused","witness":"git diff --check"}}
checked_summary_ja: プロジェクト所有の後続計画。

## Tasks

- [ ] Preserve the source acceptance.
"""

today = date.today()
half = "01-15" if today.day <= 15 else "16-31"
spec = {
    "schema_version": 1,
    "source": {
        "path": source_relative,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip(),
        "plan_digest": sha(source),
        "acceptance": [{"text": acceptance, "digest": acceptance_digest}],
    },
    "reason_codes": ["scope_drift"],
    "dirty_product_paths": [],
    "contract_path": "docs/plan/replanned/contracts/991-project-owned-history.json",
    "archive_path": f"docs/plan/replanned/{today.year:04d}/{today.month:02d}/{half}/991-project-owned-history.md",
    "successors": [{
        "id": "992", "path": paths[0],
        "content": plan("Project-owned slice", "preserve the project-owned archive"),
        "acceptance_digests": [acceptance_digest],
    }],
    "integration": {
        "id": "993", "path": paths[1],
        "content": plan("Project-owned integration", "verify the project-owned history triplet"),
        "acceptance_digests": [acceptance_digest],
    },
}
spec_path.write_text(json.dumps(spec, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY_REPLAN_SPEC
(cd "$replanned_history_out" && python3 "$root/scripts/restructure-plan.py" "$tmp/replanned-history-spec.json" >/dev/null)
fixture_git "$replanned_history_out" add docs/plan
fixture_git "$replanned_history_out" commit -m "Record project-owned replanned history" >/dev/null
replanned_archive=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive_path"])' "$tmp/replanned-history-spec.json")
replanned_contract=docs/plan/replanned/contracts/991-project-owned-history.json
replanned_index=docs/plan/replanned.md
replanned_archive_before=$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_archive")
replanned_contract_before=$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_contract")
replanned_index_before=$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_index")
run_adoption "$replanned_history_out" "$target_ref" >/dev/null
test "$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_archive")" = "$replanned_archive_before"
test "$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_contract")" = "$replanned_contract_before"
test "$(fixture_git "$replanned_history_out" hash-object "$replanned_history_out/$replanned_index")" = "$replanned_index_before"
(cd "$replanned_history_out" && python3 .project-agent-workflow/scripts/restructure-plan.py --verify)
(cd "$replanned_history_out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)

pre_v1_plan_out="$tmp/v050-managed-index-plans"
run_copier copy -q -f --vcs-ref v0.5.0 --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$pre_v1_plan_out" >/dev/null
fixture_git "$pre_v1_plan_out" init -b main >/dev/null
fixture_git "$pre_v1_plan_out" config user.email "ci@example.invalid"
fixture_git "$pre_v1_plan_out" config user.name "CI"
fixture_git "$pre_v1_plan_out" add -A
fixture_git "$pre_v1_plan_out" commit -m "Initial v0.5.0 workflow" >/dev/null

pre_v1_active=docs/plan/active/901-pre-v1-validation.md
pre_v1_checked=docs/plan/checked/2025/01/01-15/900-pre-v1-checked.md
mkdir -p "$pre_v1_plan_out/docs/plan/active" "$pre_v1_plan_out/docs/plan/checked/2025/01/01-15"
cat >"$pre_v1_plan_out/$pre_v1_active" <<'EOF_PRE_V1_ACTIVE'
# Pre-v1 validation plan

status: in_progress
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - scripts/security-static-check.py
context_files:
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 scripts/security-static-check.py
  - python3 scripts/lint-plan-docs.py
acceptance:
  - Preserve the open plan across adoption.
checked_summary_ja: 移行前の作業計画を維持する。

## Tasks

- [ ] Preserve the open plan.
EOF_PRE_V1_ACTIVE
cat >"$pre_v1_plan_out/$pre_v1_checked" <<'EOF_PRE_V1_CHECKED'
# Pre-v1 checked plan

status: checked
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - scripts/security-static-check.py
context_files:
  - docs/agent/spec-index.yaml
required_specs:
  - docs/agent/SPEC_VALIDATION.md
  - docs/agent/SPEC_GIT_WORKFLOW.md
  - docs/agent/SPEC_FILE_MANAGEMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_DEVELOPMENT_FLOW.md
  - docs/agent/SPEC_SECURITY.md
validation:
  - python3 scripts/security-static-check.py
  - python3 scripts/lint-plan-docs.py
acceptance:
  - Preserve the checked plan across adoption.
checked_summary_ja: 移行前の完了記録を維持する。

## Tasks

- [x] Preserve the checked plan.

## Validation Notes

- Pre-v1 validation passed.
EOF_PRE_V1_CHECKED
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py --add-active 901 "$pre_v1_active")
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py --append-checked 900 "$pre_v1_checked")
(cd "$pre_v1_plan_out" && python3 scripts/lint-plan-docs.py)
fixture_git "$pre_v1_plan_out" add -A
fixture_git "$pre_v1_plan_out" commit -m "Add pre-v1 managed-index plan history" >/dev/null
active_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_active")
active_index_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/plan.md")
checked_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_checked")
checked_index_digest_before=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/checked.md")
for legacy_cli in scripts/lint-plan-docs.py scripts/security-static-check.py scripts/validate-changes.py; do
  source_digest=$(fixture_git "$update_source" show "v0.5.0:template/$legacy_cli" | git hash-object --stdin)
  destination_digest=$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$legacy_cli")
  test "$destination_digest" = "$source_digest"
done

run_adoption "$pre_v1_plan_out" "$target_ref" >/dev/null
manifest="$pre_v1_plan_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
if ! grep -q '^def has_pre_v1_adoption_provenance()' "$pre_v1_plan_out/.project-agent-workflow/scripts/planlib.py"; then
  echo "adoption did not install the candidate managed plan compatibility helper" >&2
  exit 1
fi
python3 - "$manifest" "$pre_v1_plan_out" <<'PY_PRE_V1_BRIDGES'
import json
import stat
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
repository = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
expected_paths = {
    "scripts/lint-plan-docs.py",
    "scripts/security-static-check.py",
    "scripts/validate-changes.py",
}
bridged = set(manifest.get("bridged_legacy_cli_paths", []))
missing = sorted(expected_paths - bridged)
if missing:
    raise SystemExit(f"adoption manifest is missing bridged legacy CLI paths: {missing}")
if manifest.get("operation") != "recopy_adoption" or manifest.get("previous_ref") != "v0.5.0":
    raise SystemExit("adoption manifest has unexpected pre-v1 provenance")
if "docs/agent/spec-index.yaml" not in set(manifest.get("adoption_copied", [])):
    raise SystemExit("adoption manifest did not preserve the pre-v1 routing index")

for relative in sorted(expected_paths):
    path = repository / relative
    managed = f".project-agent-workflow/{relative}"
    expected = f'''#!/usr/bin/env python3
"""Compatibility bridge to Copier-managed workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path


managed = Path(__file__).resolve().parents[1] / "{managed}"
os.execv(sys.executable, [sys.executable, str(managed), *sys.argv[1:]])
'''
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"legacy CLI is not the deterministic compatibility bridge: {relative}")
    if stat.S_IMODE(path.stat().st_mode) != 0o755:
        raise SystemExit(f"legacy CLI bridge is not executable: {relative}")
PY_PRE_V1_BRIDGES
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_active")" = "$active_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/plan.md")" = "$active_index_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/$pre_v1_checked")" = "$checked_digest_before"
test "$(fixture_git "$pre_v1_plan_out" hash-object "$pre_v1_plan_out/docs/plan/checked.md")" = "$checked_index_digest_before"
(cd "$pre_v1_plan_out" && PYTHONDONTWRITEBYTECODE=1 python3 - "$pre_v1_active" <<'PY_PRE_V1_PLAN'
import sys
from pathlib import Path

sys.path.insert(0, ".project-agent-workflow/scripts")
import plan_validation_commands
import planlib

if not planlib.has_pre_v1_adoption_provenance():
    raise SystemExit("managed plan lint did not recognize pre-v1 adoption provenance")
plan_validation_commands.check_legacy_plan_for_lint(Path(sys.argv[1]), Path.cwd())
PY_PRE_V1_PLAN
)
(cd "$pre_v1_plan_out" && python3 scripts/validate-changes.py --all >/dev/null)
(cd "$pre_v1_plan_out" && python3 .project-agent-workflow/scripts/validate-changes.py --all >/dev/null)
(cd "$pre_v1_plan_out" && python3 .project-agent-workflow/scripts/lint-plan-docs.py)
fixture_git "$pre_v1_plan_out" diff --check

v100_out=$(prepare_lane v100-repair v1.0.0 "$root/tests/fixtures/python.answers.yml")
(cd "$v100_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="change_reviewer:-:max scoped_worker:-:high"
validate_common_lane "$v100_out" 0 patch_only
agent_profile_expectations=""
grep -q '^_commit: v1.3.1$' "$v100_out/.copier-answers.yml"

legacy_disabled_out=$(prepare_lane oldest-disabled "$oldest_ref" "$legacy_disabled_answers")
(cd "$legacy_disabled_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="repo_explorer:-:medium"
validate_common_lane "$legacy_disabled_out"
agent_profile_expectations=""
grep -q 'Codex hooks mode: `disabled`' "$legacy_disabled_out/.project-agent-workflow/AGENTS.md"
grep -q 'SkillSpector mode: `disabled`' "$legacy_disabled_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP=`disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear=`disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'graph memory=`disabled`' "$legacy_disabled_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
test ! -f "$legacy_disabled_out/.project-agent-workflow/scripts/skillspector-scan.sh"

legacy_override_out=$(prepare_lane oldest-explicit-disabled "$oldest_ref" "$legacy_answers" \
  --data codex_hooks_mode=disabled \
  --data skillspector_mode=disabled \
  --data mcp_policy_mode=disabled \
  --data linear_sync_mode=disabled \
  --data graph_memory_mode=disabled \
  --data ci_autofix_mode=disabled)
(cd "$legacy_override_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="repo_explorer:-:medium"
validate_common_lane "$legacy_override_out"
agent_profile_expectations=""
grep -q 'External service policy states: MCP=`disabled`, Linear=`disabled`, graph memory=`disabled`' "$legacy_override_out/.project-agent-workflow/AGENTS.md"
grep -q 'MCP=`disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'Linear=`disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
grep -q 'graph memory=`disabled`' "$legacy_override_out/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md"
if grep -q 'state: documented' "$legacy_override_out/docs/agent/external-services.yaml"; then
  echo "legacy activation booleans overrode explicit disabled modes" >&2
  exit 1
fi
test ! -f "$legacy_override_out/.project-agent-workflow/scripts/skillspector-scan.sh"

modified_out="$tmp/oldest-modified-skillspector"
run_copier copy -q -f --vcs-ref "$oldest_ref" --data-file "$legacy_disabled_answers" "$update_source" "$modified_out" >/dev/null
fixture_git "$modified_out" init -b main >/dev/null
fixture_git "$modified_out" config user.email "ci@example.invalid"
fixture_git "$modified_out" config user.name "CI"
fixture_git "$modified_out" add -A
fixture_git "$modified_out" commit -m "Initial generated workflow" >/dev/null
printf '\n# project-owned modification\n' >>"$modified_out/scripts/skillspector-scan.sh"
fixture_git "$modified_out" add scripts/skillspector-scan.sh
fixture_git "$modified_out" commit -m "Customize SkillSpector helper" >/dev/null
run_adoption "$modified_out" "$target_ref" >/dev/null
if (cd "$modified_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null 2>&1); then
  echo "modified legacy optional file was not reported for manual review" >&2
  exit 1
fi
grep -q 'project-owned modification' "$modified_out/.project-agent-workflow-migration/v1-pre-namespace/scripts/skillspector-scan.sh"
grep -q 'project-owned modification' "$modified_out/scripts/skillspector-scan.sh"
grep -q 'scripts/skillspector-scan.sh' "$modified_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"
test -f "$modified_out/.project-agent-workflow/scripts/migrate-legacy-template-files.py"
(cd "$modified_out" && python3 .project-agent-workflow/scripts/check-external-service-policy.py check >/dev/null)
fixture_git "$modified_out" diff --check

mature_out="$tmp/mature-customized-project"
run_copier copy -q -f --vcs-ref "$latest_ref" --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$mature_out" >/dev/null
fixture_git "$mature_out" init -b main >/dev/null
fixture_git "$mature_out" config user.email "ci@example.invalid"
fixture_git "$mature_out" config user.name "CI"
fixture_git "$mature_out" add -A
fixture_git "$mature_out" commit -m "Initial generated workflow" >/dev/null

printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/docs_researcher.toml"
printf '\n# project agent marker\n' >>"$mature_out/.codex/agents/scoped_worker.toml"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/pre_tool_hardening_gate.py"
printf '\n# legacy hook marker\n' >>"$mature_out/.codex/hooks/stop_review_gate.py"
cat >"$mature_out/.codex/hooks.json" <<'EOF_MATURE_HOOKS'
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/project-hook.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/agent_log_event.py --event Stop"
          }
        ]
      }
    ]
  }
}
EOF_MATURE_HOOKS
printf '\nProject adoption policy marker.\n' >>"$mature_out/docs/agent/SPEC_COPIER_ADOPTION.md"
printf '\nProject environment policy marker.\n' >>"$mature_out/docs/agent/SPEC_ENVIRONMENT.md"
printf '\nProject UI policy marker.\n' >>"$mature_out/docs/agent/SPEC_UI_DESIGN.md"
printf '\n# project plan lifecycle marker\n' >>"$mature_out/scripts/complete-plan.sh"
printf '\nProject implementation skill marker.\n' >>"$mature_out/.codex/skills/implementation-guidelines/SKILL.md"
cat >"$mature_out/docs/agent/SPEC_PRODUCT.md" <<'EOF_MATURE_PRODUCT'
# Product Notes

Local project-owned agent notes.
EOF_MATURE_PRODUCT
cat >"$mature_out/docs/agent/PROJECT_ENVIRONMENT.md" <<'EOF_MATURE_ENVIRONMENT'
# Project Environment

Preserve this project-owned environment policy.
EOF_MATURE_ENVIRONMENT
cat >"$mature_out/docs/agent/PROJECT_UI_DESIGN.md" <<'EOF_MATURE_UI'
# Project UI Design

Preserve this project-owned UI policy.
EOF_MATURE_UI
cat >"$mature_out/.codex/agents/docs_researcher.toml" <<'EOF_MATURE_DOCS_RESEARCHER'
name = "docs_researcher"
description = "Customized docs_researcher profile."
  model = "legacy-model"
  model_reasoning_effort = "legacy-effort"
sandbox_mode = "workspace-write"

developer_instructions = """
Keep this project instruction.
"""
EOF_MATURE_DOCS_RESEARCHER
cat >"$mature_out/.codex/agents/scoped_worker.toml" <<'EOF_MATURE_SCOPED_WORKER'
  name = "scoped_worker"
  description = "Customized scoped_worker profile."
  model = "seed-equal-value"
sandbox_mode = "workspace-write"

developer_instructions = """
Keep this project instruction.
"""
EOF_MATURE_SCOPED_WORKER
cat >"$mature_out/.codex/agents/repo_explorer.toml" <<'EOF_MATURE_REPO_EXPLORER'
  name = "project_repository_reader"
  description = "Customized repo_explorer profile."
sandbox_mode = "workspace-write"

developer_instructions = """
Keep this project instruction.
"""
EOF_MATURE_REPO_EXPLORER
mkdir -p "$mature_out/.github/workflows"
cat >"$mature_out/.github/workflows/product-verify.yml" <<'EOF_MATURE_WORKFLOW'
name: Product verification
on: workflow_dispatch
jobs: {}
EOF_MATURE_WORKFLOW
cat >"$mature_out/scripts/validate-project-adoption.sh" <<'EOF_MATURE_VALIDATOR'
#!/bin/sh
set -eu
grep -q '^_commit: v0.4.6$' .copier-answers.yml
EOF_MATURE_VALIDATOR
fixture_git "$mature_out" add -A
fixture_git "$mature_out" commit -m "Customize mature project workflow" >/dev/null

run_adoption "$mature_out" "$target_ref" >/dev/null
(cd "$mature_out" && python3 .project-agent-workflow/scripts/migrate-legacy-template-files.py >/dev/null)
agent_profile_expectations="change_reviewer:-:max docs_researcher:legacy-model:legacy-effort scoped_worker:seed-equal-value:-"
validate_common_lane "$mature_out"
agent_profile_expectations=""
grep -q 'Keep this project instruction.' "$mature_out/.codex/agents/docs_researcher.toml"
grep -q 'Keep this project instruction.' "$mature_out/.codex/agents/repo_explorer.toml"
# The project already declared both fields, so the update must keep its values.
grep -q '^  model = "legacy-model"$' "$mature_out/.codex/agents/docs_researcher.toml"
grep -q '^  model_reasoning_effort = "legacy-effort"$' "$mature_out/.codex/agents/docs_researcher.toml"
if grep -q 'gpt-5.6-luna' "$mature_out/.codex/agents/docs_researcher.toml"; then
  echo "update replaced a project-owned agent model value" >&2
  exit 1
fi
# The project declared model but not the effort, so only the effort is filled.
grep -q '^  model = "seed-equal-value"$' "$mature_out/.codex/agents/scoped_worker.toml"
grep -q '^  model_reasoning_effort = "medium"$' "$mature_out/.codex/agents/scoped_worker.toml"
# The project declared neither field, so both defaults are inserted.
grep -q '^  model = "gpt-5.6-luna"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  model_reasoning_effort = "low"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  name = "project_repository_reader"$' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q '^  description = "Customized repo_explorer profile\."' "$mature_out/.codex/agents/repo_explorer.toml"
grep -q 'Project adoption policy marker.' "$mature_out/docs/agent/SPEC_COPIER_ADOPTION.md"
grep -q 'Project environment policy marker.' "$mature_out/docs/agent/SPEC_ENVIRONMENT.md"
grep -q 'Project UI policy marker.' "$mature_out/docs/agent/SPEC_UI_DESIGN.md"
grep -q 'project plan lifecycle marker' "$mature_out/scripts/complete-plan.sh"
grep -q 'Project implementation skill marker.' "$mature_out/.codex/skills/implementation-guidelines/SKILL.md"
grep -q 'name: Product verification' "$mature_out/.github/workflows/product-verify.yml"
grep -q 'legacy hook marker' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/.codex/hooks/pre_tool_hardening_gate.py"
grep -q 'legacy hook marker' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/.codex/hooks/stop_review_gate.py"
if grep -q 'legacy hook marker' "$mature_out/.codex/hooks/pre_tool_hardening_gate.py" "$mature_out/.codex/hooks/stop_review_gate.py"; then
  echo "legacy hook implementation remained active after adoption" >&2
  exit 1
fi
grep -q 'Compatibility bridge' "$mature_out/.codex/hooks/pre_tool_hardening_gate.py"
grep -q 'Compatibility bridge' "$mature_out/.codex/hooks/stop_review_gate.py"
grep -q 'scripts/project-hook.py' "$mature_out/.codex/hooks.json"
grep -q '.project-agent-workflow/hooks/stop_review_gate.py' "$mature_out/.codex/hooks.json"
test "$(grep -c 'stop_review_gate.py' "$mature_out/.codex/hooks.json")" -eq 1
grep -q 'scripts/validate-project-adoption.sh' "$mature_out/.project-agent-workflow-migration/v1-pre-namespace/manifest.json"

repair_out="$tmp/v110-preserved-hooks"
run_copier copy -q -f --vcs-ref v1.1.0 --data-file "$root/tests/fixtures/typescript.answers.yml" "$update_source" "$repair_out" >/dev/null
fixture_git "$repair_out" init -b main >/dev/null
fixture_git "$repair_out" config user.email "ci@example.invalid"
fixture_git "$repair_out" config user.name "CI"
cat >"$repair_out/.codex/hooks.json" <<'EOF_REPAIR_HOOKS'
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/agent_log_event.py --event Stop"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 scripts/project-hook.py"
          }
        ]
      }
    ]
  }
}
EOF_REPAIR_HOOKS
fixture_git "$repair_out" add -A
fixture_git "$repair_out" commit -m "Preserve pre-v1 Hook configuration" >/dev/null
run_copier update -q -f --trust --vcs-ref v1.2.1 "$repair_out" >/dev/null
grep -q 'scripts/project-hook.py' "$repair_out/.codex/hooks.json"
grep -q '.project-agent-workflow/hooks/stop_review_gate.py' "$repair_out/.codex/hooks.json"
test "$(grep -c 'stop_review_gate.py' "$repair_out/.codex/hooks.json")" -eq 1
grep -q 'Compatibility bridge' "$repair_out/.codex/hooks/stop_review_gate.py"
fixture_git "$repair_out" diff --check

v111_out="$tmp/v111-without-plan-placeholders"
run_copier copy -q -f --vcs-ref v1.1.1 --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$v111_out" >/dev/null
fixture_git "$v111_out" init -b main >/dev/null
fixture_git "$v111_out" config user.email "ci@example.invalid"
fixture_git "$v111_out" config user.name "CI"
fixture_git "$v111_out" add -A
fixture_git "$v111_out" commit -m "Initial v1.1.1 workflow" >/dev/null
for plan_dir in active backlog checked handoffs; do
  test -f "$v111_out/docs/plan/$plan_dir/.gitkeep"
  fixture_git "$v111_out" rm -q "docs/plan/$plan_dir/.gitkeep"
done
fixture_git "$v111_out" commit -m "Remove plan directory placeholders" >/dev/null
run_copier update -q -f --trust --vcs-ref v1.2.1 "$v111_out" >/dev/null
assert_agent_profiles "$v111_out"
for plan_dir in active backlog checked handoffs; do
  if [ -e "$v111_out/docs/plan/$plan_dir/.gitkeep" ]; then
    echo "copier update recreated removed plan placeholder: docs/plan/$plan_dir/.gitkeep" >&2
    exit 1
  fi
done
grep -q '^_commit: v1.2.1$' "$v111_out/.copier-answers.yml"
fixture_git "$v111_out" diff --check

future_source="$update_source"
future_out="$tmp/future-project"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 --data-file "$root/tests/fixtures/typescript.answers.yml" "$future_source" "$future_out" >/dev/null
fixture_git "$future_out" init -b main >/dev/null
fixture_git "$future_out" config user.email "ci@example.invalid"
fixture_git "$future_out" config user.name "CI"
fixture_git "$future_out" add -A
fixture_git "$future_out" commit -m "Initial namespaced workflow" >/dev/null

printf '# Project Agents\n\nProject AGENTS marker.\nDo not use `.agents/skills/natural-japanese/SKILL.md`.\nThe bridge is already installed at `.agents/skills/natural-japanese/SKILL.md`.\n' >"$future_out/AGENTS.md"
printf '\nProject README marker.\n' >>"$future_out/README.md"
printf '\n# project ignore marker\n' >>"$future_out/.gitignore"
printf '\n# project config marker\n' >>"$future_out/.codex/config.toml"
sed -i '1s/^{/{\n  "_project_owned_marker": true,/' "$future_out/.codex/hooks.json"
printf '\nProject environment marker.\n' >>"$future_out/docs/agent/PROJECT_ENVIRONMENT.md"
printf '\nProject policy marker.\n' >>"$future_out/docs/agent/PROJECT_POLICY.md"
printf '\n# project external-service marker\n' >>"$future_out/docs/agent/external-services.yaml"
printf '\nProject plan marker.\n' >>"$future_out/docs/plan/README.md"
cat >"$future_out/docs/agent/SPEC_PRODUCT.md" <<'EOF_FUTURE_SPEC'
# Product Policy

Project product marker.
EOF_FUTURE_SPEC
mkdir -p "$future_out/.agents/skills/product-rules" "$future_out/.github/workflows"
cat >"$future_out/.agents/skills/product-rules/SKILL.md" <<'EOF_FUTURE_SKILL'
---
name: product-rules
description: Apply project-owned product rules.
---

# Product Rules
EOF_FUTURE_SKILL
cat >"$future_out/.github/workflows/ci.yml" <<'EOF_FUTURE_CI'
name: Product CI
on: workflow_dispatch
jobs: {}
EOF_FUTURE_CI
fixture_git "$future_out" add -A
fixture_git "$future_out" commit -m "Add project-owned extensions" >/dev/null
future_agents_before=$(fixture_git "$future_out" hash-object AGENTS.md)

printf 'dirty update preflight\n' >"$future_out/untracked-before-update.txt"
if "$future_out/.project-agent-workflow/scripts/update-from-copier.sh" \
  --defaults --vcs-ref v1.2.2 >/dev/null 2>&1; then
  echo "Copier update wrapper accepted a dirty pre-update worktree" >&2
  exit 1
fi
rm -f "$future_out/untracked-before-update.txt"

sed -i 's|Update files here through `copier update` and do not add project-specific policy or runtime facts here\.|Update files here through the generated update wrapper; keep project-specific policy and runtime facts outside this core.|' \
  "$future_source/template/.project-agent-workflow/README.md"
grep -q 'generated update wrapper' "$future_source/template/.project-agent-workflow/README.md"
fixture_git "$future_source" add template/.project-agent-workflow/README.md
fixture_git "$future_source" -c user.email=ci@example.invalid -c user.name=CI commit -m "Update managed core through the wrapper" >/dev/null
fixture_git "$future_source" tag v1.2.3

outside_cwd="$tmp/outside-cwd"
mkdir -p "$outside_cwd"
if [ -n "$(fixture_git "$future_out" status --porcelain=v1)" ]; then
  echo "clean recurring wrapper fixture is dirty before update" >&2
  fixture_git "$future_out" status --short >&2
  exit 1
fi
future_warning="$tmp/future-update-warning.txt"
if ! (cd "$outside_cwd" && "$future_out/.project-agent-workflow/scripts/update-from-copier.sh" --defaults --vcs-ref v1.2.3 >/dev/null 2>"$future_warning"); then
  echo "clean recurring Copier wrapper update failed" >&2
  exit 1
fi

grep -q 'generated update wrapper' "$future_out/.project-agent-workflow/README.md"
test "$future_agents_before" = "$(fixture_git "$future_out" hash-object AGENTS.md)"
grep -q 'Project AGENTS marker.' "$future_out/AGENTS.md"
test -f "$future_out/.agents/skills/natural-japanese/SKILL.md"
test -f "$future_out/.project-agent-workflow/skills/natural-japanese/SKILL.md"
grep -Fq 'Copier update preserved project-owned AGENTS.md without Japanese-writing routing.' "$future_warning"
grep -Fq 'read `.agents/skills/natural-japanese/SKILL.md` after the governing project policy.' "$future_warning"
PYTHONDONTWRITEBYTECODE=1 python3 - "$future_out" <<'PY'
import importlib.util
import sys
from pathlib import Path

repository = Path(sys.argv[1])
script = repository / ".project-agent-workflow/scripts/validate-copier-update.py"
spec = importlib.util.spec_from_file_location("validate_copier_update", script)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
agents = repository / "AGENTS.md"
original = agents.read_text(encoding="utf-8")
seed = next(
    line for line in module.JAPANESE_ROUTING_LINES if ", read `" in line
)
managed = next(
    line for line in module.JAPANESE_ROUTING_LINES if ", use `" in line
)
invalid = (
    f"```markdown\n{seed}\n```\n",
    f"````markdown\n```not-a-closer\n{seed}\n````\n",
    f"    {seed}\n",
    f"   \t{seed}\n",
    f"<!--\n{seed}\n-->\n",
    f"```text\nexample\n\t```\n{seed}\n```\n",
    f"{seed} Example only; do not follow this line.\n",
    "The bridge is documented at `.agents/skills/natural-japanese/SKILL.md`.\n",
    f"- Do not use this routing instruction: {managed}\n",
)
try:
    for content in invalid:
        agents.write_text(content, encoding="utf-8")
        if not module.needs_japanese_routing_guidance(repository):
            raise SystemExit("non-operative Japanese routing text suppressed guidance")
    for content in (
        seed + "\n",
        managed + "\n",
        f"```bad`info\n{seed}\n",
    ):
        agents.write_text(content, encoding="utf-8")
        if module.needs_japanese_routing_guidance(repository):
            raise SystemExit("canonical Japanese routing line was not recognized")
    agents.write_text(module.JAPANESE_ROUTING_SUGGESTION + "\n", encoding="utf-8")
    if module.needs_japanese_routing_guidance(repository):
        raise SystemExit("emitted Japanese routing suggestion was not canonical")
finally:
    agents.write_text(original, encoding="utf-8")
PY
grep -q 'Project README marker.' "$future_out/README.md"
grep -q 'project ignore marker' "$future_out/.gitignore"
grep -q 'project config marker' "$future_out/.codex/config.toml"
grep -q '"_project_owned_marker": true' "$future_out/.codex/hooks.json"
grep -q 'Project environment marker.' "$future_out/docs/agent/PROJECT_ENVIRONMENT.md"
grep -q 'Project policy marker.' "$future_out/docs/agent/PROJECT_POLICY.md"
grep -q 'project external-service marker' "$future_out/docs/agent/external-services.yaml"
grep -q 'Project plan marker.' "$future_out/docs/plan/README.md"
grep -q 'Project product marker.' "$future_out/docs/agent/SPEC_PRODUCT.md"
test -f "$future_out/.agents/skills/product-rules/SKILL.md"
grep -q 'name: Product CI' "$future_out/.github/workflows/ci.yml"
if find "$future_out" -name '*.rej' -print -quit | grep -q .; then
  echo "namespaced copier update produced rejection files" >&2
  exit 1
fi
if grep -R -n -E '^(<<<<<<<|=======|>>>>>>>)' "$future_out" --exclude-dir=.git >/dev/null; then
  echo "namespaced copier update produced inline conflict markers" >&2
  exit 1
fi
fixture_git "$future_out" diff --check

wrapper_conflict_out="$tmp/v122-to-v123-conflict"
run_copier copy -q -f --trust --defaults --vcs-ref v1.2.2 \
  --data-file "$root/tests/fixtures/docs.answers.yml" "$future_source" "$wrapper_conflict_out" >/dev/null
fixture_git "$wrapper_conflict_out" init -b main >/dev/null
fixture_git "$wrapper_conflict_out" config user.email "ci@example.invalid"
fixture_git "$wrapper_conflict_out" config user.name "CI"
fixture_git "$wrapper_conflict_out" add -A
fixture_git "$wrapper_conflict_out" commit -m "Create recurring wrapper fixture" >/dev/null
sed -i 's|Update files here through `copier update` and do not add project-specific policy or runtime facts here\.|Keep this project-specific managed-core instruction for the conflict fixture.|' \
  "$wrapper_conflict_out/.project-agent-workflow/README.md"
grep -q 'project-specific managed-core instruction' "$wrapper_conflict_out/.project-agent-workflow/README.md"
fixture_git "$wrapper_conflict_out" add .project-agent-workflow/README.md
fixture_git "$wrapper_conflict_out" commit -m "Customize the recurring update line" >/dev/null
if [ -n "$(fixture_git "$wrapper_conflict_out" status --porcelain=v1)" ]; then
  echo "conflicting recurring wrapper fixture is dirty before update" >&2
  fixture_git "$wrapper_conflict_out" status --short >&2
  exit 1
fi
if (cd "$outside_cwd" && "$wrapper_conflict_out/.project-agent-workflow/scripts/update-from-copier.sh" --defaults --vcs-ref v1.2.3 >/dev/null 2>&1); then
  echo "recurring Copier wrapper accepted a same-line merge conflict" >&2
  exit 1
fi
if ! fixture_git "$wrapper_conflict_out" ls-files -u | grep -q .; then
  echo "v1.2.2-to-v1.2.3 fixture did not create a real index conflict" >&2
  exit 1
fi

# The synthetic v1.4.4 boundary is this template without the installed
# validation-witness policy marker, so the before migration reads the
# committed downstream project as pre-schema.
v145_marker='validation-witness-migration-provenance-schema: 1'
v145_policy="$update_source/template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -qF "$v145_marker" "$v145_policy"
sed -i "s/$v145_marker/validation-witness-migration-provenance-boundary: absent/" "$v145_policy"
if grep -qF "$v145_marker" "$v145_policy"; then
  echo "the synthetic v1.4.4 policy still installs the validation-witness boundary" >&2
  exit 1
fi
fixture_git "$update_source" add -- template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
fixture_git "$update_source" -c user.email=ci@example.invalid -c user.name=CI \
  commit -qm "Create the pre-schema v1.4.4 boundary"
# The clone carries the released tags of this template, so both synthetic
# boundaries replace whatever the clone already names.
fixture_git "$update_source" tag -f v1.4.4

# The synchronization command runs as its own migration of the synthetic
# v1.4.5 boundary, ordered directly after the before migration that publishes
# the pending attempt. It emits the ready event once that migration has
# returned and holds the update child until this fixture writes the release
# path, which is how the fixture observes the pending state, the guardian
# identifier, and the release paths without naming the migration command.
v145_ready="$tmp/v145-guardian-ready"
v145_hold="$tmp/v145-hold-before-stage.sh"
cat >"$v145_hold" <<EOF_V145_HOLD
#!/bin/sh
set -eu
: >"$v145_ready"
held=0
while [ "\$held" -lt 600 ]; do
  if [ -e "$v145_release" ]; then
    exit 0
  fi
  if [ ! -d "$tmp" ]; then
    echo "the fixture temporary root disappeared while the update was held" >&2
    exit 1
  fi
  held=\$((held + 1))
  sleep 1
done
echo "the fixture release event was not observed" >&2
exit 1
EOF_V145_HOLD
chmod +x "$v145_hold"

sed -i "s/validation-witness-migration-provenance-boundary: absent/$v145_marker/" "$v145_policy"
grep -qF "$v145_marker" "$v145_policy"
python3 - "$update_source/copier.yml" "$v145_hold" <<'PY_V145_MIGRATION'
import re
import sys
from pathlib import Path

configuration = Path(sys.argv[1])
hold = sys.argv[2]
text = configuration.read_text(encoding="utf-8")
if "'" in hold or "\n" in hold:
    raise SystemExit("the fixture synchronization command path is not quotable")
starts = [match.start() for match in re.finditer(r"^  - version: ", text, re.MULTILINE)]
if not starts:
    raise SystemExit("the fixture source declares no versioned Copier migration")
selected = [
    (start, stop)
    for start, stop in zip(starts, starts[1:] + [len(text)])
    if text[start:stop].startswith("  - version: v1.4.5\n")
    and "_stage == 'before'" in text[start:stop]
]
if len(selected) != 1:
    raise SystemExit("the v1.4.5 before-stage migration is not written exactly once")
stop = selected[0][1]
if stop not in starts:
    raise SystemExit("the v1.4.5 before-stage migration is written last")
entry = (
    "  - version: v1.4.5\n"
    "    command:\n"
    f"      - '{hold}'\n"
    "    when: \"[[ _stage == 'before' ]]\"\n"
)
configuration.write_text(text[:stop] + entry + text[stop:], encoding="utf-8")
PY_V145_MIGRATION
fixture_git "$update_source" add -- copier.yml \
  template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
fixture_git "$update_source" -c user.email=ci@example.invalid -c user.name=CI \
  commit -qm "Create the v1.4.5 validation-witness boundary"
fixture_git "$update_source" tag -f v1.4.5

v145_project="$tmp/v145-project"
v145_plan="docs/plan/active/902-pre-schema-integration.md"
v145_contract="docs/plan/replanned/contracts/901-source.json"
v145_archive="docs/plan/replanned/2026/08/16-31/901-source.md"
v145_record="$v145_project/.project-agent-workflow-migration/validation-witness-provenance-v1.json"
v145_log="$tmp/v145-update.log"
run_copier copy -q -f --trust --defaults --vcs-ref v1.4.4 \
  --data-file "$root/tests/fixtures/python.answers.yml" "$update_source" "$v145_project" >/dev/null
grep -q '^_commit: v1.4.4$' "$v145_project/.copier-answers.yml"
if grep -qF "$v145_marker" "$v145_project/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"; then
  echo "the generated v1.4.4 project already installs the validation-witness boundary" >&2
  exit 1
fi

mkdir -p "$v145_project/docs/plan/active" \
  "$v145_project/docs/plan/replanned/contracts" \
  "$v145_project/docs/plan/replanned/2026/08/16-31"
cat >"$v145_project/$v145_plan" <<'EOF_V145_PLAN'
# Pre-schema integration

status: in_progress
primary_invariant: preserve the committed integration identity
replan_contract: docs/plan/replanned/contracts/901-source.json
acceptance:
  - Preserve the pre-schema acceptance.
validation:
  - python3 scripts/validate-changes.py --all
checked_summary_ja: 移行前の統合計画を保持する。

## Tasks

- [ ] Preserve the integration boundary.
EOF_V145_PLAN
cat >"$v145_project/$v145_archive" <<'EOF_V145_ARCHIVE'
# Replanned source

status: replanned
EOF_V145_ARCHIVE
python3 - "$v145_project" "$v145_plan" "$v145_contract" "$v145_archive" <<'PY_V145_CONTRACT'
import hashlib
import json
import sys
from pathlib import Path

project = Path(sys.argv[1])
plan_path = sys.argv[2]
contract_path = sys.argv[3]
archive_path = sys.argv[4]


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


plan_raw = (project / plan_path).read_bytes()
acceptance = ["Preserve the pre-schema acceptance."]
contract = {
    "archive_path": archive_path,
    "contract_path": contract_path,
    "schema_version": 1,
    "successors": [
        {
            "acceptance_digests": [digest(item.encode("utf-8")) for item in acceptance],
            "content": plan_raw.decode("utf-8"),
            "content_digest": digest(plan_raw),
            "integration": True,
            "path": plan_path,
        }
    ],
}
(project / contract_path).write_text(
    json.dumps(contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
PY_V145_CONTRACT
fixture_git "$v145_project" init -b main >/dev/null
fixture_git "$v145_project" config user.email "ci@example.invalid"
fixture_git "$v145_project" config user.name "CI"
fixture_git "$v145_project" add -A
fixture_git "$v145_project" commit -qm "Create the pre-schema v1.4.4 project"
v145_git_dir=$(fixture_git "$v145_project" rev-parse --path-format=absolute --absolute-git-dir)
v145_attempt="$v145_git_dir/project-agent-workflow/validation-witness-provenance-v1.attempt.json"

# Plan 183 settled a bounded wait on the update process itself, so this
# fixture reads the identifier it started. The identifier stays its own
# unreaped child until this wait retires it, and the forced signals run only
# while that child is still live.
"$v145_project/.project-agent-workflow/scripts/update-from-copier.sh" \
  --defaults --vcs-ref v1.4.5 >"$v145_log" 2>&1 &
update_pid=$!

v145_ready_waited=0
while [ "$v145_ready_waited" -lt 300 ]; do
  if [ -e "$v145_ready" ]; then
    break
  fi
  v145_ready_waited=$((v145_ready_waited + 1))
  sleep 1
done
if [ ! -e "$v145_ready" ]; then
  touch "$v145_release"
  echo "the guardian ready event was not observed" >&2
  cat "$v145_log" >&2
  exit 1
fi

grep -q '"state": "pending"' "$v145_attempt"
guardian_pid=$(sed -n 's/^ *"guardian_pid": *\([0-9][0-9]*\),\{0,1\} *$/\1/p' "$v145_attempt")
case "$guardian_pid" in
  ''|*[!0-9]*)
    echo "the guardian PID was not read from the pending attempt state" >&2
    exit 1
    ;;
esac
[ "$guardian_pid" -gt 0 ]

touch "$v145_release"

v145_exit_waited=0
while [ "$v145_exit_waited" -lt 30 ]; do
  if ! kill -0 "$update_pid" 2>/dev/null; then
    break
  fi
  v145_exit_waited=$((v145_exit_waited + 1))
  sleep 1
done
v145_update_status=0
v145_reaped=0
if ! kill -0 "$update_pid" 2>/dev/null; then
  wait "$update_pid" || v145_update_status=$?
  v145_reaped=1
fi
if [ "$v145_reaped" -eq 0 ]; then
  kill -TERM "$update_pid" 2>/dev/null || true
  sleep 5
  kill -KILL "$update_pid" 2>/dev/null || true
fi
wait "$update_pid" 2>/dev/null || true
update_pid=
if [ "$v145_reaped" -ne 1 ] || [ "$v145_update_status" -ne 0 ]; then
  echo "the v1.4.4-to-v1.4.5 transition update did not complete" >&2
  cat "$v145_log" >&2
  exit 1
fi

grep -q '"state": "consumed"' "$v145_attempt"
grep -q '^_commit: v1.4.5$' "$v145_project/.copier-answers.yml"
grep -qF "$v145_marker" "$v145_project/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md"
grep -q '"migration_version": "v1.4.5"' "$v145_record"
grep -q '"previous_template_ref": "v1.4.4"' "$v145_record"
grep -q "\"path\": \"$v145_plan\"" "$v145_record"
test -f "$v145_project/$v145_contract"
test -f "$v145_project/$v145_archive"
if find "$v145_project" -name '*.rej' -print -quit | grep -q .; then
  echo "the v1.4.5 transition produced rejection files" >&2
  exit 1
fi
fixture_git "$v145_project" diff --check

echo "copier update test passed"
