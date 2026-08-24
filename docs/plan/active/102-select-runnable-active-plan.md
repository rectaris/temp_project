# Select the runnable active plan from explicit lifecycle state

status: in_progress
primary_invariant: the parent selects exactly one runnable active plan from the active index and plan status instead of being blocked by a lower-numbered deferred plan
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - references/orchestration.md
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/smoke.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Select exactly one in_progress plan from the active index, reject zero or multiple runnable plans and index/file status mismatch, and never let a lower-numbered deferred plan block the selected runnable plan.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:2e98ca54eef54e608c2ae76a766dacf9c70f020467d0693e49cbd69302676a21","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
predecessor_plans: []
integration_gates:
  - preserve scripts/check-copier-template.py and tests/copier-update.sh without editing, staging, or committing them
  - Plan 188 remains deferred until this plan is checked and its exact checked archive path replaces this active predecessor
checked_summary_ja: active indexとplan statusから実行可能な1件を選び、番号が小さいdeferred planで停止しないようにする。

## Decisions

- runnable_active_plan means the one index row whose status and plan manifest are both in_progress.
- Reject zero or multiple runnable rows, duplicate ids or paths, index/file status mismatch, malformed rows, and a selected plan with unresolved predecessor inputs.
- Keep integer prefixes as immutable identities and archive ordering only; do not use them as the runnable-plan selector.
- Keep root and generated sequential-orchestrator Skill semantics aligned and enforce the selection rule in deterministic policy checks.
- Use bounded parent implementation and independent review because the selector controls every later writable plan.

## Tasks

- [x] Replace numeric-first selection with exact index/status selection in root and generated orchestration guidance.
- [x] Add deterministic checks for one runnable row, zero or multiple rows, stale index status, deferred lower ids, duplicate identities, and unresolved predecessor inputs.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the authoritative suite once, archive, commit, and activate Plan 188 with this exact checked predecessor.

## Validation Notes

- This bootstrap changes only plan selection semantics and no product file.
- The user authorized full active-plan reconstruction on 2026-08-24.
- Focused validation (`check-root-agent-policy.py`), `lint-project-workflow.sh`, `tests/smoke.sh`, and `git diff --check` all passed.
