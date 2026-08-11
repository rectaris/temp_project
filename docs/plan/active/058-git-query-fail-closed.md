# Fail validation when required Git queries fail

status: in_progress
task_types:
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/active/058-git-query-fail-closed.md
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/security-static-check.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - tests/test-validation-tools.py
context_files:
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/scripts/security_rules.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Change selection exits nonzero with an actionable message when a required Git query fails.
  - Changed-file security scanning exits nonzero when it cannot obtain the Git-visible path set.
  - A legitimate repository with no changes still reports the existing no-change success state.
  - Root and generated validators retain aligned fail-closed behavior.
checked_summary_ja: Git query 失敗を変更なしとして扱わず、変更選択と security scan を明示的な非ゼロ終了にする。

## Context

Change and security validators must fail when required Git queries fail.

The validators currently convert every nonzero Git result into an empty path list, which allows broken repository state to pass as no changes or a successful security scan.

## Decisions

- Distinguish Git failure from an empty successful result.
- Preserve machine-readable JSON failure output where the root validator supports JSON mode.

## Tasks

- [ ] Add regression tests that inject a failing Git environment.
- [ ] Raise or return explicit Git query failures in root and generated validators.
- [ ] Preserve the successful empty-change behavior.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
