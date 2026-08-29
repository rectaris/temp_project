# Verify Plan 183 successor acceptance

status: backlog
primary_invariant: checked Plan 182 and the checked runtime and checker replacements jointly satisfy the unchanged Plan 183 acceptance before Plan 184 performs its own verification
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/active/184-verify-plan178-successor-acceptance.md
  - docs/plan/plan.md
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/replanned/2026/08/16-31/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - sh -n tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
replan_source: docs/plan/active/183-build-bounded-copier-transition-fixture.md
replan_contract: docs/plan/replanned/contracts/183-build-bounded-copier-transition-fixture.json
integration_gates:
  - Plans 227 and 186 must be checked and their exact checked archive paths must replace active context paths before focused validation
  - after Plans 227 and 186 are checked, remove both preservation entries and add scripts/check-copier-template.py and tests/copier-update.sh as exact read-only context in the same parent-owned activation update
  - do not edit, stage, or commit scripts/check-copier-template.py or tests/copier-update.sh in this plan
  - Plan 184 must not start until this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
successor_plans:
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/active/186-bind-connected-copier-fixture-checker.md
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: checked Plan 182とruntime・checker後継を統合確認し、Plan 183の受入条件を維持する。

## Decisions

- Plan 183 successor acceptance gate means the condition that checked Plan 182 and both checked replacement implementation artifacts satisfy the unchanged Plan 183 acceptance before Plan 184 performs its own verification and Plan 179 runs the complete transition.
- Treat both product paths as exact read-only context and current dirty preservation coverage; neither role grants write authority, and any product edit in this plan requires another replan.
- Verify each implementation commit and its fresh independent review before running the original Plan 183 focused commands.
- Confirm that checked Plans 227 and 186 preserve and enforce the committed v1.4.4 pre-schema active plan, replanned source archive, replan contract, and its capture in the consumed provenance record.
- This plan supplies checked replacement evidence to Plan 184 and does not replace Plan 184's responsibility to verify committed Plan 182 and the replacement Plan 183 result.

## Tasks

- [ ] Replace Plans 227 and 186 active context paths with their exact checked archives and verify both implementation commits and review evidence.
- [ ] Confirm the final checker retains Plan 182's parsed migration and one-inventory checks and enforces every Plan 227 synchronization, process, provenance, and guardian operation.
- [ ] Confirm the final checker rejects omission or bypass of the committed v1.4.4 pre-schema plan and replan-contract fixture before accepting the replacement result.
- [ ] Run the original Plan 183 focused validation and fresh independent read-only review with zero unresolved High or Medium findings.
- [ ] Archive and commit only lifecycle files, then refresh Plan 184 to this checked archive.

## Validation Notes

- The stopped Plan 183 ledger and reviews are advisory history and cannot authorize this successor acceptance.
- This plan does not execute the complete Copier transition and does not change product files.
