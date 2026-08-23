# Integrate candidate review boundaries

status: in_progress
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
primary_invariant: checked candidate identity runtime turn-zero evidence and reviewer registry jointly satisfy the unchanged Plan 170 acceptance without unresolved High or Medium findings
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/active/171-integrate-session-resource-boundaries.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/hooks/logging.py
  - tests/test-plan-execution-state.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/168-verify-runtime-session-resource-evidence.md
  - docs/plan/checked/2026/08/16-31/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 -m pytest tests/hooks
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 -m pytest tests/hooks
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
replan_contract: docs/plan/replanned/contracts/170-bind-review-context-to-candidate-lifecycle.json
integration_gates:
  - Plans 172 through 174 must be checked before implementation
  - Run one complete parent-owned focused suite before independent review and authoritative validation
  - Plan 171 remains deferred until this plan is checked
successor_plans:
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
  - docs/plan/active/175-integrate-candidate-review-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: 候補識別、turn 0証拠、reviewer registryを統合して元の受入条件を検証する。

## Decisions

- candidate-review-boundary-integration means the final validation that combines the three checked review-boundary mechanisms against the original acceptance.
- Consume only checked archives from Plans 172 through 174.
- Keep Plan 171 deferred until this integration is checked, then refresh its predecessor context to the checked Plan 170 successor chain.

## Tasks

- [ ] Replace active predecessor context with exact checked archives for Plans 172 through 174.
- [ ] Reconcile root and generated policy, scripts, tests, and Copier checks.
- [ ] Run the complete focused suite and one fresh independent review.
- [ ] Run the authoritative suite exactly once.
- [ ] Update Plan 171 to consume the checked successor chain, archive this plan, and commit.

## Validation Notes

- Plan 170 was restructured after its bounded rereview found unresolved candidate identity, runtime evidence, and reviewer-history boundaries.
