# Integrate candidate review boundaries

status: checked
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
primary_invariant: the checked Plan 174 archive durably closes this required Plan 170 successor without another implementation or validation cycle
write_scope:
  - docs/plan/active/171-integrate-session-resource-boundaries.md
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
  - docs/plan/checked/2026/08/16-31/174-linearize-reviewer-session-registry.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
acceptance:
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
replan_source: docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
replan_contract: docs/plan/replanned/contracts/170-bind-review-context-to-candidate-lifecycle.json
integration_gates:
  - Plan 174 is checked and consumed through its exact archive path
  - The checked Plan 174 record must preserve and validate the complete unchanged Plan 170 acceptance
  - Make no product, policy, template, script, or test change under this plan
  - Do not run a second independent review or authoritative validation; record the Plan 174 evidence and archive this durable successor
successor_plans:
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
  - docs/plan/active/175-integrate-candidate-review-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: Plan 174の統合検証を参照し、追加実装なしでPlan 170の後継記録を閉じる。

## Decisions

- Plan 174 owns the final validation that combines candidate identity, runtime turn-zero evidence, and reviewer-session reuse prevention.
- Preserve this plan because the accepted Plan 170 restructuring contract names it as a durable successor.
- After Plan 174 is checked, refresh this plan and Plan 171 to its exact archive, record the inherited validation evidence, and archive without implementation.

## Tasks

- [x] Wait for Plan 174 to be checked.
- [x] Replace the active Plan 174 context with its exact checked archive.
- [x] Confirm that the checked Plan 174 record preserves the unchanged acceptance digest and records successful focused, independent-review, and authoritative evidence.
- [x] Confirm that Plan 171 consumes the checked Plan 174 archive.
- [x] Archive this plan without product changes or another validation cycle.

## Validation Notes

- Plan 170 was restructured after its bounded rereview found unresolved candidate identity, runtime evidence, and reviewer-history boundaries.
- On 2026-08-23 the user approved removing this plan from the implementation priority chain while retaining it as the durable successor record required by the existing restructuring contract.
- Plan 174 completed the combined implementation, fresh independent review, and authoritative validation for the unchanged Plan 170 acceptance. This plan adds no product or policy change and records that checked evidence only.
- Closure checks passed with `python3 scripts/restructure-plan.py --verify` and `git diff --check`.
