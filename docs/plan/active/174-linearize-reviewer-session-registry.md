# Linearize reviewer session registry

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
primary_invariant: each runtime-proven reviewer session is admitted once across an unbounded numbered-plan chain and the combined candidate review boundaries satisfy the unchanged Plan 170 acceptance
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
  - docs/plan/checked/2026/08/16-31/172-bind-review-to-candidate-leaf.md
  - docs/plan/checked/2026/08/16-31/173-record-runtime-review-turn-zero.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 -m unittest tests.hooks.logging
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 -m unittest tests.hooks.logging
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
  - Plans 172 and 173 must be checked and are consumed through their exact archive paths
  - The registry remains outside the repository and stores only reviewer-session digests and bounded event metadata
  - This plan performs the complete Plan 170 integration and revalidates the unchanged source acceptance
  - Plan 175 receives no product implementation or separate authoritative validation and closes only as the durable successor record required by the existing Plan 170 restructuring contract
  - Plan 171 remains deferred until this plan is checked
successor_plans:
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
  - docs/plan/active/175-integrate-candidate-review-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: reviewer sessionの再利用を外部registryで全plan横断に拒否し、Plan 170の受入条件を統合検証する。

## Decisions

- reviewer-session-registry means the append-only parent-owned external record used for exact cross-plan reviewer-session membership checks.
- Check membership and append under one exclusive lock; copied checkpoints or registries cannot authorize a second admission.
- Bind checkpoint records to the registry event-chain digest and entry count instead of copying a cumulative digest list.
- Own the final integration of candidate identity, runtime turn-zero evidence, and reviewer-session reuse prevention.
- Keep Plan 175 only as a no-change closure record; do not run another implementation or authoritative-validation cycle for it.

## Tasks

- [ ] Define the bounded registry schema, event chain, lock, and checkpoint reference.
- [ ] Require exact membership rejection before recording a review event.
- [ ] Carry registry identity through checkpoint issuance and successor claim.
- [ ] Add long-chain, copied-checkpoint, crash-recovery, omitted-registry, and reviewer-reuse tests.
- [ ] Align root and generated policy and Skill guidance.
- [ ] Reconcile the checked Plan 172 and 173 mechanisms with the registry and run the complete focused suite.
- [ ] Obtain one fresh independent review and run authoritative validation exactly once for the complete Plan 170 acceptance.
- [ ] Update Plan 171 to consume the checked Plan 174 archive, close Plan 175 without product changes, archive, and commit.

## Validation Notes

- Plan 170 was restructured after its bounded rereview found unresolved candidate identity, runtime evidence, and reviewer-history boundaries.
- On 2026-08-23 the user approved consolidating the remaining Plan 174 and 175 implementation work to prevent integration-plan priority inversion.
