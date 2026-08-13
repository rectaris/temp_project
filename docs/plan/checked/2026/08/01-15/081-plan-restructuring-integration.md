# Integrate restructured plan execution and update evidence

status: checked
primary_invariant: prove the complete source acceptance baseline after the authority repair
replan_source: docs/plan/active/079-plan-restructuring-integration.md
replan_contract: docs/plan/replanned/contracts/079-plan-restructuring-integration.json
integration_gates:
  - plan 080 is checked with exact successor acceptance authority
  - fixed scenarios and the untuned holdout execute against the real lifecycle commands
  - Copier preserves a real replanned archive, contract, and index triplet
successor_plans:
  - docs/plan/active/080-successor-acceptance-authority.md
  - docs/plan/active/081-plan-restructuring-integration.md
inherited_acceptance_digests:
  - sha256:e5ee0e951c5eef281fc3f54c22d549dffd750f43f0e232f724b12d8e0ed2e637
  - sha256:99fac9ef19ac18be11c578944c85b91c925efd945bf374f2bf6a5654e0b2e6b2
  - sha256:f63ec861469ec27fe14daef2ba73dc1cdeadae80e5a35395c09f35abfe486c57
  - sha256:675856f8d05166ebfc9efa5b4fffc5199d404792bf648a919f094bd3e9ea2c8e
  - sha256:30e8a6c3d65ec3e739284e02025847bf88f88901e855beec711bf8424f3866f7
  - sha256:6d763d5c86eacb20d1eb1cc7e29cb45707d57c2ec2c7fd9e74af6a4074ad7001
  - sha256:5cc609d78dd1464f9a71b7dde9005bb8ebe3db475048a24a2bd804dc86d8fef8
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
  - scripts/plan_validation_commands.py
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - template/docs/plan/
  - tests/copier-update.sh
  - tests/fixtures/orchestration/
  - tests/smoke.sh
  - tests/test-plan-execution-state.py
  - tests/test-plan-restructure.py
  - tests/test-validation-tools.py
context_files:
  - docs/plan/replanned/2026/08/01-15/079-plan-restructuring-integration.md
  - docs/plan/replanned/contracts/079-plan-restructuring-integration.json
  - docs/plan/checked/2026/08/01-15/076-plan-restructuring-policy-schema.md
  - docs/plan/checked/2026/08/01-15/077-atomic-plan-restructuring.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add fixed median, edge, negative, and untuned holdout scenarios for requirement preservation, exhausted delegated corrections, repeated parent-direct review findings, multi-invariant findings, scope drift, and post-authoritative design changes.
  - Prove that every hard trigger blocks continued implementation and requires an atomic successor and integration-plan transition.
  - Prove that requirement changes remain pending until explicit user authorization and cannot be disguised as clarification or successor mapping.
  - Keep root and generated policy, schemas, commands, Skills, tests, indexes, and lifecycle behavior aligned.
  - Preserve project-owned product code, policy, configuration, plan history, and validation behavior through supported Copier copy and update paths.
  - Reject unresolved conflicts, rejection files, unclassified tracked-file deletion, destination collisions, index divergence, and partial transition artifacts.
  - Run one independent final High/Medium review before the authoritative suite and keep zero unresolved High or Medium findings.
checked_summary_ja: 再構成したplan実行と更新証拠を統合し、元planの受入れ条件をすべて検証した。

## Decisions

- Plan 080 must be checked before authoritative integration validation begins.
- Execute the untuned holdout against the real ledger and restructure command, not only the fixture checker.
- Preserve a real archive, durable contract, and replanned index by exact hash across Copier update.

## Tasks

- [x] Complete and accept plan 080.
- [x] Finish fixed scenario, holdout, and Copier history-triplet execution coverage.
- [x] Run final independent review and resolve every High or Medium finding.
- [x] Run the authoritative suite once, archive this plan, and commit.

## Validation Notes

- Plan 079 stopped after independent review exposed separate authority and integration invariants.
- Plan 080 was accepted with zero unresolved High or Medium findings and archived before integration resumed.
- Fixed tuning scenarios execute through the ledger, runner gate, and atomic restructuring command.
- The physically separate untuned holdout executes security-boundary stop, dirty product byte preservation, and contract verification.
- Copier update coverage constructs and verifies a real replanned archive, durable contract, and replanned index by exact before/after hashes.
- Focused holdout tests, shell/Python syntax, diff whitespace, and durable contract verification passed before final independent review.
- Final independent review reported zero unresolved High or Medium findings before the authoritative suite.
- Authoritative results: plan restructuring 16 tests, execution ledger 12 tests, sandboxed runner 65 tests, and validation tools 31 tests passed; runner self-test, root policy, Copier template, workflow lint, and smoke passed.
- The first required Copier run stopped because the v0.4.6 fixture declared post-migration spec paths. The fixture was corrected to its actual pre-v1 root layout; the required Copier lane then passed with archive, contract, and index hashes preserved plus post-update contract verification and plan lint.
- After the localized Copier correction, `python3 scripts/validate-changes.py --all` and `git diff --check` passed. Independent review of the suite-after correction reported zero unresolved High or Medium findings.
