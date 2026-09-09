# Map every acceptance item to its earliest validation witness

status: replanned
replan_reason_codes:
  - parent_remediation_budget_exhausted
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
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
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/16-31/162-integrate-structured-worker-completion-receipt.md
  - docs/plan/checked/2026/08/16-31/115-classify-review-outcomes-and-sequence-writes.md
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
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
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
- Focused validation passed 37 validation-tool tests, the root policy check, the Copier static check, and `git diff --check`; the authoritative suite was not run.
- After two parent-direct remediation rounds, final independent review still found three High and one Medium findings covering legacy-provenance forgery, authoritative-suite preservation, validation-authority write-scope drift, and symlinked context ancestry.
- Execution ledger `/tmp/project-agent-workflow-plan130-20260822-b/execution-state.json` entered `replan_required` with `parent_remediation_budget_exhausted`; stop this plan before further implementation, validation, completion, or archival.
