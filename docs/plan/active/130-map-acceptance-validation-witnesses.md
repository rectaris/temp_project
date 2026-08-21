# Map every acceptance item to its earliest validation witness

status: in_progress
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: reject a plan whose acceptance cannot reach its earliest parent-owned validation witness without weakening the authoritative suite
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-validation-tools.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
  - docs/plan/active/114-validate-structured-worker-completion.md
  - docs/plan/active/115-classify-review-outcomes-and-sequence-writes.md
  - docs/plan/replanned/2026/08/16-31/116-evaluate-plan-worker-orchestration.md
  - docs/plan/checked/2026/08/01-15/075-staged-orchestration-acceptance.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
replan_source: docs/plan/active/116-evaluate-plan-worker-orchestration.md
replan_contract: docs/plan/replanned/contracts/116-evaluate-plan-worker-orchestration.json
integration_gates:
  - plan 136 as the accepted successor for plan 113, plus plans 114 and 115, must be checked before implementation starts
  - plan 133 must evaluate the accepted witness mapping without weakening the source authoritative suite
successor_plans:
  - docs/plan/active/130-map-acceptance-validation-witnesses.md
  - docs/plan/active/131-require-confirmed-failure-diagnosis.md
  - docs/plan/active/132-checkpoint-plan-session-resources.md
  - docs/plan/active/133-evaluate-resource-bounded-orchestration.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 各受入条件を最初に確認する限定検証へ対応付け、最終検証まで統合不整合を持ち越さない。

## Decisions

- Add one structured `validation_witness_map` derived from the unchanged plan acceptance and parent-owned validation commands.
- Keep focused preflight distinct from the complete authoritative suite and never use the map to remove or weaken an authoritative command.
- Require an explicit bounded reason when an integration boundary cannot have a narrower safe preflight.
- Derive Copier fixture copy and Git staging inputs from one inventory instead of parallel hand-maintained lists.
- Use bounded parent implementation and independent review because this plan changes validation-authority paths.

## Tasks

- [ ] Define the witness schema, plan parsing, identity binding, and rejection behavior.
- [ ] Enforce complete acceptance coverage and earliest-witness validity before candidate execution.
- [ ] Replace Copier fixture copy/stage duplication with one inventory and add drift tests.
- [ ] Align root and generated policy, parsing, checks, fixtures, and Copier behavior.
- [ ] Review the bounded parent diff, run focused validation, obtain independent review, run the authoritative suite once, and archive the accepted plan.

## Validation Notes

- The user approved this validation-boundary change on 2026-08-21.
- The source Plan 116 acceptance text is preserved exactly.
