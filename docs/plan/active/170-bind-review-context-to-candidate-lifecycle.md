# Bind review context to candidate lifecycle

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
primary_invariant: each admitted candidate receives at most one initial review and one rereview from runtime-proven zero-inheritance reviewer sessions not reused across numbered plans
write_scope:
  - AGENTS.md
  - .codex/skills/sequential-plan-orchestrator/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/test-plan-execution-state.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/active/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
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
replan_source: docs/plan/active/132-checkpoint-plan-session-resources.md
replan_contract: docs/plan/replanned/contracts/132-checkpoint-plan-session-resources.json
integration_gates:
  - Plans 168 and 169 must be checked and their exact checked archives must replace active context paths before implementation
  - derive the review target from the admitted candidate lifecycle rather than a receipt-selected digest
  - Plan 171 must start in a different directly observed root session after this plan is checked
successor_plans:
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/active/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
  - docs/plan/active/171-integrate-session-resource-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: reviewerの限定入力、継承turn 0、候補単位の2回上限を実行台帳へ結合する。

## Decisions

- Derive review identity from the admitted candidate lifecycle and diff digest, not from reviewer-supplied labels.
- Verify zero inherited turns through the runtime evidence accepted by Plan 168.
- Carry complete reviewer-session history through every terminal checkpoint boundary.
- Permit one initial review and one rereview for each admitted candidate lifecycle.

## Tasks

- [ ] Define the candidate-bound review receipt and runtime inheritance evidence.
- [ ] Enforce per-candidate review rounds and cross-plan reviewer-session non-reuse.
- [ ] Carry complete reviewer history at every checkpoint boundary.
- [ ] Add rejection tests for fabricated inheritance, target reset, omitted history, and reviewer reuse.
- [ ] Align root and generated policy and Skill guidance.
- [ ] Run focused validation, independent review, authoritative validation once, archive, and commit.

## Validation Notes

- Plan 132 rereview proved that a receipt-selected target digest and optional predecessor checkpoint do not enforce the review budget.
