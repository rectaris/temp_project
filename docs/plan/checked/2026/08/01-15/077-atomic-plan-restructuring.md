# Implement atomic plan restructuring

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - CHANGELOG.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - template/docs/plan/README.md
  - template/docs/plan/replanned.md
  - tests/root-plan-lifecycle.sh
  - tests/smoke.sh
  - tests/test-plan-restructure.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/checked/2026/08/01-15/076-plan-restructuring-policy-schema.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-plan-restructure.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add a parent-owned restructuring command that accepts one `replan_required` source plan, a bounded exact-schema successor specification, and a destination integration plan.
  - Verify source HEAD, source-plan digest, every normalized acceptance digest, active-index mapping, successor identifiers and paths, and complete acceptance mapping before changing metadata.
  - Copy every source acceptance item exactly into the integration plan and require each item to map to at least one successor or integration gate; reject missing, duplicate, malformed, or unauthorized replacement mappings.
  - Move the source plan to a distinct date-partitioned replanned archive with status `replanned`, create successors as `in_progress`, and update active and replanned indexes atomically under a lock.
  - Use exclusive destination creation, reject path traversal and collisions, and restore original metadata when any transition write fails.
  - Preserve committed work and leave dirty product changes and unaccepted candidate artifacts untouched; require every recorded dirty path to be covered by a successor write scope before execution resumes.
  - Keep complete/finalize commands from treating `replan_required` or `replanned` as successful completion.
  - Preserve legacy checked/deferred behavior and root/generated lifecycle parity.
checked_summary_ja: 元要件をdigestで保持し、後続planと統合planへatomicに再構成できるようにした。

## Decisions

- Plan 076 must be accepted before this plan starts.
- Use one durable JSON replan contract plus a historical Markdown source-plan record.
- Do not reset, stash, delete, commit, or apply product changes as part of restructuring.
- Keep mutation in one command with deterministic preflight and rollback tests.

## Tasks

- [x] Add replan contract schema and atomic root transition.
- [x] Add generated transition and lifecycle-index behavior.
- [x] Add success, collision, tampering, concurrency, dirty-worktree, and failure-injection tests.
- [x] Run required validation, independent review, archive, and commit before plan 078.

## Validation Notes

- `python3 tests/test-plan-restructure.py`: 10 tests passed.
- `tests/root-plan-lifecycle.sh`: passed.
- `python3 scripts/check-root-agent-policy.py`: passed.
- `python3 scripts/check-copier-template.py`: passed.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the documented actionlint-unavailable skip and fallback backend.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Independent `change_reviewer` initially found three Medium issues in successor manifest admission, acceptance-text binding, and durable contract verification. All were fixed; final rereview reported zero unresolved High or Medium findings.
